# Changelog

## 0.1.0 - 2026-10-30

First release.

- Config flow with manual setup, zeroconf (`_ipp`, `_ipps`, `_uscan`,
  `_printer`) and DHCP discovery, reauth, reconfigure and options.
- Sensors: status enum, per-cartridge level / raw level / state / pages
  remaining, page counters (total, mono, colour, duplex, scans, copies, fax),
  jams, mispicks, cancel presses, ink used, Wi-Fi RSSI / bars / SSID, IP,
  last boot, paper size/type, scanner state, current/last/queued jobs,
  alignment state, HP web services, last event code, last scan.
- Binary sensors: problem, attention, printing, scanning, sleeping, low ink,
  paper loaded, firmware update available, Wi-Fi connected, HP web services,
  accepting jobs, alignment required.
- Switches: quiet mode, firmware auto check/update, power save, EWS,
  AirPrint, IPPS, Bluetooth, remote scans, Wi-Fi Direct, IPP, 9100, SNMP,
  Bonjour, WS-Discovery/Print/Scan, LLMNR, Webscan.
- Selects: sleep timeout, auto-off, language, time/date format, print
  quality/resolution, copy quality/colour/paper size, scan defaults.
- Numbers: default copies, job timeout, copy count, copy darkness.
- Buttons: locate, scan, cancel job, check firmware, clean/align cartridges,
  internet check, restart, status report, network summary, print quality
  diagnostic, wireless test.
- Update entity for the firmware, image entity for the last scan, event
  entity for printer/job/scan events, text entities for location/description.
- Actions: `scan`, `print_file`, `print_report`, `identify`, `cancel_job`,
  `clean_cartridges`.
- Diagnostics, icons, English and Brazilian Portuguese translations.
