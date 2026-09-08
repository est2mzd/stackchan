#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clock_format import clock_message

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None

try:
    import websockets
except ImportError:
    websockets = None


async def broadcast_loop(
    weekday_lang: str,
    tz_name: str,
    serial_port: str | None,
    ws_host: str,
    ws_port: int,
    ws_path: str,
) -> None:
    if websockets is None:
        raise SystemExit("websockets is required")

    tz = ZoneInfo(tz_name)
    connected: set = set()
    ser = None
    if serial_port:
        if serial_mod is None:
            raise SystemExit("pyserial is required for --serial")
        ser = serial_mod.Serial(serial_port, 115200, timeout=0.1)
        ser.dtr = False
        ser.rts = False
        print(f"serial opened {serial_port}", flush=True)
        await asyncio.sleep(3)

    async def handler(websocket) -> None:
        path = ""
        request = getattr(websocket, "request", None)
        if request is not None:
            path = getattr(request, "path", "") or ""
        elif hasattr(websocket, "path"):
            path = websocket.path or ""
        if path not in ("", ws_path):
            await websocket.close()
            return
        connected.add(websocket)
        print(f"ws client {websocket.remote_address} path={path}", flush=True)
        try:
            await websocket.wait_closed()
        finally:
            connected.discard(websocket)
            print("ws client disconnected", flush=True)

    async with websockets.serve(handler, ws_host, ws_port):
        print(f"websocket ws://{ws_host}:{ws_port}{ws_path}", flush=True)
        while True:
            now = datetime.now(tz).replace(tzinfo=None)
            payload = json.dumps(clock_message(now, weekday_lang), ensure_ascii=False) + "\n"
            dead = []
            for ws in list(connected):
                try:
                    await ws.send(payload.strip())
                except Exception:
                    dead.append(ws)
            for ws in dead:
                connected.discard(ws)
            if ser is not None:
                try:
                    ser.write(payload.encode("utf-8"))
                except Exception as exc:
                    print(f"serial write failed: {exc}", flush=True)
            await asyncio.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="StackChan clock host")
    parser.add_argument("--weekday", choices=("en", "ja"), default="en")
    parser.add_argument("--tz", default="Asia/Tokyo")
    parser.add_argument("--serial", default="")
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8000)
    parser.add_argument("--ws-path", default="/ws/stackchan")
    args = parser.parse_args()
    asyncio.run(
        broadcast_loop(
            weekday_lang=args.weekday,
            tz_name=args.tz,
            serial_port=args.serial or None,
            ws_host=args.ws_host,
            ws_port=args.ws_port,
            ws_path=args.ws_path,
        )
    )


if __name__ == "__main__":
    main()
