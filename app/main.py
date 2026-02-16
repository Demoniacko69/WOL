import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from urllib import request as urlrequest

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import load_settings
from .database import Database
from .logging_config import setup_logging
from .rate_limit import build_rate_limit_middleware
from .schemas import ApiMessage, DeviceCreate, ScheduleCreate, WakeRequest
from .security import build_auth_middleware
from .wol import send_magic_packet


logger = logging.getLogger("wolserver")



def parse_broadcasts(raw_broadcast, defaults: list[str]) -> list[str]:
    if raw_broadcast is None:
        return defaults
    if isinstance(raw_broadcast, str):
        return [raw_broadcast]
    return [x for x in raw_broadcast if x]



def ping_host(host: str) -> bool:
    if sys.platform.startswith("win"):
        cmd = ["ping", "-n", "1", "-w", "1000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
        return result.returncode == 0
    except Exception:
        return False



def create_app() -> FastAPI:
    settings = load_settings()
    setup_logging(settings.log_level)

    db = Database(settings.db_path)
    db.init()

    scheduler = BackgroundScheduler(timezone="UTC")
    templates = Jinja2Templates(directory="app/templates")

    app = FastAPI(
        title="WOL Server",
        description="Wake-On-LAN web server with persistence, scheduler and optional auth",
        version="1.0.0",
    )

    app.middleware("http")(build_rate_limit_middleware(settings))
    app.middleware("http")(build_auth_middleware(settings))

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "request",
            extra={
                "extra": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "client": request.client.host if request.client else "unknown",
                }
            },
        )
        return response

    def schedule_job(schedule_id: int, device_id: int, broadcasts: list[str] | None):
        def _job():
            device = db.get_device(device_id)
            if not device:
                logger.warning("schedule_device_not_found", extra={"extra": {"schedule_id": schedule_id, "device_id": device_id}})
                return

            selected = broadcasts if broadcasts else json.loads(device["broadcasts"])
            for broadcast in selected:
                try:
                    send_magic_packet(device["mac"], broadcast)
                    logger.info(
                        "scheduled_wake_sent",
                        extra={"extra": {"schedule_id": schedule_id, "device_id": device_id, "broadcast": broadcast}},
                    )
                except Exception as exc:
                    logger.error(
                        "scheduled_wake_failed",
                        extra={"extra": {"schedule_id": schedule_id, "device_id": device_id, "broadcast": broadcast, "error": str(exc)}},
                    )

        return _job

    @app.on_event("startup")
    def startup_event():
        scheduler.start()
        for item in db.list_schedules():
            if not int(item["enabled"]):
                continue
            trigger = CronTrigger.from_crontab(item["cron_expr"])
            bcasts = json.loads(item["broadcasts"]) if item["broadcasts"] else None
            scheduler.add_job(
                schedule_job(item["id"], item["device_id"], bcasts),
                trigger=trigger,
                id=f"schedule-{item['id']}",
                replace_existing=True,
            )
        logger.info("scheduler_started")

    @app.on_event("shutdown")
    def shutdown_event():
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        devices = db.list_devices()
        parsed_devices = []
        for device in devices:
            parsed = dict(device)
            parsed["broadcasts"] = json.loads(device["broadcasts"])
            parsed_devices.append(parsed)

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "devices": parsed_devices,
                "default_broadcast": ",".join(settings.default_broadcasts),
            },
        )

    @app.get("/health", response_model=ApiMessage)
    def health():
        return ApiMessage(success=True, message="ok", data={"service": "wolserver"})

    @app.post("/wake", response_model=ApiMessage)
    def wake(payload: WakeRequest):
        broadcasts = parse_broadcasts(payload.broadcast, settings.default_broadcasts)
        sent = []

        for broadcast in broadcasts:
            try:
                send_magic_packet(payload.mac, broadcast)
                sent.append(broadcast)
                logger.info("wake_sent", extra={"extra": {"mac": payload.mac, "broadcast": broadcast}})
            except Exception as exc:
                logger.error("wake_failed", extra={"extra": {"mac": payload.mac, "broadcast": broadcast, "error": str(exc)}})
                raise HTTPException(status_code=500, detail=f"Error sending WOL packet: {exc}")

        return ApiMessage(success=True, message="Magic packet sent", data={"mac": payload.mac, "broadcasts": sent})

    @app.get("/devices", response_model=ApiMessage)
    def list_devices():
        rows = db.list_devices()
        result = []
        for row in rows:
            record = dict(row)
            record["broadcasts"] = json.loads(row["broadcasts"])
            result.append(record)
        return ApiMessage(success=True, message="Devices loaded", data={"devices": result})

    @app.post("/devices", response_model=ApiMessage)
    def add_device(payload: DeviceCreate):
        broadcasts = payload.broadcasts if payload.broadcasts else settings.default_broadcasts
        created_at = datetime.now(timezone.utc).isoformat()
        device_id = db.add_device(
            name=payload.name.strip(),
            mac=payload.mac,
            ip=payload.ip.strip() if payload.ip else None,
            broadcasts_json=json.dumps(broadcasts),
            shutdown_url=payload.shutdown_url.strip() if payload.shutdown_url else None,
            created_at=created_at,
        )
        logger.info("device_created", extra={"extra": {"device_id": device_id, "name": payload.name}})
        return ApiMessage(success=True, message="Device added", data={"id": device_id})

    @app.delete("/devices/{device_id}", response_model=ApiMessage)
    def delete_device(device_id: int):
        schedule_ids = db.list_schedule_ids_for_device(device_id)
        deleted = db.delete_device(device_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Device not found")

        for schedule_id in schedule_ids:
            job_id = f"schedule-{schedule_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

        logger.info("device_deleted", extra={"extra": {"device_id": device_id}})
        return ApiMessage(success=True, message="Device deleted")

    @app.get("/status/{device_id}", response_model=ApiMessage)
    def status(device_id: int):
        device = db.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        if not device["ip"]:
            raise HTTPException(status_code=400, detail="Device has no IP/hostname configured")

        online = ping_host(device["ip"])
        return ApiMessage(
            success=True,
            message="Status checked",
            data={"id": device_id, "ip": device["ip"], "status": "online" if online else "offline"},
        )

    @app.get("/schedules", response_model=ApiMessage)
    def list_schedules():
        rows = db.list_schedules()
        result = []
        for row in rows:
            entry = dict(row)
            entry["broadcasts"] = json.loads(row["broadcasts"]) if row["broadcasts"] else None
            result.append(entry)
        return ApiMessage(success=True, message="Schedules loaded", data={"schedules": result})

    @app.post("/schedules", response_model=ApiMessage)
    def add_schedule(payload: ScheduleCreate):
        device = db.get_device(payload.device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        try:
            trigger = CronTrigger.from_crontab(payload.cron)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc

        created_at = datetime.now(timezone.utc).isoformat()
        broadcasts_json = json.dumps(payload.broadcasts) if payload.broadcasts else None
        schedule_id = db.add_schedule(payload.device_id, payload.cron, broadcasts_json, created_at)

        scheduler.add_job(
            schedule_job(schedule_id, payload.device_id, payload.broadcasts),
            trigger=trigger,
            id=f"schedule-{schedule_id}",
            replace_existing=True,
        )

        logger.info("schedule_created", extra={"extra": {"schedule_id": schedule_id, "device_id": payload.device_id}})
        return ApiMessage(success=True, message="Schedule added", data={"id": schedule_id})

    @app.delete("/schedules/{schedule_id}", response_model=ApiMessage)
    def delete_schedule(schedule_id: int):
        deleted = db.delete_schedule(schedule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Schedule not found")

        job_id = f"schedule-{schedule_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        logger.info("schedule_deleted", extra={"extra": {"schedule_id": schedule_id}})
        return ApiMessage(success=True, message="Schedule deleted")

    @app.post("/shutdown/{device_id}", response_model=ApiMessage)
    def shutdown_device(device_id: int):
        device = db.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        if not device["shutdown_url"]:
            raise HTTPException(status_code=400, detail="No shutdown_url configured for this device")

        try:
            req = urlrequest.Request(device["shutdown_url"], data=b"{}", method="POST", headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=5) as resp:
                status_code = resp.status
        except Exception as exc:
            logger.error("shutdown_failed", extra={"extra": {"device_id": device_id, "error": str(exc)}})
            raise HTTPException(status_code=502, detail=f"Remote shutdown request failed: {exc}") from exc

        logger.info("shutdown_requested", extra={"extra": {"device_id": device_id, "shutdown_url": device["shutdown_url"]}})
        return ApiMessage(success=True, message="Shutdown request sent", data={"status_code": status_code})

    return app
