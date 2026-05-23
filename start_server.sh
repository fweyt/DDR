#!/bin/bash
# start_server.sh — start de AI-hulpservice
cd "$(dirname "$0")"
.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 5000 --reload
