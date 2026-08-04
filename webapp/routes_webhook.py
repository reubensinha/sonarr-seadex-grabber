"""Sonarr webhook receiver + health check, merged into the main web server.

Replaces the old standalone webhook_server.py. The server always runs (so
the dashboard/health check are always reachable); USE_WEBHOOK only gates
whether an incoming webhook actually triggers a sync, matching the original
behavior where the whole webhook server used to simply not start.
"""

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from core.config import USE_WEBHOOK
from core.utils import log
from main import webhook_event_handler

router = APIRouter()


@router.get("/health")
def health():
    return PlainTextResponse("Sonarr Seadex Grabber is running")


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception as e:
        log(f"Failed to parse webhook JSON: {e}")
        return JSONResponse({"status": "invalid json"}, status_code=400)

    event_type = payload.get("eventType", "Unknown")
    log(f"Received Sonarr webhook: {event_type}")

    if not USE_WEBHOOK:
        log(f"Webhook event '{event_type}' received but USE_WEBHOOK is disabled - ignoring")
        return JSONResponse({"status": "ignored (webhook disabled)"})

    # Runs in a background thread so the HTTP response returns immediately,
    # matching the old raw http.server implementation's behavior.
    background_tasks.add_task(webhook_event_handler, event_type, payload)

    return JSONResponse({"status": "success"})
