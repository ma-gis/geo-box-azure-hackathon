"""
MCP Gateway Middleware

Provides security and observability for MCP server endpoints:
  1. /health bypass    — health endpoint skips all checks
  2. Kill-switch       — if MCP_GATEWAY_DISABLED=true, return 503 immediately
  3. API key auth      — validate X-API-Key header using timing-safe compare
                         (optional: only enforced when MCP_API_KEY env var is set)
  4. Rate limiter      — sliding window, 60 req/min per client IP (in-memory)
  5. Audit log         — structured log on every request: request_id, path,
                         method, client_ip, status_code, duration_ms
  6. Request ID        — UUID4 if X-Request-ID header absent; propagated in response

Usage:
    app.add_middleware(MCPGatewayMiddleware)
"""

import os
import time
import hmac
import uuid
import collections
import structlog
from typing import DefaultDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# Rate limiter — per-client deque of monotonic request timestamps
_rate_limit_state: DefaultDict[str, collections.deque] = collections.defaultdict(
    lambda: collections.deque()
)
RATE_LIMIT_WINDOW = 60   # seconds
RATE_LIMIT_MAX = 60      # max requests per window per IP


class MCPGatewayMiddleware(BaseHTTPMiddleware):
    """
    Lightweight gateway middleware for MCP servers.

    Add to any Starlette/FastAPI app:
        app.add_middleware(MCPGatewayMiddleware)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # 1. /health bypass — skip all gateway checks
        if path == "/health":
            return await call_next(request)

        # 2. Kill-switch — operator can disable MCP tool access without redeploy
        if os.getenv("MCP_GATEWAY_DISABLED", "").lower() == "true":
            logger.warning("mcp_gateway_disabled_kill_switch", path=path)
            return JSONResponse(
                {"error": "Service Unavailable", "detail": "MCP gateway is disabled"},
                status_code=503,
            )

        # 6. Request ID — use caller-supplied value or generate a new UUID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 3. API key validation (optional — only when MCP_API_KEY is configured)
        api_key_required = os.getenv("MCP_API_KEY", "")
        if api_key_required:
            provided_key = request.headers.get("X-API-Key", "")
            # hmac.compare_digest is timing-safe — prevents timing oracle attacks
            if not hmac.compare_digest(provided_key, api_key_required):
                logger.warning(
                    "mcp_api_key_invalid",
                    request_id=request_id,
                    path=path,
                    client_ip=_get_client_ip(request),
                )
                return JSONResponse(
                    {"error": "Unauthorized", "detail": "Invalid or missing API key"},
                    status_code=401,
                    headers={"X-Request-ID": request_id},
                )

        # 4. Rate limiter — sliding window per client IP
        client_ip = _get_client_ip(request)
        now = time.monotonic()
        window_start = now - RATE_LIMIT_WINDOW

        dq = _rate_limit_state[client_ip]
        # Evict timestamps outside the current window
        while dq and dq[0] < window_start:
            dq.popleft()

        if len(dq) >= RATE_LIMIT_MAX:
            logger.warning(
                "mcp_rate_limit_exceeded",
                request_id=request_id,
                client_ip=client_ip,
                path=path,
            )
            return JSONResponse(
                {
                    "error": "Too Many Requests",
                    "detail": f"Rate limit: {RATE_LIMIT_MAX} requests per {RATE_LIMIT_WINDOW}s",
                },
                status_code=429,
                headers={"X-Request-ID": request_id},
            )

        dq.append(now)

        # 5. Audit log — request start
        method = request.method
        start_time = time.monotonic()

        logger.info(
            "mcp_request",
            request_id=request_id,
            path=path,
            method=method,
            client_ip=client_ip,
        )

        # Forward request to the actual handler
        response = await call_next(request)

        duration_ms = (time.monotonic() - start_time) * 1000

        # 5. Audit log — request complete
        logger.info(
            "mcp_response",
            request_id=request_id,
            path=path,
            method=method,
            client_ip=client_ip,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 1),
        )

        # 6. Propagate Request ID in response headers
        response.headers["X-Request-ID"] = request_id

        return response


def _get_client_ip(request: Request) -> str:
    """Extract client IP from the actual TCP peer.

    We intentionally ignore X-Forwarded-For to prevent spoofing-based
    rate-limit bypass. These MCP servers run on internal ingress only,
    so the peer IP is always the real caller (the orchestrator container).
    """
    return request.client.host if request.client else "unknown"
