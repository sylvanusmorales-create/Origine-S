import os
import caldav
from datetime import datetime, timedelta, timezone


GMAIL = os.environ.get("GMAIL_ADDRESS", "")
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
CALDAV_URL = "https://apidata.googleusercontent.com/caldav/v2"


def _get_client():
    return caldav.DAVClient(
        url=CALDAV_URL,
        username=GMAIL,
        password=PASSWORD
    )


def calendar_read(days_ahead: int = 7) -> str:
    try:
        client = _get_client()
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            return "Aucun calendrier trouvé."

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        results = []

        for cal in calendars[:3]:
            events = cal.date_search(start=now, end=end, expand=True)
            for event in events:
                comp = event.vobject_instance.vevent
                summary = str(getattr(comp, "summary", "Sans titre").value)
                dtstart = getattr(comp, "dtstart", None)
                dtend = getattr(comp, "dtend", None)
                location = str(getattr(comp, "location", "").value) if hasattr(comp, "location") else ""

                start_str = dtstart.value.strftime("%d/%m/%Y %H:%M") if dtstart else "?"
                end_str = dtend.value.strftime("%H:%M") if dtend else "?"

                entry = f"• {summary}\n  {start_str} → {end_str}"
                if location:
                    entry += f"\n  Lieu : {location}"
                results.append(entry)

        if not results:
            return f"Aucun événement dans les {days_ahead} prochains jours."

        return f"Agenda ({days_ahead} jours) :\n\n" + "\n\n".join(results)

    except Exception as e:
        return f"Erreur Calendar (lecture) : {e}"


def calendar_create(title: str, date: str, time: str = "09:00", duration_hours: int = 1, description: str = "") -> str:
    try:
        client = _get_client()
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            return "Aucun calendrier trouvé."

        cal = calendars[0]

        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        dt_end = dt + timedelta(hours=duration_hours)

        uid = f"origine-s-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Origine S//FR
BEGIN:VEVENT
UID:{uid}
SUMMARY:{title}
DESCRIPTION:{description}
DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}
END:VEVENT
END:VCALENDAR"""

        cal.add_event(ical)
        return f"Événement créé : {title} le {date} à {time}"

    except Exception as e:
        return f"Erreur Calendar (création) : {e}"