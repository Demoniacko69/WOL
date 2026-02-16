from collections import defaultdict, deque
from time import time

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import Settings



def build_rate_limit_middleware(settings: Settings):
    requests_by_ip: dict[str, deque[float]] = defaultdict(deque)

    async def rate_limit_middleware(request: Request, call_next):
        if not settings.enable_rate_limit:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time()
        window_start = now - settings.rate_limit_window_seconds

        bucket = requests_by_ip[ip]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Rate limit exceeded",
                    "data": {
                        "limit": settings.rate_limit_requests,
                        "window_seconds": settings.rate_limit_window_seconds,
                    },
                },
            )

        bucket.append(now)
        return await call_next(request)

    return rate_limit_middleware
