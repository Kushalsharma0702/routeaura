"""One definition of "today" for bookings. Hotel check-in/out dates are calendar dates at the property, so they are
compared with today's date in the property's time zone (default Asia/Kolkata), not the server's or UTC's."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().booking_timezone)).date()
