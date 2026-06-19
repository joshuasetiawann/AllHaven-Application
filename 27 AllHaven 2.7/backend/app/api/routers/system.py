"""System Control router — start/stop/restart, status, logs, and port settings.

Every endpoint requires an authenticated principal. The service layer enforces
the service/action allowlists and the local-mode gate, and forwards privileged
work to the localhost-only Haven agent. No shell, no Docker here.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.api.dependencies import get_current_principal
from app.core.principal import Principal
from app.core.responses import success_response
from app.services import system_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def status(principal: Principal = Depends(get_current_principal)) -> dict:
    return success_response(system_service.get_status(), "System status")


@router.post("/services/{name}/{action}")
def service_action(
    name: str,
    action: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return success_response(system_service.do_action(name, action), "Service updated")


@router.get("/logs/{name}")
def service_logs(
    name: str,
    lines: int = Query(300, ge=1, le=1000),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return success_response(system_service.get_logs(name, lines), "Service logs")


@router.get("/ports")
def get_ports(principal: Principal = Depends(get_current_principal)) -> dict:
    return success_response(system_service.get_ports(), "Service ports")


@router.post("/ports")
def save_ports(
    payload: dict = Body(...),
    restart: bool = Query(False),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return success_response(system_service.save_ports(payload, restart), "Ports saved")
