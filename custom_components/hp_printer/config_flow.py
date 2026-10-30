"""Config flow for the HP Printer integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from hp_printer import (
    HPPrinter,
    HPPrinterConnectionError,
    HPPrinterError,
    HPPrinterNotSupportedError,
)

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
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_COLOR_MODES,
    SCAN_FORMATS,
    SCAN_RESOLUTIONS,
    SCAN_SOURCES,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Optional(CONF_PASSWORD, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)
PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _options_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=5,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Optional(
                CONF_SCAN_RESOLUTION, default=DEFAULT_SCAN_RESOLUTION
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=str(r), label=f"{r} dpi")
                        for r in SCAN_RESOLUTIONS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_SCAN_COLOR_MODE, default=DEFAULT_SCAN_COLOR_MODE
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_COLOR_MODES),
                    translation_key=CONF_SCAN_COLOR_MODE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_SCAN_FORMAT, default=DEFAULT_SCAN_FORMAT): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_FORMATS),
                    translation_key=CONF_SCAN_FORMAT,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_SCAN_SOURCE, default=DEFAULT_SCAN_SOURCE): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_SOURCES),
                    translation_key=CONF_SCAN_SOURCE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_SCAN_DIRECTORY, default=""): TextSelector(),
        }
    )


class HPPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery, manual setup, reauth and reconfigure."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._host: str | None = None
        self._name: str | None = None

    async def _async_probe(
        self, host: str, password: str | None
    ) -> tuple[dict[str, str], dict[str, Any]]:
        """Connect to the printer; return (errors, info)."""
        errors: dict[str, str] = {}
        info: dict[str, Any] = {}
        client = HPPrinter(
            host, password=password or None, session=async_get_clientsession(self.hass)
        )
        try:
            await client.discover()
            device = await client.get_device_info()
            if password:
                verified = await client.check_password()
                if verified is False:
                    errors["base"] = "invalid_auth"
        except HPPrinterNotSupportedError:
            errors["base"] = "not_supported"
        except HPPrinterConnectionError:
            errors["base"] = "cannot_connect"
        except HPPrinterError:
            LOGGER.exception("Unexpected error probing %s", host)
            errors["base"] = "unknown"
        else:
            info = {
                "unique_id": (device.uuid or device.serial_number or host).lower(),
                "title": device.name,
                "serial": device.serial_number,
            }
        return errors, info

    # ------------------------------------------------------------------ #
    # Manual
    # ------------------------------------------------------------------ #
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, info = await self._async_probe(
                user_input[CONF_HOST], user_input.get(CONF_PASSWORD)
            )
            if not errors:
                await self.async_set_unique_id(
                    info["unique_id"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or {CONF_HOST: self._host or ""}
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle mDNS discovery (_ipp, _ipps, _uscan, _printer)."""
        props = {k.lower(): v for k, v in discovery_info.properties.items()}
        uuid = props.get("uuid")
        host = discovery_info.host
        name = props.get("ty") or discovery_info.name.split(".")[0]
        if uuid:
            await self.async_set_unique_id(uuid.lower())
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        else:
            self._async_abort_entries_match({CONF_HOST: host})
        self._host = host
        self._name = name
        self.context["title_placeholders"] = {"name": name, "host": host}
        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery: update the host of a known printer."""
        mac = format_mac(discovery_info.macaddress)
        for entry in self._async_current_entries(include_ignore=False):
            device_mac = entry.data.get("mac")
            if device_mac and format_mac(device_mac) == mac:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: discovery_info.ip}
                )
                return self.async_abort(reason="already_configured")
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})
        errors, info = await self._async_probe(discovery_info.ip, None)
        if errors:
            return self.async_abort(reason=errors["base"])
        await self.async_set_unique_id(info["unique_id"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self._host = discovery_info.ip
        self._name = info["title"]
        self.context["title_placeholders"] = {"name": info["title"], "host": self._host}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered printer (optionally with the admin password)."""
        errors: dict[str, str] = {}
        if user_input is not None and self._host:
            errors, info = await self._async_probe(
                self._host, user_input.get(CONF_PASSWORD)
            )
            if not errors:
                await self.async_set_unique_id(
                    info["unique_id"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: self._host,
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                    },
                )
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=PASSWORD_SCHEMA,
            description_placeholders={
                "name": self._name or "HP printer",
                "host": self._host or "",
            },
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Reauth / reconfigure / options
    # ------------------------------------------------------------------ #
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The printer rejected the admin password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new admin password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, _ = await self._async_probe(
                entry.data[CONF_HOST], user_input.get(CONF_PASSWORD)
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input.get(CONF_PASSWORD, "")},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=PASSWORD_SCHEMA,
            description_placeholders={"name": entry.title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host and/or password."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, info = await self._async_probe(
                user_input[CONF_HOST], user_input.get(CONF_PASSWORD)
            )
            if not errors:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HPPrinterOptionsFlow:
        """Return the options flow."""
        return HPPrinterOptionsFlow()


class HPPrinterOptionsFlow(OptionsFlowWithReload):
    """Polling interval and scan defaults."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show/save the options."""
        if user_input is not None:
            user_input[CONF_SCAN_RESOLUTION] = int(user_input[CONF_SCAN_RESOLUTION])
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)
        current = dict(self.config_entry.options)
        if CONF_SCAN_RESOLUTION in current:
            current[CONF_SCAN_RESOLUTION] = str(current[CONF_SCAN_RESOLUTION])
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_options_schema(), current),
        )
