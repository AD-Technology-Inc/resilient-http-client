import asyncio
import logging

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [chaos-mock] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chaos Downstream Mock", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/resource")
async def get_resource(
    request: Request,
    chaos: str | None = Query(default=None),
    delay_secs: float = Query(default=12.0, ge=0.0, le=30.0),
    status: int = Query(default=500, ge=400, le=599),
):
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        "Received request path=%s  chaos=%s  client=%s",
        request.url.path,
        chaos or "none",
        client_ip,
    )

    if chaos == "delay":
        logger.warning("Injecting %.2fs delay spike", delay_secs)
        await asyncio.sleep(delay_secs)
        return JSONResponse(
            {"ok": True, "chaos": "delay", "delay_secs": delay_secs},
            status_code=200,
        )

    if chaos == "error":
        logger.warning("Injecting HTTP %d error", status)
        return JSONResponse(
            {"ok": False, "chaos": "error", "injected_status": status},
            status_code=status,
        )

    return JSONResponse({"ok": True, "message": "healthy response"}, status_code=200)
