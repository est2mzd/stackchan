from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_notify import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def load_events(
    credentials_path: Path,
    token_path: Path,
    tz_name: str,
    now: datetime,
    window_hours: int = 24,
) -> list[CalendarEvent]:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds is None or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                return []
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    tz = ZoneInfo(tz_name)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    time_min = now.astimezone(timezone.utc).isoformat()
    time_max = (now + timedelta(hours=window_hours)).astimezone(timezone.utc).isoformat()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    out: list[CalendarEvent] = []
    for item in result.get("items", []):
        start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        if not start_raw:
            continue
        if "T" in start_raw:
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(tz).replace(tzinfo=None)
        else:
            start = datetime.fromisoformat(start_raw)
        out.append(
            CalendarEvent(
                event_id=item.get("id", start_raw),
                title=item.get("summary") or "(無題)",
                start=start,
            )
        )
    return out
