import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS
from app.routers import auth, cards, insights, log_error, statements, sync, transactions

# ── Logging setup ─────────────────────────────────────────────────────────────
# Always configure a stdout handler so logs appear in the local terminal.
# On Cloud Run (K_SERVICE is set), additionally route to Cloud Logging.
import os

class _ExtraFormatter(logging.Formatter):
    """Formatter that appends extra={} fields to the log line for local visibility."""
    _BASE_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def format(self, record):
        msg = super().format(record)
        extras = {k: v for k, v in record.__dict__.items()
                  if k not in self._BASE_ATTRS and k not in ("message", "asctime")}
        if extras:
            msg += f" | {extras}"
        return msg

_handler = logging.StreamHandler()
_handler.setFormatter(_ExtraFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_handler)

if os.environ.get("K_SERVICE"):
    # Running on Cloud Run — also send structured logs to Cloud Logging
    try:
        import google.cloud.logging
        cloud_logging_client = google.cloud.logging.Client()
        cloud_logging_client.setup_logging()
    except Exception as e:
        logging.warning("cloud_logging_setup_failed: %s", e)

logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FinyBot API",
    description="Credit card expense tracker — fetches Gmail PDF statements and extracts transactions via Gemini.",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",         tags=["auth"])
app.include_router(cards.router,        prefix="/api/cards",        tags=["cards"])
app.include_router(sync.router,         prefix="/api/sync",         tags=["sync"])
app.include_router(transactions.router, prefix="/api/transactions",  tags=["transactions"])
app.include_router(statements.router,   prefix="/api/statements",   tags=["statements"])
app.include_router(insights.router,     prefix="/api/insights",     tags=["insights"])
app.include_router(log_error.router,    prefix="/api/log-error",    tags=["logging"])

# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "type": type(exc).__name__,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. It has been logged."},
    )

# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    """Used by Cloud Run health checks."""
    return {"status": "ok"}


logger.info("finybot_api_started", extra={"cors_origins": CORS_ORIGINS})
