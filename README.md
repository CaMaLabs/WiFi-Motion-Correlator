# WiFi Motion Correlator

Raspberry Pi companion service for correlating **camera/NVR motion events** with **passive Wi-Fi metadata observations** on networks and property you are authorized to monitor.

This module intentionally stores no packet payloads and HMAC-hashes device identifiers before they enter SQLite. A correlation means only that a radio observation occurred near the same time as a camera event; it does **not** establish a person's identity.

## Why this structure

Use an existing RF collector such as Passive-Vigilance/Kismet for monitor-mode capture, and keep camera/event correlation separate. This avoids duplicating mature RF collection code and makes camera integrations easy to swap.

## Install on Raspberry Pi

```bash
sudo apt install -y python3-venv
./install_pi.sh
```

Dashboard: `http://PI_IP:8787`

## Camera motion webhook

POST JSON to `/api/motion`:

```json
{"camera":"driveway","zone":"gate","event_type":"person","confidence":0.94}
```

Optional `ts` is Unix epoch seconds. If omitted, arrival time is used.

Example:

```bash
curl -X POST http://PI_IP:8787/api/motion -H 'Content-Type: application/json' \
  -d '{"camera":"driveway","zone":"gate","event_type":"motion"}'
```

## Wi-Fi metadata input

POST metadata to `/api/wifi`:

```json
{"mac":"aa:bb:cc:dd:ee:ff","rssi":-52,"channel":36,"sensor":"front-pi","source":"kismet"}
```

The raw MAC/device identifier is immediately converted to a keyed HMAC and is never stored.

`kismet_tail.py` accepts newline-delimited JSON on stdin and forwards it to `/api/wifi`; wire it to a Kismet metadata export or plugin rather than packet payload output.

## Correlation

Default window: ±20 seconds (`WMC_CORRELATION_WINDOW_SEC`). Each camera event is associated with Wi-Fi observations in that window and assigned a simple time/RSSI score. The dashboard shows event counts; `/api/event/<id>` shows anonymous correlated radio observations.

## Next integrations

- Passive-Vigilance/Kismet event adapter
- Frigate webhook/MQTT bridge
- Blue Iris alert bridge
- UniFi Protect event bridge
- optional Nexmon CSI motion-score input as a *motion sensor*, separate from device identity
- zone-specific sensors and per-sensor baselines
