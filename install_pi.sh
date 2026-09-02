#!/usr/bin/env bash
set -euo pipefail
sudo mkdir -p /opt/wifi-motion-correlator
sudo cp -r app requirements.txt kismet_tail.py /opt/wifi-motion-correlator/
sudo python3 -m venv /opt/wifi-motion-correlator/.venv
sudo /opt/wifi-motion-correlator/.venv/bin/pip install -r /opt/wifi-motion-correlator/requirements.txt
KEY=$(python3 - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
)
echo "WMC_HASH_KEY=$KEY" | sudo tee /etc/default/wifi-motion-correlator >/dev/null
sudo cp systemd/wifi-motion-correlator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-motion-correlator
printf 'Dashboard: http://<pi-ip>:8787\n'
