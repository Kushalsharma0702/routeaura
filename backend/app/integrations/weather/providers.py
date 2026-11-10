from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from app.core.config import get_settings
from app.integrations.weather.base import DayForecast, WeatherError, WeatherNotConfigured, WeatherProvider


class NoWeather:
    name = "none"

    def forecast(self, lat: float, lng: float, start: date, end: date) -> list[DayForecast]:
        raise WeatherNotConfigured("No weather provider is configured (set WEATHER_PROVIDER=open-meteo)")


class OpenMeteo:
    """Open-Meteo daily forecast (free for non-commercial use, no key). Only the destination's public coordinates
    are sent. Dates beyond the forecast horizon come back null and stay unknown."""

    name = "open-meteo"

    def __init__(self, base_url: str, timeout: float = 15.0, client: httpx.Client | None = None):
        self.base_url, self.timeout, self._client = base_url.rstrip("/"), timeout, client

    def forecast(self, lat: float, lng: float, start: date, end: date) -> list[DayForecast]:
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lng:.4f}",
            "timezone": "auto",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min",
        }
        try:
            r = (self._client or httpx).get(f"{self.base_url}/v1/forecast", params=params, timeout=self.timeout)
            r.raise_for_status()
            daily = r.json()["daily"]
            fetched = datetime.now(UTC)
            return [
                DayForecast(
                    date.fromisoformat(d),
                    _num(daily["precipitation_sum"][i]),
                    _num(daily["precipitation_probability_max"][i]),
                    _num(daily["temperature_2m_max"][i]),
                    _num(daily["temperature_2m_min"][i]),
                    self.name,
                    fetched,
                )
                for i, d in enumerate(daily["time"])
            ]
        except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError) as exc:
            raise WeatherError(f"open-meteo request failed: {type(exc).__name__}") from exc


def _num(v) -> float | None:
    return None if v is None else float(v)


def get_weather() -> WeatherProvider:
    s = get_settings()
    return OpenMeteo(s.weather_base_url) if s.weather_provider == "open-meteo" else NoWeather()
