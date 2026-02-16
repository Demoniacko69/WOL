import base64
import hmac
from fastapi import Request
from fastapi.responses import JSONResponse

from .config import Settings



def build_auth_middleware(settings: Settings):
    async def auth_middleware(request: Request, call_next):
        if not settings.enable_auth:
            return await call_next(request)

        if not settings.auth_user or not settings.auth_pass:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Auth enabled but AUTH_USER/AUTH_PASS are missing"},
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
                content={"success": False, "message": "Authentication required"},
            )

        try:
            raw = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
            provided_user, provided_pass = raw.split(":", 1)
        except Exception:
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
                content={"success": False, "message": "Invalid auth header"},
            )

        user_ok = hmac.compare_digest(provided_user, settings.auth_user)
        pass_ok = hmac.compare_digest(provided_pass, settings.auth_pass)
        if not (user_ok and pass_ok):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
                content={"success": False, "message": "Invalid credentials"},
            )

        return await call_next(request)

    return auth_middleware
