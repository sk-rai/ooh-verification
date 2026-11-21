"""
Reusable CRON_SECRET authentication dependency for scheduled endpoints.

Usage:
    from app.core.cron_auth import require_cron_secret

    @router.post("/cron/my-job")
    async def my_job(db=Depends(get_db), _=Depends(require_cron_secret)):
        ...

The caller must supply the header:
    X-Cron-Secret: <value of CRON_SECRET env var>

Fail-closed:
  - If CRON_SECRET is not set in the environment, all cron calls are blocked.
  - If the header is absent, empty or wrong, 401 is returned.
  - Comparison is constant-time (hmac.compare_digest) to prevent timing attacks.
  - The secret is never logged.
"""
import hmac
import os

from fastapi import Header, HTTPException, status


def require_cron_secret(
    x_cron_secret: str = Header(
        default="",
        description="Shared cron secret — must match CRON_SECRET env var",
        alias="X-Cron-Secret",
    ),
) -> None:
    """FastAPI dependency that enforces the cron shared secret.

    Raises HTTP 401 if the secret is missing, empty or incorrect.
    Raises HTTP 503 if CRON_SECRET is not configured in the environment
    (fail-closed: an unconfigured server must not accept cron calls).
    """
    expected = os.getenv("CRON_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cron endpoint unavailable: CRON_SECRET is not configured on this server.",
        )
    if not x_cron_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Cron-Secret header is required.",
        )
    # Constant-time comparison — never use == for secrets.
    if not hmac.compare_digest(x_cron_secret.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron secret.",
        )
