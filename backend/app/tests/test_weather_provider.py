from datetime import date

import httpx
import pytest

from app.integrations.weather.base import WeatherError, WeatherNotConfigured
from app.integrations.weather.providers import NoWeather, OpenMeteo, get_weather


def provider(handler):
    return OpenMeteo("https://wx.test", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_no_weather_provider_refuses_instead_of_inventing():
    with pytest.raises(WeatherNotConfigured):
        NoWeather().forecast(26.9, 75.8, date(2030, 1, 1), date(2030, 1, 2))
    assert get_weather().name == "none"  # default configuration


def test_open_meteo_parses_daily_values_and_keeps_nulls_unknown():
    seen = {}

    def handler(req: httpx.Request):
        seen["q"] = dict(req.url.params)
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2030-01-01", "2030-01-02"],
                    "precipitation_sum": [12.4, None],
                    "precipitation_probability_max": [80, None],
                    "temperature_2m_max": [24.5, None],
                    "temperature_2m_min": [11.0, None],
                }
            },
        )

    out = provider(handler).forecast(26.9124, 75.7873, date(2030, 1, 1), date(2030, 1, 2))
    assert (
        out[0].precip_mm == 12.4
        and out[0].precip_prob == 80
        and out[0].temp_max_c == 24.5
        and out[0].source == "open-meteo"
    )
    assert out[1].precip_mm is None and out[1].precip_prob is None and out[1].temp_max_c is None  # never defaulted to 0
    assert out[0].day == date(2030, 1, 1) and out[0].fetched_at.tzinfo is not None
    assert (
        seen["q"]["latitude"] == "26.9124"
        and seen["q"]["start_date"] == "2030-01-01"
        and "precipitation_sum" in seen["q"]["daily"]
    )


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500),
        lambda r: httpx.Response(200, text="nope"),
        lambda r: httpx.Response(200, json={"daily": {"time": ["2030-01-01"]}}),
        lambda r: httpx.Response(200, json={"error": True}),
    ],
)
def test_open_meteo_failures_raise_weather_error(handler):
    with pytest.raises(WeatherError):
        provider(handler).forecast(26.9, 75.8, date(2030, 1, 1), date(2030, 1, 1))
