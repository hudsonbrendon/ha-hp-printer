# HP Printer for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Release](https://img.shields.io/github/v/release/hudsonbrendon/ha-hp-printer)](https://github.com/hudsonbrendon/ha-hp-printer/releases)
[![Tests](https://github.com/hudsonbrendon/ha-hp-printer/actions/workflows/tests.yml/badge.svg)](https://github.com/hudsonbrendon/ha-hp-printer/actions/workflows/tests.yml)
[![hassfest](https://github.com/hudsonbrendon/ha-hp-printer/actions/workflows/hassfest.yml/badge.svg)](https://github.com/hudsonbrendon/ha-hp-printer/actions/workflows/hassfest.yml)

<img src="assets/hp.png" alt="HP" width="96" align="right">

Local, cloud-free control of HP inkjet and laser printers. It talks every
protocol the printer exposes on your LAN — **LEDM** XML, **CDM** JSON (HP+
firmware), **eSCL** (AirScan) and **IPP** — through
[python-hp-printer](https://github.com/hudsonbrendon/python-hp-printer), and
turns all of it into Home Assistant entities and actions:

- **Status** as one enum sensor (`idle`, `printing`, `scanning`, `copying`,
  `sleeping`, `attention`, `error`...) plus problem / printing / scanning /
  sleeping / low-ink binary sensors and an **event entity** for job, scan,
  alert and power events.
- **Supplies**: level, raw level, cartridge state and estimated pages per
  cartridge (or toner / ink tank), with cartridge numbers (667 / 667XL...),
  genuine / refilled flags and the CSS colour used by the card.
- **Counters**: total / mono / colour / duplex pages, scans, copies, faxes,
  jams, mispicks, cancel presses, ink used, quiet-mode pages.
- **Scanner**: scanner state, **Scan** button and `hp_printer.scan` action
  (PDF or JPEG, flatbed or ADF), the result saved under
  `media/hp_printer/<serial>/` and shown in an **image entity**.
- **Jobs**: current job, last job, queued jobs, **Cancel current job**,
  `hp_printer.print_file` (print a JPEG/PDF from an allowed folder) and
  **Locate** (flashes the printer).
- **Settings** (need the EWS admin password on LEDM printers): quiet mode,
  sleep timeout, auto-off, panel language, time/date format, default print
  quality / resolution / copies, copy defaults, location, firmware auto
  check/update, AirPrint / IPPS / Bluetooth / Wi-Fi Direct / IPP / 9100 /
  SNMP / Bonjour / WS-* / LLMNR / Webscan switches.
- **Maintenance**: firmware **update entity** (check + install), clean
  cartridges, align cartridges, print status report / network summary /
  print quality diagnostic, internet connection test, restart.
- **Network**: Wi-Fi RSSI and bars, SSID, IP address, connectivity.
- Zeroconf (`_ipp`, `_ipps`, `_uscan`, `_printer`) and DHCP discovery,
  reauth, reconfigure, options, diagnostics, English and Brazilian Portuguese.

Pair it with [hp-printer-card](https://github.com/hudsonbrendon/hp-printer-card)
for an animated dashboard card.

## Supported printers

Tested on an **HP DeskJet Ink Advantage 2774** (DeskJet 2700 series). Any HP
printer that exposes `/DevMgmt/DiscoveryTree.xml` (DeskJet, ENVY, OfficeJet,
Smart Tank, LaserJet Pro from ~2010 on) gets the full LEDM feature set;
newer CDM-only HP+ models (Smart Tank 5xx, DeskJet 28xx/42xx, LaserJet
3xxx/4xxx) get status, supplies, counters, settings, firmware, media and
network through `/cdm/`. Scanning needs eSCL (every HP all-in-one since
~2012). Entities are only created for what your printer reports.

## Installation

1. HACS → Integrations → ⋮ → *Custom repositories* → add
   `https://github.com/hudsonbrendon/ha-hp-printer` as *Integration*.
2. Install **HP Printer** and restart Home Assistant.
3. The printer is discovered automatically (Settings → Devices & services).
   Otherwise *Add integration* → **HP Printer** → enter the IP.

### Admin password

Reads, scanning, printing and quiet mode (via CDM) work without credentials.
LEDM settings (sleep timeout, language, network services...) require the
printer's EWS admin password (user `admin`). On most models the default is
the PIN printed on the label inside the cartridge door; if HP Smart set a
password it is the one you chose in the app. Add it during setup or later via
*Reconfigure*. A rejected password starts a reauth flow.

## Options

| Option | Default | Description |
| --- | --- | --- |
| Polling interval | 30 s | Status, supplies, scanner and jobs. Counters, configuration and network every 10 polls. |
| Scan resolution / colour / format / source | 300 dpi, colour, PDF, flatbed | Defaults for the Scan button and `hp_printer.scan`; also exposed as selects. |
| Scan directory | `media/hp_printer/<serial>` | Where scans are written. |

## Actions

| Action | Fields | Response |
| --- | --- | --- |
| `hp_printer.scan` | `device_id`, `resolution`, `color_mode`, `format`, `source`, `filename` | `path`, `pages`, `content_type`, `size`, `scanned_at` |
| `hp_printer.print_file` | `device_id`, `path`, `format`, `copies` | `job_id`, `document_format` |
| `hp_printer.print_report` | `device_id`, `page` | — |
| `hp_printer.identify` | `device_id` | — |
| `hp_printer.cancel_job` | `device_id`, `job_id` (optional) | — |
| `hp_printer.clean_cartridges` | `device_id`, `level` | — |

Example — scan when a button is pressed and send the PDF to your phone:

```yaml
automation:
  - alias: Scan to phone
    triggers:
      - trigger: state
        entity_id: event.deskjet_2700_series_events
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'scan_completed' }}"
    actions:
      - action: notify.mobile_app_phone
        data:
          message: Scan ready
          data:
            attachment:
              url: "/media/local/hp_printer/br28bcb23h/{{ trigger.to_state.attributes.path | basename }}"
```

## Known limitations

- HP firmware only accepts LEDM writes over HTTPS with the admin password;
  without it the config entities raise "needs the printer admin password".
- `print_file` sends the file as-is. HP inkjets print JPEG, PCLm, URF and
  PWG raster natively; most do **not** rasterise PDF (LaserJets do).
- Printer events are detected by polling the LEDM event table; they arrive
  at most one polling interval late.
- The DeskJet 2700 has no ADF and no `WalkupScan` (scan-to-computer button)
  endpoints, so those paths are implemented from public dumps but untested.

## Troubleshooting

Enable debug logging under the integration's menu (it covers
`custom_components.hp_printer`, `hp_printer` and `pyipp`) and download the
diagnostics file — it contains every value parsed from the printer with
serial numbers, MACs and SSIDs redacted.

## Development

```bash
uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check .
```

Fixtures under `tests/fixtures/` are real dumps from the DeskJet 2774.

## License

MIT
