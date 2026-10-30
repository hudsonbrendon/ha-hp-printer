"""Data update coordinator for HP printers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from hp_printer import (
    HPPrinter,
    HPPrinterAuthenticationError,
    HPPrinterConnectionError,
    HPPrinterError,
    HPPrinterNotSupportedError,
    HPPrinterScanError,
    PrinterData,
    ScanSettings,
)
from hp_printer.models import Capabilities

from .const import (
    CONF_SCAN_COLOR_MODE,
    CONF_SCAN_DIRECTORY,
    CONF_SCAN_FORMAT,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_RESOLUTION,
    CONF_SCAN_SOURCE,
    DEFAULT_SCAN_COLOR_MODE,
    DEFAULT_SCAN_FORMAT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_RESOLUTION,
    DEFAULT_SCAN_SOURCE,
    DOMAIN,
    LEDM_EVENT_MAP,
    LOGGER,
    MEDIA_SUBDIR,
    SIGNAL_EVENT,
    SIGNAL_SCAN_DONE,
    STATIC_EVERY_POLLS,
)

if TYPE_CHECKING:
    from . import HPPrinterConfigEntry


class ScanResult:
    """Outcome of a scan started from Home Assistant."""

    def __init__(
        self, pages: list[bytes], content_type: str, path: Path | None, when: datetime
    ) -> None:
        """Store the scanned pages and where they were saved."""
        self.pages = pages
        self.content_type = content_type
        self.path = path
        self.when = when

    @property
    def first_page(self) -> bytes:
        """First page / the PDF."""
        return self.pages[0]

    def as_dict(self) -> dict[str, Any]:
        """Response payload for the ``scan`` action."""
        return {
            "path": str(self.path) if self.path else None,
            "pages": len(self.pages),
            "content_type": self.content_type,
            "size": sum(len(p) for p in self.pages),
            "scanned_at": self.when.isoformat(),
        }


class HPPrinterCoordinator(DataUpdateCoordinator[PrinterData]):
    """Poll the printer and expose actions shared by the platforms."""

    config_entry: HPPrinterConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HPPrinterConfigEntry, client: HPPrinter
    ) -> None:
        """Initialise the coordinator."""
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} {entry.title}",
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.capabilities: Capabilities | None = None
        self.last_scan: ScanResult | None = None
        self.scanning = False
        self._poll = 0
        self._event_stamps: dict[str, str] = {}
        self._job_states: dict[int, str | None] = {}

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #
    async def _async_setup(self) -> None:
        """Discover what the printer supports before the first refresh."""
        try:
            self.capabilities = await self.client.discover()
        except HPPrinterConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.client.host, "error": str(err)},
            ) from err
        except HPPrinterNotSupportedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="not_supported",
                translation_placeholders={"host": self.client.host},
            ) from err

    async def _async_update_data(self) -> PrinterData:
        """Fetch status (every poll) and static data (every N polls)."""
        full = self.data is None or self._poll % STATIC_EVERY_POLLS == 0
        try:
            data = await self.client.update(
                include_static=full,
                include_network=full,
                include_jobs=True,
                previous=self.data,
            )
        except HPPrinterConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.client.host, "error": str(err)},
            ) from err
        except HPPrinterError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._poll += 1
        self._detect_events(data)
        return data

    def _detect_events(self, data: PrinterData) -> None:
        """Fire dispatcher signals for new LEDM events and job transitions."""
        stamps = {e.category: e.aging_stamp or "" for e in data.events}
        if self._event_stamps:
            for category, stamp in stamps.items():
                if self._event_stamps.get(category) != stamp:
                    event_type = LEDM_EVENT_MAP.get(category)
                    if event_type:
                        async_dispatcher_send(
                            self.hass,
                            SIGNAL_EVENT,
                            self.config_entry.entry_id,
                            event_type,
                            {"category": category, "aging_stamp": stamp},
                        )
        self._event_stamps = stamps
        job_states = {job.id: job.state for job in data.jobs}
        if self._job_states:
            for job in data.jobs:
                previous = self._job_states.get(job.id)
                if previous is None and job.is_active:
                    async_dispatcher_send(
                        self.hass,
                        SIGNAL_EVENT,
                        self.config_entry.entry_id,
                        "print_job_started",
                        {"job_id": job.id, "job_name": job.name},
                    )
                elif (
                    previous
                    and previous != job.state
                    and job.state
                    in (
                        "completed",
                        "canceled",
                        "aborted",
                    )
                ):
                    async_dispatcher_send(
                        self.hass,
                        SIGNAL_EVENT,
                        self.config_entry.entry_id,
                        "print_job_completed",
                        {"job_id": job.id, "job_name": job.name, "state": job.state},
                    )
        self._job_states = job_states

    # ------------------------------------------------------------------ #
    # Helpers used by entities and actions
    # ------------------------------------------------------------------ #
    @property
    def serial(self) -> str:
        """Serial number used in paths and identifiers."""
        if self.data and self.data.device and self.data.device.serial_number:
            return self.data.device.serial_number
        return self.config_entry.unique_id or self.config_entry.entry_id

    async def async_write(self, action: Callable[[], Awaitable[Any]]) -> Any:
        """Run a write on the printer, translate errors and refresh afterwards."""
        try:
            result = await action()
        except HPPrinterAuthenticationError as err:
            if self.client.password:
                self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="password_required"
                if not self.client.password
                else "invalid_auth",
            ) from err
        except HPPrinterNotSupportedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_supported_action",
                translation_placeholders={"error": str(err)},
            ) from err
        except HPPrinterError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()
        return result

    def scan_settings(self, **overrides: Any) -> ScanSettings:
        """Build scan settings from the entry options plus overrides."""
        options = self.config_entry.options
        values = {
            "resolution": options.get(CONF_SCAN_RESOLUTION, DEFAULT_SCAN_RESOLUTION),
            "color_mode": options.get(CONF_SCAN_COLOR_MODE, DEFAULT_SCAN_COLOR_MODE),
            "document_format": options.get(CONF_SCAN_FORMAT, DEFAULT_SCAN_FORMAT),
            "source": options.get(CONF_SCAN_SOURCE, DEFAULT_SCAN_SOURCE),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        return ScanSettings(**values)

    def scan_directory(self) -> Path:
        """Directory where scans are stored (``/media/hp_printer/<serial>``)."""
        configured = self.config_entry.options.get(CONF_SCAN_DIRECTORY)
        if configured:
            return Path(configured)
        media_dirs = self.hass.config.media_dirs or {}
        base = media_dirs.get("local") or self.hass.config.path("media")
        return Path(base) / MEDIA_SUBDIR / slugify(self.serial)

    async def async_scan(
        self, *, filename: str | None = None, **overrides: Any
    ) -> ScanResult:
        """Scan with the configured defaults, save the result and notify."""
        if self.scanning:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="scan_in_progress"
            )
        settings = self.scan_settings(**overrides)
        self.scanning = True
        self.async_update_listeners()
        try:
            pages = await self.client.scan(settings)
        except HPPrinterScanError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="scan_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except HPPrinterError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            self.scanning = False
        now = dt_util.now()
        path = await self.hass.async_add_executor_job(
            self._save_scan, pages, settings, filename, now
        )
        result = ScanResult(pages, settings.document_format, path, now)
        self.last_scan = result
        async_dispatcher_send(self.hass, SIGNAL_SCAN_DONE, self.config_entry.entry_id)
        async_dispatcher_send(
            self.hass,
            SIGNAL_EVENT,
            self.config_entry.entry_id,
            "scan_completed",
            result.as_dict(),
        )
        self.async_update_listeners()
        return result

    def _save_scan(
        self,
        pages: list[bytes],
        settings: ScanSettings,
        filename: str | None,
        when: datetime,
    ) -> Path | None:
        directory = self.scan_directory()
        directory.mkdir(parents=True, exist_ok=True)
        stem = filename or f"scan_{when.strftime('%Y%m%d_%H%M%S')}"
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(stem).stem) or "scan"
        if len(pages) == 1:
            target = directory / f"{stem}.{settings.extension}"
            target.write_bytes(pages[0])
            return target
        first: Path | None = None
        for index, page in enumerate(pages, 1):
            target = directory / f"{stem}_{index}.{settings.extension}"
            target.write_bytes(page)
            first = first or target
        return first
