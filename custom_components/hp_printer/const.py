"""Constants for the HP Printer integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hp_printer"
MANUFACTURER: Final = "HP"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
]

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_SCAN_RESOLUTION: Final = "scan_resolution"
CONF_SCAN_COLOR_MODE: Final = "scan_color_mode"
CONF_SCAN_FORMAT: Final = "scan_format"
CONF_SCAN_SOURCE: Final = "scan_source"
CONF_SCAN_DIRECTORY: Final = "scan_directory"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600
# Static resources (usage counters, configuration, network) are refreshed
# every N polls; status, supplies, scanner and jobs on every poll.
STATIC_EVERY_POLLS: Final = 10
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

DEFAULT_SCAN_RESOLUTION: Final = 300
DEFAULT_SCAN_COLOR_MODE: Final = "RGB24"
DEFAULT_SCAN_FORMAT: Final = "application/pdf"
DEFAULT_SCAN_SOURCE: Final = "Platen"

SCAN_RESOLUTIONS: Final = (75, 100, 150, 200, 300, 600, 1200)
SCAN_COLOR_MODES: Final = ("RGB24", "Grayscale8", "BlackAndWhite1")
SCAN_FORMATS: Final = ("application/pdf", "image/jpeg")
SCAN_SOURCES: Final = ("Platen", "Feeder")

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_DEVICE_ID: Final = "device_id"
ATTR_RESOLUTION: Final = "resolution"
ATTR_COLOR_MODE: Final = "color_mode"
ATTR_FORMAT: Final = "format"
ATTR_SOURCE: Final = "source"
ATTR_FILENAME: Final = "filename"
ATTR_PAGE: Final = "page"
ATTR_JOB_ID: Final = "job_id"
ATTR_COPIES: Final = "copies"
ATTR_PATH: Final = "path"
ATTR_ACTION: Final = "action"
ATTR_LEVEL: Final = "level"

SERVICE_SCAN: Final = "scan"
SERVICE_PRINT_FILE: Final = "print_file"
SERVICE_PRINT_REPORT: Final = "print_report"
SERVICE_IDENTIFY: Final = "identify"
SERVICE_CANCEL_JOB: Final = "cancel_job"
SERVICE_CLEAN_CARTRIDGES: Final = "clean_cartridges"

SIGNAL_EVENT: Final = f"{DOMAIN}_event"
SIGNAL_SCAN_DONE: Final = f"{DOMAIN}_scan_done"

# Event entity types (LEDM EventMgmt categories + integration events).
EVENT_TYPES: Final = (
    "alert_table_changed",
    "job_event",
    "power_up",
    "powering_down",
    "scan_event",
    "consumable_event",
    "device_capabilities_changed",
    "oobe_status_changed",
    "scan_completed",
    "print_job_started",
    "print_job_completed",
)

LEDM_EVENT_MAP: Final = {
    "AlertTableChanged": "alert_table_changed",
    "JobEvent": "job_event",
    "PowerUpEvent": "power_up",
    "PoweringDownEvent": "powering_down",
    "ScanEvent": "scan_event",
    "ConsumableEvent": "consumable_event",
    "DeviceCapabilitiesChanged": "device_capabilities_changed",
    "OOBEStatusChanged": "oobe_status_changed",
}

# Internal pages exposed as buttons (job type -> translation key).
REPORT_BUTTONS: Final = {
    "configurationPage": "print_configuration_page",
    "networkSummary": "print_network_summary",
    "pqDiagnosticsPage": "print_quality_report",
    "wirelessNetworkPage": "print_wireless_test",
}

MEDIA_SUBDIR: Final = "hp_printer"
