"""Production lab agent: authenticated requests, shared limits, JSON logs."""
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
            "event": record.getMessage(), **getattr(record, "fields", {}),
        }, ensure_ascii=False)

logger = logging.getLogger("production_agent")
logger.setLevel(settings.log_level)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    # Uvicorn handles SIGTERM and drains in-flight requests before this cleanup.
    # Do not replace its signal handlers.
    yield
    r.close()
    logger.info("shutdown")

app = FastAPI(title="Production AI Agent", lifespan=lifespan)

@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = uuid.uuid4().hex
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = request.scope.get("route")
        logger.info("request", extra={"fields": {
            "request_id": request_id, "method": request.method,
            "path": route.path if route else "unmatched", "status": status,
            "ms": round((time.perf_counter() - start) * 1000, 2),
        }})

@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    logger.warning("redis_unavailable")
    return JSONResponse(status_code=503, content={"detail": "State store unavailable"},
                        headers={"Retry-After": "1"})

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    healthy = redis_healthy()
    return JSONResponse(status_code=200 if healthy else 503, content={"ready": healthy})

@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    # FastAPI runs this synchronous handler in its thread pool.
    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)
    logger.info("llm_call", extra={"fields": {
        "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost,
    }})
    return {"question": body.question, "answer": answer,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}}
