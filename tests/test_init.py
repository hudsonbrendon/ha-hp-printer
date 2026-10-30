"""Setup, unload, device registration and availability."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from hp_printer import HPPrinterConnectionError, HPPrinterNotSupportedError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hp_printer.const import DOMAIN

from .conftest import UUID, setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.discover.assert_awaited_once()
    mock_client.update.assert_awaited()

    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (DOMAIN, UUID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "HP"
    assert device.model == "DeskJet 2700 series"
    assert device.serial_number == "BR28BCB23H"
    assert device.sw_version == "TWP1FN2550DR"
    assert (dr.CONNECTION_NETWORK_MAC, "5c:60:ba:50:24:72") in device.connections
    assert device.configuration_url == "http://192.168.31.12/"

    state = hass.states.get("sensor.deskjet_2700_series_status")
    assert state is not None and state.state == "sleeping"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_offline(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    mock_client.discover.side_effect = HPPrinterConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_on_unsupported_device(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    mock_client.discover.side_effect = HPPrinterNotSupportedError("nope")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entities_unavailable_then_recover(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup_integration(hass, mock_config_entry)
    data = mock_client.update.return_value
    mock_client.update.side_effect = HPPrinterConnectionError("timeout")
    # two failures are tolerated (printer busy while printing/scanning)
    for _ in range(2):
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.deskjet_2700_series_status").state == "sleeping"
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.deskjet_2700_series_status").state == STATE_UNAVAILABLE
    )

    mock_client.update.side_effect = None
    mock_client.update.return_value = data
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.deskjet_2700_series_status").state == "sleeping"


async def test_static_data_polled_every_tenth_update(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup_integration(hass, mock_config_entry)
    first_call = mock_client.update.await_args_list[0]
    assert first_call.kwargs["include_static"] is True
    for _ in range(3):
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert mock_client.update.await_args_list[1].kwargs["include_static"] is False
    assert mock_client.update.await_args_list[1].kwargs["previous"] is not None


async def test_remove_device_only_when_stale(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    from custom_components.hp_printer import async_remove_config_entry_device

    await setup_integration(hass, mock_config_entry)
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (DOMAIN, UUID), mock_config_entry.entry_id
    )
    assert device is not None
    assert not await async_remove_config_entry_device(hass, mock_config_entry, device)
    stale = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "old")}
    )
    assert await async_remove_config_entry_device(hass, mock_config_entry, stale)
