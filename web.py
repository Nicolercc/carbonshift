#!/usr/bin/env python3
"""
CarbonShift web interface.

Usage:
  python web.py              # runs on http://localhost:5050
  python web.py --port 8080
  python web.py --host 0.0.0.0 --port 8080   # LAN-accessible

Note: default port is 5050. Port 5000 is taken by macOS AirPlay Receiver on
Monterey and later (binds to *:5000 including IPv6, so localhost:5000 hits
AirPlay, not Flask). Port 5050 avoids that conflict and is reserved for this
project to avoid clashing with other local dev servers.
"""

import argparse

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import init_db
from src.web.app import app

init_db()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CarbonShift web server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Port (default: 5050)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    print(f"CarbonShift web interface → http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
