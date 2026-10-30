"""Config, discovery, reauth, reconfigure and options flows."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from hp_printer import (
    HPPrinterConnectionError,
    HPPrinterError,
    HPPrinterNotSupportedError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hp_printer.const import (
    CONF_SCAN_COLOR_MODE,
    CONF_SCAN_DIRECTORY,
    CONF_SCAN_FORMAT,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_RESOLUTION,
    CONF_SCAN_SOURCE,
    DOMAIN,
)

from .conftest import HOST, TITLE, UUID, setup_integration


def _zeroconf(host: str = HOST, uuid: str | None = UUID) -> ZeroconfServiceInfo:
    props = {
        "ty": "HP DeskJet 2700 series",
        "usb_MFG": "HP",
        "mac": "5c:60:ba:50:24:72",
    }
    if uuid:
        props["UUID"] = uuid
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="HP5C60BA502472.local.",
        name="HP DeskJet 2700 series [502472]._ipp._tcp.local.",
        port=631,
        properties=props,
        type="_ipp._tcp.local.",
    )


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    mock_client.discover.side_effect = HPPrinterConnectionError("no")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: ""}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.discover.side_effect = HPPrinterNotSupportedError("no")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: ""}
    )
    assert result["errors"] == {"base": "not_supported"}

    mock_client.discover.side_effect = HPPrinterError("weird")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: ""}
    )
    assert result["errors"] == {"base": "unknown"}

    mock_client.discover.side_effect = None
    mock_client.check_password.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.check_password.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: "12345678"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_HOST: HOST, CONF_PASSWORD: "12345678"}
    assert result["result"].unique_id == UUID


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.31.99", CONF_PASSWORD: ""}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.31.99"


async def test_zeroconf_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=_zeroconf()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["name"] == "HP DeskJet 2700 series"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: ""}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID
    assert result["data"][CONF_HOST] == HOST


async def test_zeroconf_updates_host_of_known_printer(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf(host="192.168.31.77"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.31.77"


async def test_zeroconf_without_uuid(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf(uuid=None),
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID  # probed from the device


async def test_dhcp_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip=HOST, hostname="hp502472", macaddress="5c60ba502472"),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_dhcp_unreachable_aborts(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.discover.side_effect = HPPrinterConnectionError("no")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip=HOST, hostname="hp502472", macaddress="5c60ba502472"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth_flow(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    mock_client.check_password.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    mock_client.check_password.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "good"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "good"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    other = mock_client.get_device_info.return_value
    original_uuid = other.uuid
    other.uuid = "11111111-2222-3333-4444-555555555555"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.31.50", CONF_PASSWORD: ""}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"

    other.uuid = original_uuid
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.31.50", CONF_PASSWORD: "pw"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: "192.168.31.50", CONF_PASSWORD: "pw"}


async def test_options_flow(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 60,
            CONF_SCAN_RESOLUTION: "600",
            CONF_SCAN_COLOR_MODE: "Grayscale8",
            CONF_SCAN_FORMAT: "image/jpeg",
            CONF_SCAN_SOURCE: "Platen",
            CONF_SCAN_DIRECTORY: "",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_SCAN_INTERVAL] == 60
    assert mock_config_entry.options[CONF_SCAN_RESOLUTION] == 600
    assert mock_config_entry.options[CONF_SCAN_COLOR_MODE] == "Grayscale8"
    # reopening shows the stored values
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
