from __future__ import annotations

from datetime import datetime

WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
WEEKDAYS_JA = (
    "月曜日",
    "火曜日",
    "水曜日",
    "木曜日",
    "金曜日",
    "土曜日",
    "日曜日",
)


def format_clock_lines(now: datetime, weekday_lang: str = "en") -> list[str]:
    if weekday_lang == "ja":
        weekday = WEEKDAYS_JA[now.weekday()]
    else:
        weekday = WEEKDAYS_EN[now.weekday()]
    return [
        now.strftime("%Y/%m/%d"),
        now.strftime("%H:%M:%S"),
        weekday,
    ]


def clock_message(now: datetime, weekday_lang: str = "en") -> dict:
    return {"type": "clock", "lines": format_clock_lines(now, weekday_lang)}
