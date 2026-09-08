from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    title: str
    start: datetime


def due_notifications(
    events: list[CalendarEvent],
    now: datetime,
    lead_minutes: int,
    already_sent: set[str],
    drop_past: bool = True,
) -> list[CalendarEvent]:
    """Events whose notify time has arrived and start is still in the future."""
    due: list[CalendarEvent] = []
    lead = timedelta(minutes=lead_minutes)
    for event in events:
        if drop_past and event.start <= now:
            continue
        fire_at = event.start - lead
        if fire_at <= now < event.start and event.event_id not in already_sent:
            due.append(event)
    return due


def spoken_alert(event: CalendarEvent, lead_minutes: int) -> str:
    return f"{lead_minutes}分後、{event.title}です"
