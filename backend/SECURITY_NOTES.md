# API hardening notes

## In-memory state and deployment limits
- Session, anti-replay (nonce cache) and rate-limiting data are stored in local process memory only. Restarting the process clears this state and signs out users. Running multiple workers would require shared storage to maintain protections.
- The platform already terminates TLS; cookies are still marked `Secure` when `APP_ENV=prod`.

## Environment variables
- `SESSION_TTL` (default: `1800` seconds) controls sliding session expiration.
- `FRESHNESS_WINDOW` (default: `300` seconds) limits the acceptable drift for replay-protected timestamps and nonce retention.
- `RATE_LIMIT_RPS` (default: `10.0`) defines requests-per-second for the in-memory token bucket (burst = `2 × RPS`).
- `APP_ENV` toggles Secure cookies when set to `prod`.
- `EXPOSE_CSRF_SEED` remains disabled by default; no public seeding endpoint has been added.

## Middleware order
Middleware is mounted in the following order:
1. `RateLimitMiddleware`
2. `AntiReplayMiddleware`
3. `SessionMiddleware`
4. Application-level middleware (request logging, CSRF seeding helper, etc.)

This ensures rate limiting and replay checks run before sessions are materialised, as requested.

## CSRF handling
- A double-submit cookie named `csrftoken` is issued automatically when missing.
- Mutable routes require both the cookie and `X-CSRF-Token` header with matching values.
- Helper `ensure_csrf_cookie(...)` can be called manually if future private routes need to refresh or rotate the token.

## Session lifecycle
- Every request refreshes the sliding TTL and re-sets the `sid` cookie with `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
- Login flows should call `core.sessions.rotate_sid(...)` and set the returned cookie to prevent fixation.
- Logout handlers should delete the stored session (`core.sessions.SESSIONS.pop(sid, None)`) and clear the cookie.

## Replay and rate limiting
- Nonces are single-use within the freshness window; reuse or stale timestamps lead to `401` responses.
- Rate limiting returns `429` when the per-IP budget is exhausted and replenishes tokens over time.

Logging avoids emitting sensitive header or cookie contents; only client IPs, SID prefixes, and rejection reasons are recorded.
