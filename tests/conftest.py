"""Fixtures: a fully mocked HPPrinter fed with real DeskJet 2774 dumps."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from hp_printer import PrinterData
from hp_printer.models import (
    Capabilities,
    ConsumablesInfo,
    CopyConfig,
    DeviceEvent,
    DeviceInfo,
    EPrint,
    Firmware,
    IppStatus,
    MediaHandling,
    Network,
    PrintConfig,
    ProductLogs,
    ScannerCapabilities,
    ScannerStatus,
    Settings,
    SettingsCapabilities,
    Status,
    Usage,
)
from hp_printer.xml_utils import parse_xml
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hp_printer.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "192.168.31.12"
UUID = "ab462181-f7b2-f0ee-b557-a0b7dbf0d250"
TITLE = "DeskJet 2700 series"


def xml(name: str):  # noqa: ANN201
    return parse_xml((FIXTURES / name).read_bytes())


def build_printer_data() -> PrinterData:
    """Assemble PrinterData from the captured LEDM/eSCL dumps."""
    caps = Capabilities.from_discovery(
        xml("DiscoveryTree.xml"),
        json.loads((FIXTURES / "servicesDiscovery.json").read_text()),
    )
    consumables = ConsumablesInfo.from_node(xml("ConsumableConfigDyn.xml"))
    consumables.merge_usage(xml("ProductUsageDyn.xml"))
    network = Network.from_nodes(
        xml("Adapters.xml"),
        xml("IoConfig.xml"),
        xml("NetAppsDyn.xml"),
        xml("NetAppsSecureDyn.xml"),
    )
    assert network.wifi is not None
    network.wifi.merge_protocols(xml("Wifi0Protocols.xml"))
    network.wifi.merge_stats(xml("Wifi0NetworkStats.xml"))
    return PrinterData(
        capabilities=caps,
        device=DeviceInfo.from_node(xml("ProductConfigDyn.xml")),
        settings=Settings.from_node(xml("ProductConfigDyn.xml")),
        settings_capabilities=SettingsCapabilities.from_node(
            xml("ProductConfigCap.xml")
        ),
        status=Status.from_node(xml("ProductStatusDyn.xml")),
        consumables=consumables,
        usage=Usage.from_node(xml("ProductUsageDyn.xml")),
        print_config=PrintConfig.from_node(
            xml("PrintConfigDyn.xml"), xml("PrintConfigCap.xml")
        ),
        copy_config=CopyConfig.from_node(
            xml("CopyConfigDyn.xml"), xml("CopyConfigCap.xml")
        ),
        media=MediaHandling.from_node(xml("MediaHandlingDyn.xml"), xml("MediaDyn.xml")),
        network=network,
        firmware=Firmware.from_node(xml("WebFWUpdate.xml")),
        eprint=EPrint.from_node(xml("ePrintConfigDyn.xml")),
        calibration_state="CalibrationRequired",
        internet_connection_state="idle",
        logs=ProductLogs.from_node(xml("ProductLogsDyn.xml")),
        events=[
            DeviceEvent.from_node(e) for e in xml("EventTable.xml").findall("Event")
        ],
        scanner=ScannerStatus.from_node(xml("ScannerStatus.xml")),
        scanner_capabilities=ScannerCapabilities.from_node(
            xml("ScannerCapabilities.xml")
        ),
        ipp=IppStatus.from_attributes(
            {
                "printer-state": 3,
                "printer-state-reasons": "none",
                "printer-is-accepting-jobs": True,
                "queued-job-count": 0,
                "printer-up-time": 9074,
                "printer-wifi-ssid": "CASA_396_5G",
                "printer-wifi-state": 8,
                "operations-supported": [2, 4, 8, 10, 11, 60],
                "identify-actions-supported": ["flash", "pin"],
            }
        ),
        jobs=[],
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in every test."""


@pytest.fixture
def printer_data() -> PrinterData:
    """Fresh PrinterData per test."""
    return build_printer_data()


@pytest.fixture
def mock_client(printer_data: PrinterData) -> Generator[MagicMock]:
    """Patch HPPrinter in the integration and the config flow."""
    client = MagicMock()
    client.host = HOST
    client.password = None
    client.discover = AsyncMock(return_value=printer_data.capabilities)
    client.get_device_info = AsyncMock(return_value=printer_data.device)
    client.check_password = AsyncMock(return_value=True)
    client.update = AsyncMock(return_value=printer_data)
    client.scan = AsyncMock(return_value=[(FIXTURES / "scan_75dpi.jpg").read_bytes()])
    for name in (
        "identify",
        "cancel_job",
        "set_quiet_mode",
        "set_power_save_timeout",
        "set_auto_off_time",
        "set_device_language",
        "set_time_format",
        "set_date_format",
        "set_ews_enabled",
        "set_device_location",
        "set_device_description",
        "set_product_settings",
        "set_print_config",
        "set_copy_config",
        "set_network_services",
        "set_secure_network_services",
        "set_firmware_auto",
        "firmware_action",
        "print_internal_page",
        "clean_cartridges",
        "align_cartridges",
        "check_internet_connection",
        "restart",
        "print_data",
        "close",
    ):
        setattr(client, name, AsyncMock(return_value=None))

    def factory(host: str, **kwargs: object) -> MagicMock:
        client.host = host
        client.password = kwargs.get("password")
        return client

    with (
        patch("custom_components.hp_printer.HPPrinter", side_effect=factory) as cls,
        patch("custom_components.hp_printer.config_flow.HPPrinter", new=cls),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config entry for the DeskJet."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=UUID,
        data={CONF_HOST: HOST, CONF_PASSWORD: ""},
        options={},
        entry_id="01J0HPPRINTERENTRY00000001",
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and load it."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
