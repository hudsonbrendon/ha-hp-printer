"""Entity states and writes across platforms."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from hp_printer import HPPrinterAuthenticationError, HPPrinterNotSupportedError
from hp_printer.models import IppJob
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .conftest import setup_integration

P = "deskjet_2700_series"


async def test_sensor_states(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    status = hass.states.get(f"sensor.{P}_status")
    assert status is not None and status.state == "sleeping"
    assert status.attributes["categories"] == ["genuineHP", "inPowerSave"]
    assert status.attributes["problems"] == []
    assert hass.states.get(f"sensor.{P}_tri_color_ink").state == "90"
    black = hass.states.get(f"sensor.{P}_black_ink")
    assert black.state == "70"
    assert black.attributes["cartridge_number"] == "667"
    assert black.attributes["compatible_numbers"] == ["667XL", "667"]
    assert black.attributes["genuine_hp"] is True
    assert hass.states.get(f"sensor.{P}_black_cartridge_state").state == "newGenuineHP"
    assert hass.states.get(f"sensor.{P}_total_pages").state == "66"
    assert hass.states.get(f"sensor.{P}_scanned_pages").state == "5"
    assert hass.states.get(f"sensor.{P}_copied_pages").state == "3"
    assert hass.states.get(f"sensor.{P}_paper_jams").state == "0"
    assert hass.states.get(f"sensor.{P}_ink_used").state == "3.0"
    assert hass.states.get(f"sensor.{P}_wi_fi_signal").state == "-49"
    assert hass.states.get(f"sensor.{P}_wi_fi_network").state == "CASA_396_5G"
    assert hass.states.get(f"sensor.{P}_ip_address").state == "192.168.31.12"
    assert hass.states.get(f"sensor.{P}_paper_size").state == "iso_a4_210x297mm"
    assert hass.states.get(f"sensor.{P}_scanner").state == "idle"
    assert hass.states.get(f"sensor.{P}_current_job").state == "unknown"
    assert hass.states.get(f"sensor.{P}_queued_jobs").state == "0"
    assert hass.states.get(f"sensor.{P}_last_scan").state == "unknown"
    # monochrome/colour impressions are not reported by this model
    assert hass.states.get(f"sensor.{P}_monochrome_pages") is None
    # disabled by default
    registry = er.async_get(hass)
    entry = registry.async_get(f"sensor.{P}_black_ink_raw_level")
    assert (
        entry is not None and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_binary_sensors_and_update(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(f"binary_sensor.{P}_problem").state == STATE_OFF
    assert hass.states.get(f"binary_sensor.{P}_printing").state == STATE_OFF
    assert hass.states.get(f"binary_sensor.{P}_scanning").state == STATE_OFF
    assert hass.states.get(f"binary_sensor.{P}_sleeping").state == STATE_ON
    assert hass.states.get(f"binary_sensor.{P}_low_ink").state == STATE_OFF
    assert hass.states.get(f"binary_sensor.{P}_wi_fi_connected").state == STATE_ON
    assert hass.states.get(f"binary_sensor.{P}_alignment_required").state == STATE_ON
    update = hass.states.get(f"update.{P}_firmware")
    assert update.state == STATE_OFF
    assert update.attributes["installed_version"] == "TWP1FN2550DR"
    assert update.attributes["latest_version"] == "TWP1FN2550DR"
    assert hass.states.get(f"event.{P}_events") is not None


async def test_printing_state_from_jobs(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup_integration(hass, mock_config_entry)
    data = mock_client.update.return_value
    data.status.categories = ["processing"]
    data.jobs = [IppJob(id=7, name="report.pdf", state="processing", impressions=3)]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{P}_status").state == "printing"
    assert hass.states.get(f"binary_sensor.{P}_printing").state == STATE_ON
    job = hass.states.get(f"sensor.{P}_current_job")
    assert job.state == "report.pdf" and job.attributes["job_id"] == 7
    # job finishes -> event entity fires print_job_completed
    data.status.categories = ["ready"]
    data.jobs = [IppJob(id=7, name="report.pdf", state="completed")]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    event = hass.states.get(f"event.{P}_events")
    assert event.attributes["event_type"] == "print_job_completed"
    assert event.attributes["job_id"] == 7
    # cancel current job -> no active job error
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: f"button.{P}_cancel_current_job"},
            blocking=True,
        )


async def test_switch_select_number_text_writes(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(f"switch.{P}_quiet_mode").state == STATE_OFF
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: f"switch.{P}_quiet_mode"}, blocking=True
    )
    mock_client.set_quiet_mode.assert_awaited_with(True)
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: f"switch.{P}_quiet_mode"}, blocking=True
    )
    mock_client.set_quiet_mode.assert_awaited_with(False)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: f"switch.{P}_automatic_firmware_update"},
        blocking=True,
    )
    mock_client.set_firmware_auto.assert_awaited_with(update=False)

    sleep = hass.states.get(f"select.{P}_sleep_after")
    assert sleep.state == "5minutes"
    assert sleep.attributes["options"] == ["5minutes", "10minutes", "15minutes"]
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: f"select.{P}_sleep_after", "option": "15minutes"},
        blocking=True,
    )
    mock_client.set_power_save_timeout.assert_awaited_with("15minutes")
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: f"select.{P}_default_print_quality", "option": "Best"},
        blocking=True,
    )
    mock_client.set_print_config.assert_awaited_with(quality="Best")

    assert hass.states.get(f"number.{P}_default_copies").state == "1"
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: f"number.{P}_default_copies", "value": 3},
        blocking=True,
    )
    mock_client.set_print_config.assert_awaited_with(copies=3)

    # scan defaults live in the entry options, not on the printer
    scan_res = hass.states.get(f"select.{P}_scan_resolution")
    assert scan_res.state == "300"
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: f"select.{P}_scan_resolution", "option": "600"},
        blocking=True,
    )
    assert mock_config_entry.options["scan_resolution"] == 600
    assert hass.states.get(f"select.{P}_scan_resolution").state == "600"


async def test_write_errors_are_translated(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    mock_client.set_power_save_timeout.side_effect = HPPrinterAuthenticationError("401")
    with pytest.raises(HomeAssistantError, match="admin password"):
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: f"select.{P}_sleep_after", "option": "10minutes"},
            blocking=True,
        )
    mock_client.identify.side_effect = HPPrinterNotSupportedError("405")
    with pytest.raises(HomeAssistantError, match="does not support"):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: f"button.{P}_locate"}, blocking=True
        )


async def test_buttons(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    for entity, mock, args in (
        (f"button.{P}_locate", mock_client.identify, ()),
        (
            f"button.{P}_check_for_firmware_update",
            mock_client.firmware_action,
            ("check",),
        ),
        (f"button.{P}_clean_cartridges", mock_client.clean_cartridges, (1,)),
        (f"button.{P}_align_cartridges", mock_client.align_cartridges, ()),
        (
            f"button.{P}_print_status_report",
            mock_client.print_internal_page,
            ("configurationPage",),
        ),
    ):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: entity}, blocking=True
        )
        mock.assert_awaited_with(*args)
