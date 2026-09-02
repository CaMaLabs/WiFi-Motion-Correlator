#!/usr/bin/env python3
"""Read newline-delimited JSON metadata from stdin and forward Wi-Fi observations.
Expected fields: mac/device_id, rssi, channel, optional ts/sensor.
Use this adapter with a Kismet export/plugin you control; it never captures payloads.
"""
import json, os, sys, urllib.request
URL=os.getenv('WMC_WIFI_URL','http://127.0.0.1:8787/api/wifi')
for line in sys.stdin:
    try:
        d=json.loads(line)
        raw=json.dumps(d).encode()
        req=urllib.request.Request(URL,data=raw,headers={'Content-Type':'application/json'},method='POST')
        urllib.request.urlopen(req,timeout=2).read()
    except Exception as e:
        print(f'wmc adapter: {e}',file=sys.stderr)
