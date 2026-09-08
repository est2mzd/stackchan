from datetime import datetime, timedelta

from calendar_notify import CalendarEvent, due_notifications, spoken_alert


def test_fires_once_in_lead_window():
    start = datetime(2026, 9, 9, 12, 10, 0)
    now = datetime(2026, 9, 9, 12, 0, 0)
    event = CalendarEvent("e1", "定例", start)
    due = due_notifications([event], now, lead_minutes=10, already_sent=set())
    assert due == [event]
    due2 = due_notifications([event], now, lead_minutes=10, already_sent={"e1"})
    assert due2 == []


def test_drops_past_events():
    start = datetime(2026, 9, 9, 11, 0, 0)
    now = datetime(2026, 9, 9, 12, 0, 0)
    event = CalendarEvent("e1", "過ぎた", start)
    assert due_notifications([event], now, 10, set()) == []


def test_spoken_alert():
    event = CalendarEvent("e1", "定例ミーティング", datetime.now() + timedelta(minutes=10))
    assert spoken_alert(event, 10) == "10分後、定例ミーティングです"
