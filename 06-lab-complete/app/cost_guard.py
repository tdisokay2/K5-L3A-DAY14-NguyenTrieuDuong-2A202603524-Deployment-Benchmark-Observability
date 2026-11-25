"""UTC daily and monthly shared spending ledgers, stored in nano-USD."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
NANO_USD = 1_000_000_000

def _periods():
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_month = (now.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    prefix = f"cost:{{{settings.environment}}}"
    return (
        (f"{prefix}:day:{now:%Y-%m-%d}", int(tomorrow.timestamp()), settings.daily_budget_usd),
        (f"{prefix}:month:{now:%Y-%m}", int(next_month.timestamp()), settings.monthly_budget_usd),
    )

def check_budget() -> None:
    periods = _periods()
    spent = r.mget([p[0] for p in periods])
    if any(int(value or 0) >= round(period[2] * NANO_USD)
           for value, period in zip(spent, periods)):
        raise HTTPException(status_code=402, detail="LLM budget exhausted")

def record_cost(input_tokens: int, output_tokens: int) -> float:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be nonnegative")
    # Exactly 150 nano-USD/input token and 600 nano-USD/output token.
    nano_cost = input_tokens * 150 + output_tokens * 600
    with r.pipeline(transaction=True) as pipe:
        for key, expires_at, _ in _periods():
            pipe.incrby(key, nano_cost)
            pipe.expireat(key, expires_at)
        pipe.execute()
    return nano_cost / NANO_USD
