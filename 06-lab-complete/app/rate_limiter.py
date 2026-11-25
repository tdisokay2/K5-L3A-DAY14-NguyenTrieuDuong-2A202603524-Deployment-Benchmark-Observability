"""An atomic Redis sliding window shared across workers and restarts."""
import hashlib
import math
import uuid
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

# Redis time avoids clock differences between instances. Rejected calls do not
# consume slots. Keys contain digests rather than raw API keys.
SLIDING_WINDOW = """
local clock = redis.call('TIME')
local now = clock[1] * 1000 + math.floor(clock[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, tonumber(oldest[2]) + 60000 - now)
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], 60000)
return 0
"""

def check_rate_limit(key: str) -> None:
    digest = hashlib.sha256(key.encode()).hexdigest()
    retry_ms = r.eval(SLIDING_WINDOW, 1, f"rate:{settings.environment}:{digest}",
                      settings.rate_limit_per_minute, uuid.uuid4().hex)
    if retry_ms:
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(math.ceil(int(retry_ms) / 1000))})
