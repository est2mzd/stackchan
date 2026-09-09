#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import errno
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clock_format import clock_message
from defaults import WS_PORT

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None

try:
    import websockets
except ImportError:
    websockets = None


def open_serial(port: str):
    ser = serial_mod.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


async def drain_serial(ser) -> None:
    buf = b""
    while True:
        chunk = await asyncio.to_thread(ser.read, 4096)
        if not chunk:
            await asyncio.sleep(0.02)
            continue
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                print(text, flush=True)


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
        ser = open_serial(serial_port)
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

    drain_task = None
    if ser is not None:
        drain_task = asyncio.create_task(drain_serial(ser))

    async def tick() -> None:
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
                    await asyncio.to_thread(ser.write, payload.encode("utf-8"))
                    ser.flush()
                except Exception as exc:
                    print(f"serial write failed: {exc}", flush=True)
            await asyncio.sleep(1)

    try:
        if ws_port <= 0:
            print("websocket disabled", flush=True)
            await tick()
            return
        async with websockets.serve(handler, ws_host, ws_port):
            print(f"websocket ws://{ws_host}:{ws_port}{ws_path}", flush=True)
            await tick()
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"port {ws_port} already in use ({ws_host}:{ws_port}). "
                f"別のポートで起動する: --ws-port {ws_port + 1} （0 で WebSocket なし）"
            ) from exc
        raise
    finally:
        if drain_task is not None:
            drain_task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="StackChan clock host")
    parser.add_argument("--weekday", choices=("en", "ja"), default="en")
    parser.add_argument("--tz", default="Asia/Tokyo")
    parser.add_argument("--serial", default="")
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=WS_PORT)
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
