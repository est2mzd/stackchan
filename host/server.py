#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import errno
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asr import NullAsr, WhisperAsr, pcm_mean_abs
from calendar_google import load_events
from calendar_notify import CalendarEvent, due_notifications, spoken_alert
from chatfmt import chat_screen, clip_line, thinking_placeholder
from clock_format import clock_message
from defaults import WS_PORT
from envfile import load_env_file
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


def ws_in_use_exit(host: str, port: int) -> None:
    raise SystemExit(
        f"port {port} already in use ({host}:{port}). "
        f"別のポートで起動する: --ws-port {port + 1} （0 で WebSocket なし）"
    )


class StackchanHost:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tz = ZoneInfo(args.tz)
        self.mode = "clock"
        self.pcm_buf = bytearray()
        self.sent_events: set[str] = set()
        self.ser = None
        self.ws_clients: set = set()
        self.io = asyncio.Lock()
        self.busy = False
        self.speak_done = asyncio.Event()
        self.sending_audio = False
        self.pcm_expect = 0
        self.pcm_wait = 0.0
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
        async with self.io:
            if self.ser is not None:
                self._write_serial(line)
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send(line.strip())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    def _write_serial(self, line: str) -> None:
        self.ser.write(line.encode("utf-8"))
        self.ser.flush()

    async def send_clock(self, extra: str | None = None) -> None:
        msg = clock_message(self.now(), self.args.weekday)
        if extra:
            await self.broadcast({"type": "alert", "lines": msg["lines"] + [extra]})
        else:
            await self.broadcast(msg)

    def _write_raw(self, data: bytes, flush: bool = True) -> None:
        self.ser.write(data)
        if flush:
            self.ser.flush()

    async def speak(self, text: str) -> None:
        if not text:
            return
        pcm = await self.synth(text)
        if not pcm:
            print("tts empty", flush=True)
            return
        if len(pcm) % 2:
            pcm = pcm[:-1]
        print(f"tts device bytes={len(pcm)}", flush=True)
        self.speak_done.clear()
        self.sending_audio = True
        try:
            header = (json.dumps({"type": "speak_start", "bytes": len(pcm)}) + "\n").encode("utf-8")
            if self.ser is not None:
                async with self.io:
                    self._write_raw(header, flush=True)
                await asyncio.sleep(0.08)
                off = 0
                while off < len(pcm):
                    piece = pcm[off : off + 4096]
                    async with self.io:
                        self._write_raw(piece, flush=False)
                    off += len(piece)
                    await asyncio.sleep(0)
                async with self.io:
                    self.ser.flush()
            timeout = min(25.0, max(12.0, len(pcm) / 32000 + 6.0))
            try:
                await asyncio.wait_for(self.speak_done.wait(), timeout=timeout)
            except TimeoutError:
                print("SPEAK_DONE timeout", flush=True)
                await self.broadcast({"type": "idle"})
        finally:
            self.sending_audio = False

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
        shown = clip_line(text)
        if thinking_placeholder(self.args.llm):
            await self.broadcast({"type": "chat", "lines": chat_screen(shown, "考え中")})
        try:
            reply = await asyncio.wait_for(
                complete(
                    text,
                    self.args.llm,
                    self.args.llm_model,
                    self.args.llm_base_url,
                    os.environ.get("OPENAI_API_KEY", ""),
                ),
                timeout=self.args.llm_timeout,
            )
        except TimeoutError:
            reply = "応答が時間切れです"
        except Exception as exc:
            reply = f"LLMエラー: {exc}"
        print(f"reply {reply!r}", flush=True)
        await self.broadcast({"type": "chat", "lines": chat_screen(shown, reply)})
        await self.speak(reply)
        if self.mode == "chat":
            await self.broadcast({"type": "listen"})

    async def on_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        if line in ("CLOCK_APPLIED", "CLOCK_FW_READY", "SPEAK_DONE"):
            print(line, flush=True)
            if line == "SPEAK_DONE":
                self.speak_done.set()
            return
        if line == "CLOCK_TIMEOUT":
            print(line, flush=True)
            if self.mode == "chat":
                await self.broadcast({"type": "listen"})
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            print("serial", line[:120], flush=True)
            return
        typ = msg.get("type")
        if typ == "pcm":
            b64 = msg.get("data") or ""
            b64 += "=" * ((4 - len(b64) % 4) % 4)
            try:
                raw = base64.b64decode(b64)
            except Exception:
                return
            self.pcm_buf.extend(raw)
            return
        if typ == "pcm_start":
            self.pcm_buf = bytearray()
            self.pcm_expect = int(msg.get("bytes") or 0)
            self.pcm_wait = 0.0
            print(f"pcm_start bytes={self.pcm_expect}", flush=True)
            return
        if typ == "pcm_end":
            pcm = bytes(self.pcm_buf)
            self.pcm_buf = bytearray()
            self.pcm_expect = 0
            print(f"pcm_end bytes={len(pcm)} reason={msg.get('reason')}", flush=True)
            if self.busy:
                print("busy, drop pcm_end", flush=True)
                return
            self.busy = True
            asyncio.create_task(self._after_pcm(pcm))
            return
        if typ == "touch":
            print("touch", flush=True)
            if self.mode == "clock":
                await self.enter_chat()
            else:
                await self.enter_clock()
            return

    async def _after_pcm(self, pcm: bytes) -> None:
        try:
            energy = pcm_mean_abs(pcm)
            print(f"pcm energy={energy}", flush=True)
            if self.mode == "chat":
                await self.broadcast({"type": "status", "text": "考え中"})
            text = await asyncio.to_thread(self.asr.transcribe, pcm)
            print(f"asr {text!r}", flush=True)
            if not text:
                if self.mode == "chat":
                    await self.enter_chat("話してください")
                return
            await self.handle_text(text)
        except Exception as exc:
            print(f"asr failed: {exc}", flush=True)
            if self.mode == "chat":
                await self.broadcast({"type": "chat", "lines": ["聞き取れません", clip_line(str(exc))]})
                await self.broadcast({"type": "listen"})
        finally:
            self.busy = False

    async def serial_reader(self) -> None:
        buf = b""
        while True:
            async with self.io:
                want = min(4096, self.pcm_expect) if self.pcm_expect > 0 else 4096
                chunk = self.ser.read(want) if want else b""
            if not chunk:
                if self.pcm_expect > 0:
                    self.pcm_wait += 0.02
                    if self.pcm_wait > 3.0:
                        print("pcm binary timeout", flush=True)
                        self.pcm_expect = 0
                        self.pcm_buf = bytearray()
                await asyncio.sleep(0.02)
                continue
            self.pcm_wait = 0.0
            if self.pcm_expect > 0:
                take = min(len(chunk), self.pcm_expect)
                self.pcm_buf.extend(chunk[:take])
                self.pcm_expect -= take
                buf += chunk[take:]
                if self.pcm_expect > 0:
                    continue
            else:
                buf += chunk
            while b"\n" in buf and self.pcm_expect == 0:
                line, buf = buf.split(b"\n", 1)
                await self.on_line(line.decode("utf-8", errors="replace"))
                if self.pcm_expect > 0 and buf:
                    take = min(len(buf), self.pcm_expect)
                    self.pcm_buf.extend(buf[:take])
                    buf = buf[take:]
                    self.pcm_expect -= take

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
            if self.sending_audio or self.pcm_expect > 0:
                await asyncio.sleep(0.2)
                continue
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
            self.ser = serial_mod.Serial()
            self.ser.port = self.args.serial
            self.ser.baudrate = 115200
            self.ser.timeout = 0
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            print(f"serial opened {self.args.serial}", flush=True)
            await asyncio.sleep(3)

        async def run_tasks() -> None:
            tasks = [asyncio.create_task(self.tick_loop()), asyncio.create_task(self.calendar_loop())]
            if self.ser is not None:
                tasks.append(asyncio.create_task(self.serial_reader()))
            await asyncio.gather(*tasks)

        if self.args.ws_port <= 0:
            print("websocket disabled", flush=True)
            await run_tasks()
            return

        async def ws_handler(websocket) -> None:
            self.ws_clients.add(websocket)
            try:
                async for _incoming in websocket:
                    pass
            finally:
                self.ws_clients.discard(websocket)

        try:
            async with websockets.serve(ws_handler, self.args.ws_host, self.args.ws_port):
                print(f"websocket ws://{self.args.ws_host}:{self.args.ws_port}", flush=True)
                await run_tasks()
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                ws_in_use_exit(self.args.ws_host, self.args.ws_port)
            raise


def main() -> None:
    load_env_file(Path(__file__).resolve().parent / ".env")
    parser = argparse.ArgumentParser(description="StackChan host (clock, talk, calendar)")
    parser.add_argument("--weekday", choices=("en", "ja"), default="en")
    parser.add_argument("--tz", default="Asia/Tokyo")
    parser.add_argument("--serial", default="")
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument(
        "--ws-port",
        type=int,
        default=WS_PORT,
        help=f"WebSocket port (default {WS_PORT}). 0 disables it (USB serial only).",
    )
    parser.add_argument("--asr", choices=("whisper", "none"), default="whisper")
    parser.add_argument("--whisper-model", default="base")
    parser.add_argument("--tts", choices=("edge", "none"), default="edge")
    parser.add_argument("--llm", choices=("echo", "ollama", "openai"), default="echo")
    parser.add_argument("--llm-model", default="")
    parser.add_argument(
        "--llm-base-url",
        default="",
        help="Ollama default http://127.0.0.1:11434. OpenAI default https://api.openai.com/v1.",
    )
    parser.add_argument("--llm-timeout", type=float, default=20.0)
    parser.add_argument("--notify-minutes", type=int, default=10)
    parser.add_argument("--calendar-credentials", default="host/google_credentials.json")
    parser.add_argument("--calendar-token", default="host/google_token.json")
    parser.add_argument("--calendar-demo-in-sec", type=int, default=0)
    parser.add_argument("--calendar-demo-title", default="デモ予定")
    args = parser.parse_args()
    asyncio.run(StackchanHost(args).run())


if __name__ == "__main__":
    main()
