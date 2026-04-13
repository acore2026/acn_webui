#!/bin/bash
cd /root/lpx/webui/backend
source /root/lpx/acn_gw/venv/bin/activate
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9050
