"""Actions: scan, print_file, print_report, identify, cancel_job, clean + image/diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from hp_printer import HPPrinterScanError
from hp_printer.models import IppJob
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hp_printer.const import DOMAIN
from custom_components.hp_printer.diagnostics import async_get_config_entry_diagnostics

from .conftest import UUID, setup_integration

P = "deskjet_2700_series"


async def _device_id(hass: HomeAssistant, entry_id: str) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, UUID), entry_id)
    assert device is not None
    return device.id


async def test_scan_action_saves_file_and_updates_image(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
    hass_client,
) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}
    await setup_integration(hass, mock_config_entry)
    device_id = await _device_id(hass, mock_config_entry.entry_id)
    response = await hass.services.async_call(
        DOMAIN,
        "scan",
        {
            "device_id": device_id,
            "resolution": 75,
            "format": "image/jpeg",
            "filename": "test doc",
        },
        blocking=True,
        return_response=True,
    )
    settings = mock_client.scan.await_args.args[0]
    assert settings.resolution == 75 and settings.document_format == "image/jpeg"
    assert settings.color_mode == "RGB24"  # default from options
    saved = Path(response["path"])
    assert saved.exists() and saved.name == "test_doc.jpg"
    assert saved.parent == tmp_path / "hp_printer" / "br28bcb23h"
    assert response["pages"] == 1 and response["content_type"] == "image/jpeg"

    assert hass.states.get(f"sensor.{P}_last_scan").state != "unknown"
    event = hass.states.get(f"event.{P}_events")
    assert event.attributes["event_type"] == "scan_completed"

    image = hass.states.get(f"image.{P}_last_scan")
    assert image is not None and image.state != "unknown"
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/image.{P}_last_scan")
    assert resp.status == 200
    assert resp.content_type == "image/jpeg"
    assert (await resp.read())[:2] == b"\xff\xd8"

    # scan button uses the same path
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: f"button.{P}_scan"}, blocking=True
    )
    assert mock_client.scan.await_count == 2

    mock_client.scan.side_effect = HPPrinterScanError("busy")
    with pytest.raises(HomeAssistantError, match="Scan failed"):
        await hass.services.async_call(
            DOMAIN, "scan", {"device_id": device_id}, blocking=True
        )


async def test_scan_multi_page(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}
    await setup_integration(hass, mock_config_entry)
    mock_client.scan.return_value = [b"\xff\xd8a", b"\xff\xd8b"]
    response = await hass.services.async_call(
        DOMAIN,
        "scan",
        {
            "device_id": await _device_id(hass, mock_config_entry.entry_id),
            "source": "Feeder",
            "format": "image/jpeg",
        },
        blocking=True,
        return_response=True,
    )
    assert response["pages"] == 2
    first = Path(response["path"])
    assert first.name.endswith("_1.jpg")
    assert first.with_name(first.name.replace("_1.jpg", "_2.jpg")).exists()


async def test_print_file_action(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    await setup_integration(hass, mock_config_entry)
    device_id = await _device_id(hass, mock_config_entry.entry_id)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    with pytest.raises(ServiceValidationError, match="not inside"):
        await hass.services.async_call(
            DOMAIN,
            "print_file",
            {"device_id": device_id, "path": str(photo)},
            blocking=True,
        )
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await hass.services.async_call(
            DOMAIN,
            "print_file",
            {"device_id": device_id, "path": str(tmp_path / "missing.jpg")},
            blocking=True,
        )
    mock_client.print_data.return_value = IppJob(id=12, state="pending")
    response = await hass.services.async_call(
        DOMAIN,
        "print_file",
        {"device_id": device_id, "path": str(photo), "copies": 2},
        blocking=True,
        return_response=True,
    )
    assert response == {"job_id": 12, "document_format": "image/jpeg"}
    kwargs = mock_client.print_data.await_args.kwargs
    assert kwargs["document_format"] == "image/jpeg" and kwargs["copies"] == 2
    assert kwargs["job_name"] == "photo.jpg"


async def test_other_actions(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    device_id = await _device_id(hass, mock_config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "identify", {"device_id": device_id}, blocking=True
    )
    mock_client.identify.assert_awaited()
    await hass.services.async_call(
        DOMAIN,
        "print_report",
        {"device_id": device_id, "page": "networkSummary"},
        blocking=True,
    )
    mock_client.print_internal_page.assert_awaited_with("networkSummary")
    await hass.services.async_call(
        DOMAIN, "clean_cartridges", {"device_id": device_id, "level": 2}, blocking=True
    )
    mock_client.clean_cartridges.assert_awaited_with(2)
    await hass.services.async_call(
        DOMAIN, "cancel_job", {"device_id": device_id, "job_id": 5}, blocking=True
    )
    mock_client.cancel_job.assert_awaited_with(5)
    with pytest.raises(HomeAssistantError, match="no active"):
        await hass.services.async_call(
            DOMAIN, "cancel_job", {"device_id": device_id}, blocking=True
        )
    with pytest.raises(ServiceValidationError, match="No HP printer"):
        await hass.services.async_call(
            DOMAIN, "identify", {"device_id": "does-not-exist"}, blocking=True
        )


async def test_diagnostics_redacts(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["data"]["device"]["serial_number"] == "**REDACTED**"
    assert diagnostics["data"]["device"]["model_family"] == "DeskJet 2700 series"
    assert diagnostics["data"]["network"]["adapters"][0]["mac"] == "**REDACTED**"
    assert diagnostics["capabilities"]["has_escl"] is True
    assert diagnostics["last_scan"] is None
