"""
AquaTwin AI — Zero-Trust FastAPI Security Shield (Step 4 of 5)
Provides TrustedHost protection, constant-time API key + HMAC-SHA256 replay-proof auth,
adaptive IP burst banning, payload/injection filtering, and strict response headers.
"""

from collections import deque
import hashlib
import hmac
import logging
import os
import re
import time
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

logger = logging.getLogger("aquatwin.zero_trust")

MAX_PAYLOAD_BYTES = 16384
BURST_WINDOW_SEC = 60
BURST_MAX_REQS = 90
VIOLATION_WINDOW_SEC = 300
VIOLATION_BAN_THRESHOLD = 8
BAN_DURATION_SEC = 900
MAX_TRACKED_IPS = 5000
HMAC_REPLAY_WINDOW_SEC = 300

PUBLIC_EXEMPT_PATHS = {"/", "/health"}

SUSPICIOUS_PATTERNS = [
    re.compile(r"\.\.(?:/|\\|%2f|%5c)", re.IGNORECASE),
    re.compile(r"(?:%00|\x00)", re.IGNORECASE),
    re.compile(r"<\s*script\b", re.IGNORECASE),
    re.compile(r"\bunion\s+all?\s+select\b", re.IGNORECASE),
    re.compile(r"(?:/etc/passwd|win\.ini|cmd\.exe)", re.IGNORECASE),
]


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64] or "unknown"
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return "unknown"


def _is_suspicious_request(path: str, query: str) -> bool:
    decoded = unquote(f"{path}?{query}")
    for pat in SUSPICIOUS_PATTERNS:
        if pat.search(decoded):
            return True
    return False


def verify_constant_time_key(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def verify_hmac_request(secret: str, timestamp_str: str, signature_hex: str, method: str, path: str, body: bytes) -> bool:
    if not secret or not timestamp_str or not signature_hex:
        return False
    try:
        ts = int(timestamp_str)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > HMAC_REPLAY_WINDOW_SEC:
        return False
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = f"{ts}.{method.upper()}.{path}.{body_hash}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature_hex.strip().lower())


class ZeroTrustMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._req_hits: dict[str, deque] = {}
        self._violations: dict[str, deque] = {}
        self._banned_until: dict[str, float] = {}

    def _prune_if_needed(self, now: float) -> None:
        if len(self._req_hits) > MAX_TRACKED_IPS:
            expired = [ip for ip, q in self._req_hits.items() if not q or (now - q[-1]) > BURST_WINDOW_SEC]
            for ip in expired:
                self._req_hits.pop(ip, None)
            if len(self._req_hits) > MAX_TRACKED_IPS:
                self._req_hits.clear()
        if len(self._banned_until) > MAX_TRACKED_IPS:
            self._banned_until = {ip: until for ip, until in self._banned_until.items() if until > now}

    def _record_violation(self, ip: str, now: float) -> None:
        q = self._violations.setdefault(ip, deque())
        while q and (now - q[0]) > VIOLATION_WINDOW_SEC:
            q.popleft()
        q.append(now)
        if len(q) >= VIOLATION_BAN_THRESHOLD:
            self._banned_until[ip] = now + BAN_DURATION_SEC
            logger.warning("ZeroTrust banned IP %s for %ds after repeated security violations", ip, BAN_DURATION_SEC)

    def _apply_headers(self, response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        if "server" in response.headers:
            del response.headers["server"]
        return response

    async def dispatch(self, request: Request, call_next):
        # Allow CORS preflight OPTIONS requests to pass through to CORSMiddleware
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        now = time.time()
        ip = _client_ip(request)
        self._prune_if_needed(now)

        # 1. Check active temporary IP ban
        ban_until = self._banned_until.get(ip, 0.0)
        if ban_until > now:
            retry_after = max(1, int(ban_until - now))
            resp = JSONResponse(
                status_code=429,
                content={"ok": False, "code": "IP_TEMPORARILY_BANNED", "message": "Access temporarily suspended due to abusive traffic."},
                headers={"Retry-After": str(retry_after)},
            )
            return self._apply_headers(resp)

        # 2. Adaptive sliding-window burst flood detection
        hits = self._req_hits.setdefault(ip, deque())
        while hits and (now - hits[0]) > BURST_WINDOW_SEC:
            hits.popleft()
        hits.append(now)
        if len(hits) > BURST_MAX_REQS:
            self._banned_until[ip] = now + BAN_DURATION_SEC
            resp = JSONResponse(
                status_code=429,
                content={"ok": False, "code": "BURST_BLOCKED", "message": "Request burst limit exceeded. Try again later."},
                headers={"Retry-After": str(BAN_DURATION_SEC)},
            )
            return self._apply_headers(resp)

        # 3. Pre-route payload size limit (> 16 KB)
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_PAYLOAD_BYTES:
            self._record_violation(ip, now)
            resp = JSONResponse(
                status_code=413,
                content={"ok": False, "code": "PAYLOAD_TOO_LARGE", "message": "Request payload exceeds 16 KB security limit."},
            )
            return self._apply_headers(resp)

        # 4. Path traversal, null-byte & injection probe block
        if _is_suspicious_request(request.url.path, request.url.query):
            self._record_violation(ip, now)
            resp = JSONResponse(
                status_code=400,
                content={"ok": False, "code": "MALICIOUS_REQUEST_BLOCKED", "message": "Request rejected by input security filter."},
            )
            return self._apply_headers(resp)

        # 5. Optional Zero-Trust API Key & HMAC-SHA256 enforcement on non-health routes
        path = request.url.path.rstrip("/") or "/"
        if path not in PUBLIC_EXEMPT_PATHS:
            expected_key = os.getenv("AQUATWIN_API_KEY", "").strip()
            if expected_key:
                provided_key = request.headers.get("X-API-Key", "").strip()
                if not verify_constant_time_key(provided_key, expected_key):
                    self._record_violation(ip, now)
                    resp = JSONResponse(
                        status_code=401,
                        content={"ok": False, "code": "UNAUTHORIZED", "message": "Valid API credentials are required."},
                    )
                    return self._apply_headers(resp)

            hmac_secret = os.getenv("AQUATWIN_HMAC_SECRET", "").strip()
            if hmac_secret and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                body = await request.body()
                if len(body) > MAX_PAYLOAD_BYTES:
                    self._record_violation(ip, now)
                    return self._apply_headers(JSONResponse(status_code=413, content={"ok": False, "code": "PAYLOAD_TOO_LARGE", "message": "Payload exceeds 16 KB."}))
                ts_hdr = request.headers.get("X-AquaTwin-Timestamp", "")
                sig_hdr = request.headers.get("X-AquaTwin-Signature", "")
                if not verify_hmac_request(hmac_secret, ts_hdr, sig_hdr, request.method, path, body):
                    self._record_violation(ip, now)
                    resp = JSONResponse(
                        status_code=401,
                        content={"ok": False, "code": "INVALID_SIGNATURE", "message": "Request signature verification failed."},
                    )
                    return self._apply_headers(resp)

        response = await call_next(request)
        if response.status_code in {401, 403}:
            self._record_violation(ip, now)
        return self._apply_headers(response)


def attach_zero_trust(app: FastAPI) -> None:
    if getattr(app.state, "_aquatwin_zero_trust_attached", False):
        return
    app.state._aquatwin_zero_trust_attached = True

    default_hosts = [
        "localhost",
        "127.0.0.1",
        "testserver",
        "aquatwin-ai-api.onrender.com",
        "*.onrender.com",
    ]
    extra = [h.strip() for h in os.getenv("AQUATWIN_TRUSTED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=default_hosts + extra)
    app.add_middleware(ZeroTrustMiddleware)
