#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asr import NullAsr, WhisperAsr
from calendar_google import load_events
from calendar_notify import CalendarEvent, due_notifications, spoken_alert
from clock_format import clock_message
from intent import route_utterance
from llm import complete
from tts import synth_edge, synth_none

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None

try:
    import websockets
except ImportError:
    websockets = None


def b64pcm(pcm: bytes) -> str:
    return base64.b64encode(pcm).decode("ascii")


class StackchanHost:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tz = ZoneInfo(args.tz)
        self.mode = "clock"
        self.pcm_buf = bytearray()
        self.sent_events: set[str] = set()
        self.ser = None
        self.ws_clients: set = set()
        self.asr = NullAsr() if args.asr == "none" else WhisperAsr(args.whisper_model)
        self.synth = synth_none if args.tts == "none" else synth_edge
        self.demo_events: list[CalendarEvent] = []
        if args.calendar_demo_in_sec > 0:
            start = datetime.now(self.tz).replace(tzinfo=None) + timedelta(
                seconds=args.calendar_demo_in_sec
            )
            self.demo_events.append(CalendarEvent("demo", args.calendar_demo_title, start))

    def now(self) -> datetime:
        return datetime.now(self.tz).replace(tzinfo=None)

    async def broadcast(self, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        if self.ser is not None:
            await asyncio.to_thread(self.ser.write, line.encode("utf-8"))
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send(line.strip())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    async def send_clock(self, extra: str | None = None) -> None:
        msg = clock_message(self.now(), self.args.weekday)
        if extra:
            await self.broadcast({"type": "alert", "lines": msg["lines"] + [extra]})
        else:
            await self.broadcast(msg)

    async def speak(self, text: str) -> None:
        if not text:
            return
        pcm = await self.synth(text)
        if not pcm:
            return
        await self.broadcast({"type": "speak_start"})
        chunk = 1024
        for i in range(0, len(pcm), chunk):
            await self.broadcast({"type": "pcm", "data": b64pcm(pcm[i : i + chunk])})
            await asyncio.sleep(0.01)
        await self.broadcast({"type": "speak_end"})
        await asyncio.sleep(0.2)

    async def enter_clock(self) -> None:
        self.mode = "clock"
        await self.broadcast({"type": "idle"})
        await self.send_clock()

    async def enter_chat(self, status: str = "話してください") -> None:
        self.mode = "chat"
        await self.broadcast({"type": "status", "text": status})
        await self.broadcast({"type": "listen"})

    async def handle_text(self, text: str) -> None:
        if not text:
            if self.mode == "chat":
                await self.broadcast({"type": "listen"})
            return
        kind = route_utterance(text)
        if kind == "clock":
            await self.enter_clock()
            return
        if kind == "chat":
            await self.enter_chat()
            return
        if self.mode != "chat":
            return
        await self.broadcast({"type": "chat", "lines": [text, "考え中"]})
        try:
            reply = await complete(
                text,
                self.args.llm,
                self.args.llm_model,
                self.args.llm_base_url,
                os.environ.get("OPENAI_API_KEY", ""),
            )
        except Exception as exc:
            reply = f"LLMエラー: {exc}"
        await self.broadcast({"type": "chat", "lines": [text, reply]})
        await self.speak(reply)
        await self.broadcast({"type": "listen"})

    async def on_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        if line in ("CLOCK_APPLIED", "CLOCK_TIMEOUT", "CLOCK_FW_READY", "SPEAK_DONE"):
            print(line, flush=True)
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            print("serial", line[:120], flush=True)
            return
        typ = msg.get("type")
        if typ == "pcm":
            raw = base64.b64decode(msg.get("data") or "")
            self.pcm_buf.extend(raw)
            return
        if typ == "pcm_start":
            self.pcm_buf = bytearray()
            return
        if typ == "pcm_end":
            pcm = bytes(self.pcm_buf)
            self.pcm_buf = bytearray()
            print(f"pcm_end bytes={len(pcm)} reason={msg.get('reason')}", flush=True)
            text = await asyncio.to_thread(self.asr.transcribe, pcm)
            print(f"asr {text!r}", flush=True)
            await self.handle_text(text)
            return
        if typ == "touch":
            print("touch", flush=True)
            if self.mode == "clock":
                await self.enter_chat()
            else:
                await self.enter_clock()

    async def serial_reader(self) -> None:
        buf = b""
        while True:
            chunk = await asyncio.to_thread(self.ser.read, 4096)
            if not chunk:
                await asyncio.sleep(0.02)
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                await self.on_line(line.decode("utf-8", errors="replace"))

    async def calendar_loop(self) -> None:
        cred = Path(self.args.calendar_credentials)
        token = Path(self.args.calendar_token)
        while True:
            events = list(self.demo_events)
            if cred.exists():
                try:
                    events.extend(
                        await asyncio.to_thread(
                            load_events, cred, token, self.args.tz, self.now()
                        )
                    )
                except Exception as exc:
                    print(f"calendar fetch failed: {exc}", flush=True)
            due = due_notifications(
                events, self.now(), self.args.notify_minutes, self.sent_events
            )
            for event in due:
                self.sent_events.add(event.event_id)
                spoken = spoken_alert(event, self.args.notify_minutes)
                print(f"calendar {spoken}", flush=True)
                await self.send_clock(extra=event.title)
                await self.speak(spoken)
                self.mode = "clock"
            await asyncio.sleep(5)

    async def tick_loop(self) -> None:
        while True:
            if self.mode == "clock":
                extra = None
                if self.demo_events:
                    due = due_notifications(
                        self.demo_events, self.now(), self.args.notify_minutes, set()
                    )
                    if due:
                        extra = due[0].title
                await self.send_clock(extra=extra)
            else:
                await self.broadcast({"type": "hb"})
            await asyncio.sleep(1)

    async def run(self) -> None:
        if websockets is None:
            raise SystemExit("websockets is required")
        if self.args.serial:
            if serial_mod is None:
                raise SystemExit("pyserial is required")
            self.ser = serial_mod.Serial(self.args.serial, 115200, timeout=0.2)
            self.ser.dtr = False
            self.ser.rts = False
            print(f"serial opened {self.args.serial}", flush=True)
            await asyncio.sleep(3)

        async def ws_handler(websocket) -> None:
            self.ws_clients.add(websocket)
            try:
                async for _incoming in websocket:
                    pass
            finally:
                self.ws_clients.discard(websocket)

        async with websockets.serve(ws_handler, self.args.ws_host, self.args.ws_port):
            print(f"websocket ws://{self.args.ws_host}:{self.args.ws_port}", flush=True)
            tasks = [asyncio.create_task(self.tick_loop()), asyncio.create_task(self.calendar_loop())]
            if self.ser is not None:
                tasks.append(asyncio.create_task(self.serial_reader()))
            await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="StackChan host (clock, talk, calendar)")
    parser.add_argument("--weekday", choices=("en", "ja"), default="en")
    parser.add_argument("--tz", default="Asia/Tokyo")
    parser.add_argument("--serial", default="")
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8000)
    parser.add_argument("--asr", choices=("whisper", "none"), default="whisper")
    parser.add_argument("--whisper-model", default="base")
    parser.add_argument("--tts", choices=("edge", "none"), default="edge")
    parser.add_argument("--llm", choices=("echo", "ollama", "openai"), default="echo")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--notify-minutes", type=int, default=10)
    parser.add_argument("--calendar-credentials", default="host/google_credentials.json")
    parser.add_argument("--calendar-token", default="host/google_token.json")
    parser.add_argument("--calendar-demo-in-sec", type=int, default=0)
    parser.add_argument("--calendar-demo-title", default="デモ予定")
    args = parser.parse_args()
    asyncio.run(StackchanHost(args).run())


if __name__ == "__main__":
    main()
