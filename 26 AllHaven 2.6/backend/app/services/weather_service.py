"""Weather: saved locations (persisted) + honest current-weather fetch.

Current weather is only returned from a real provider response. If the weather
integration is not configured, the API returns ``setup_required`` — never faked.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.weather import WeatherLocation
from app.services import integration_config_service as integrations
from app.services.ai_providers.base import safe_request

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def list_locations(db: Session, principal: Principal) -> List[WeatherLocation]:
    stmt = (
        select(WeatherLocation)
        .where(WeatherLocation.workspace_id == principal.workspace_id)
        .order_by(WeatherLocation.is_default.desc(), WeatherLocation.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def add_location(db: Session, principal: Principal, name: str, is_default: bool = False) -> WeatherLocation:
    if is_default:
        for row in list_locations(db, principal):
            row.is_default = False
    loc = WeatherLocation(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        name=name,
        is_default=is_default,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, principal: Principal, location_id: uuid.UUID) -> None:
    loc = db.scalar(
        select(WeatherLocation).where(
            WeatherLocation.id == location_id,
            WeatherLocation.workspace_id == principal.workspace_id,
        )
    )
    if not loc:
        raise NotFoundError("Location not found.")
    db.delete(loc)
    db.commit()


def _default_location(db: Session, principal: Principal) -> Optional[str]:
    for row in list_locations(db, principal):
        if row.is_default:
            return row.name
    rows = list_locations(db, principal)
    return rows[0].name if rows else None


def current_weather(db: Session, principal: Principal, location: Optional[str] = None) -> dict:
    public, secrets = integrations.effective_config(db, principal, "weather_api")
    api_key = secrets.get("api_key")
    provider = (public.get("provider") or "openweathermap").lower()
    loc = location or public.get("default_location") or _default_location(db, principal)

    if not api_key:
        return {"status": "setup_required", "detail": "Add a Weather API key in Settings → Connected Tools.", "location": loc}
    if not loc:
        return {"status": "no_location", "detail": "Set a default location to see current weather.", "location": None}
    if provider != "openweathermap":
        return {"status": "unsupported_provider", "detail": f"Live fetch not implemented for '{provider}'.", "location": loc}

    code, body, err = safe_request("GET", OPENWEATHER_URL, params={"q": loc, "appid": api_key, "units": "metric"})
    if err or code is None:
        return {"status": "unavailable", "detail": f"Could not reach the weather provider: {err}" if err else "No response", "location": loc}
    if code == 401:
        return {"status": "error", "detail": "The weather API key was rejected (HTTP 401).", "location": loc}
    if code == 404:
        return {"status": "error", "detail": f"Location '{loc}' was not found.", "location": loc}
    if code != 200 or not body:
        return {"status": "error", "detail": f"Weather provider error (HTTP {code}).", "location": loc}

    try:
        return {
            "status": "ok",
            "location": body.get("name") or loc,
            "temp_c": body["main"]["temp"],
            "feels_like_c": body["main"].get("feels_like"),
            "humidity": body["main"].get("humidity"),
            "description": (body.get("weather") or [{}])[0].get("description", ""),
            "icon": (body.get("weather") or [{}])[0].get("icon", ""),
            "wind_speed": (body.get("wind") or {}).get("speed"),
        }
    except (KeyError, TypeError, IndexError):
        return {"status": "error", "detail": "Unexpected response from the weather provider.", "location": loc}
