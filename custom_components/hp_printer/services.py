"""Integration actions: scan, print_file, print_report, identify, cancel_job..."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from hp_printer import INTERNAL_PRINT_JOBS

from .const import (
    ATTR_COLOR_MODE,
    ATTR_COPIES,
    ATTR_DEVICE_ID,
    ATTR_FILENAME,
    ATTR_FORMAT,
    ATTR_JOB_ID,
    ATTR_LEVEL,
    ATTR_PAGE,
    ATTR_PATH,
    ATTR_RESOLUTION,
    ATTR_SOURCE,
    DOMAIN,
    SCAN_COLOR_MODES,
    SCAN_FORMATS,
    SCAN_SOURCES,
    SERVICE_CANCEL_JOB,
    SERVICE_CLEAN_CARTRIDGES,
    SERVICE_IDENTIFY,
    SERVICE_PRINT_FILE,
    SERVICE_PRINT_REPORT,
    SERVICE_SCAN,
)

if TYPE_CHECKING:
    from .coordinator import HPPrinterCoordinator

DEVICE_SCHEMA = {vol.Required(ATTR_DEVICE_ID): cv.string}

SCAN_SCHEMA = vol.Schema(
    {
        **DEVICE_SCHEMA,
        vol.Optional(ATTR_RESOLUTION): vol.All(
            vol.Coerce(int), vol.Range(min=75, max=2400)
        ),
        vol.Optional(ATTR_COLOR_MODE): vol.In(SCAN_COLOR_MODES),
        vol.Optional(ATTR_FORMAT): vol.In(SCAN_FORMATS),
        vol.Optional(ATTR_SOURCE): vol.In(SCAN_SOURCES),
        vol.Optional(ATTR_FILENAME): cv.string,
    }
)
PRINT_FILE_SCHEMA = vol.Schema(
    {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_PATH): cv.string,
        vol.Optional(ATTR_FORMAT): cv.string,
        vol.Optional(ATTR_COPIES, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=99)
        ),
    }
)
PRINT_REPORT_SCHEMA = vol.Schema(
    {**DEVICE_SCHEMA, vol.Required(ATTR_PAGE): vol.In(INTERNAL_PRINT_JOBS)}
)
IDENTIFY_SCHEMA = vol.Schema(DEVICE_SCHEMA)
CANCEL_JOB_SCHEMA = vol.Schema(
    {**DEVICE_SCHEMA, vol.Optional(ATTR_JOB_ID): vol.Coerce(int)}
)
CLEAN_SCHEMA = vol.Schema(
    {
        **DEVICE_SCHEMA,
        vol.Optional(ATTR_LEVEL, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=3)
        ),
    }
)

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".pclm": "application/PCLm",
    ".urf": "image/urf",
    ".pwg": "image/pwg-raster",
    ".pcl": "application/vnd.hp-PCL",
    ".ps": "application/postscript",
}


def _coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> HPPrinterCoordinator:
    """Resolve the coordinator owning a device id."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    entry_ids = (
        [device.config_entry_id]
        if getattr(device, "config_entry_id", None)
        else list(getattr(device, "config_entries", []))
    )
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            continue
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"device_id": device_id},
            )
        return coordinator  # type: ignore[no-any-return]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={"device_id": device_id},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions once per Home Assistant instance."""

    async def scan(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        if not coordinator.data.capabilities.has_escl:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_scanner"
            )
        result = await coordinator.async_scan(
            filename=call.data.get(ATTR_FILENAME),
            resolution=call.data.get(ATTR_RESOLUTION),
            color_mode=call.data.get(ATTR_COLOR_MODE),
            document_format=call.data.get(ATTR_FORMAT),
            source=call.data.get(ATTR_SOURCE),
        )
        return result.as_dict() if call.return_response else None

    async def print_file(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        path = Path(call.data[ATTR_PATH])
        if not hass.config.is_allowed_path(str(path)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": str(path)},
            )
        if not await hass.async_add_executor_job(path.is_file):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"path": str(path)},
            )
        document_format = call.data.get(ATTR_FORMAT) or MIME_BY_SUFFIX.get(
            path.suffix.lower(),
            mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        data = await hass.async_add_executor_job(path.read_bytes)
        job = await coordinator.async_write(
            lambda: coordinator.client.print_data(
                data,
                document_format=document_format,
                job_name=path.name,
                copies=call.data[ATTR_COPIES],
            )
        )
        if not call.return_response:
            return None
        return {"job_id": job.id if job else None, "document_format": document_format}

    async def print_report(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_write(
            lambda: coordinator.client.print_internal_page(call.data[ATTR_PAGE])
        )

    async def identify(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_write(lambda: coordinator.client.identify())

    async def cancel_job(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        job_id = call.data.get(ATTR_JOB_ID)
        if job_id is None:
            current = coordinator.data.current_job
            if current is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_active_job"
                )
            job_id = current.id
        await coordinator.async_write(lambda: coordinator.client.cancel_job(job_id))

    async def clean_cartridges(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_write(
            lambda: coordinator.client.clean_cartridges(call.data[ATTR_LEVEL])
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        scan,
        schema=SCAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PRINT_FILE,
        print_file,
        schema=PRINT_FILE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PRINT_REPORT, print_report, schema=PRINT_REPORT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IDENTIFY, identify, schema=IDENTIFY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_JOB, cancel_job, schema=CANCEL_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAN_CARTRIDGES, clean_cartridges, schema=CLEAN_SCHEMA
    )


def service_response_keys() -> dict[str, Any]:
    """Documented response keys (used by tests and docs)."""
    return {
        "scan": ["path", "pages", "content_type", "size", "scanned_at"],
        "print_file": ["job_id", "document_format"],
    }
