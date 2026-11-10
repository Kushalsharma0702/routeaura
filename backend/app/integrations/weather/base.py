"""Weather provider interface. Forecasts carry their SOURCE and FETCH TIME; unknown values stay None."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


class WeatherError(Exception):
    pass


class WeatherNotConfigured(WeatherError):
    pass


@dataclass
class DayForecast:
    day: date
    precip_mm: float | None
    precip_prob: float | None  # percent, None when the provider does not give it
    temp_max_c: float | None
    temp_min_c: float | None
    source: str
    fetched_at: datetime

    def to_payload(self) -> dict:
        return {
            "date": self.day.isoformat(),
            "precip_mm": self.precip_mm,
            "precip_prob": self.precip_prob,
            "temp_max_c": self.temp_max_c,
            "temp_min_c": self.temp_min_c,
        }


class WeatherProvider(Protocol):
    name: str

    def forecast(self, lat: float, lng: float, start: date, end: date) -> list[DayForecast]: ...
