import json
import logging
import os
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, Query

from ... import config  # noqa: F401

router = APIRouter(prefix="/api/weather", tags=["weather"])
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5"
logger = logging.getLogger(__name__)


def _demo_weather_payload(endpoint: str, params: dict[str, str]) -> dict:
    city = params.get("q") or os.getenv("WEATHER_CITY", "Hyderabad")
    weather_states = [
        {"main": "Clear", "description": "clear sky", "icon": "01d"},
        {"main": "Clouds", "description": "few clouds", "icon": "02d"},
        {"main": "Rain", "description": "light rain", "icon": "10d"},
    ]

    if endpoint == "weather":
        return {
            "name": city,
            "sys": {"country": "IN"},
            "weather": [weather_states[0]],
            "main": {"temp": 28, "feels_like": 30, "humidity": 52},
            "wind": {"speed": 14.2},
        }

    items = []
    for offset in range(5):
        state = weather_states[offset % len(weather_states)]
        when = datetime.utcnow() + timedelta(hours=offset * 6)
        items.append(
            {
                "dt": int(when.timestamp()),
                "main": {"temp": 25 + offset, "feels_like": 27 + offset, "humidity": 55 + offset},
                "weather": [state],
                "pop": 0.2 + offset * 0.12,
            }
        )
    return {"list": items}


def _request(endpoint: str, params: dict[str, str]) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logger.warning("OPENWEATHER_API_KEY not configured; returning demo weather data.")
        return _demo_weather_payload(endpoint, params)

    query = urlencode({**params, "appid": api_key, "units": "metric"})
    try:
        with urlopen(f"{OPENWEATHER_URL}/{endpoint}?{query}", timeout=10) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 401:
            logger.warning("OpenWeather API key rejected; returning demo weather data.")
            return _demo_weather_payload(endpoint, params)
        if error.code == 404:
            logger.warning("Configured weather city not found; returning demo weather data.")
            return _demo_weather_payload(endpoint, params)
        logger.warning("OpenWeather request failed; returning demo weather data.")
        return _demo_weather_payload(endpoint, params)
    except (URLError, TimeoutError) as error:
        logger.warning("OpenWeather provider unavailable; returning demo weather data.", exc_info=error)
        return _demo_weather_payload(endpoint, params)


def _location_params(city: str | None, latitude: float | None, longitude: float | None) -> dict[str, str]:
    if latitude is not None and longitude is not None:
        return {"lat": str(latitude), "lon": str(longitude)}
    return {"q": city or os.getenv("WEATHER_CITY", "Delhi")}


@router.get("")
def get_weather(
    city: str | None = Query(default=None),
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
) -> dict:
    params = _location_params(city, latitude, longitude)
    current = _request("weather", params)
    forecast = _request("forecast", params)
    daily: dict[str, dict] = {}

    for item in forecast["list"]:
        date = datetime.fromtimestamp(item["dt"]).date().isoformat()
        entry = daily.setdefault(
            date,
            {
                "date": date,
                "temperatures": [],
                "rain_probability": 0,
                "description": item["weather"][0]["description"].title(),
                "icon": item["weather"][0]["icon"],
            },
        )
        entry["temperatures"].append(item["main"]["temp"])
        entry["rain_probability"] = max(entry["rain_probability"], round(item.get("pop", 0) * 100))

    days = list(daily.values())[:5]
    for entry in days:
        temperatures = entry.pop("temperatures")
        entry["high"] = round(max(temperatures))
        entry["low"] = round(min(temperatures))

    return {
        "location": current.get("name", "Configured location"),
        "country": current.get("sys", {}).get("country", ""),
        "current": {
            "temperature": round(current["main"]["temp"]),
            "feels_like": round(current["main"]["feels_like"]),
            "description": current["weather"][0]["description"].title(),
            "icon": current["weather"][0]["icon"],
            "humidity": current["main"]["humidity"],
            "wind_speed": round(current["wind"].get("speed", 0) * 3.6, 1),
            "rain_probability": days[0]["rain_probability"] if days else 0,
        },
        "forecast": days,
    }
