"""Admin authentication dependencies.
Completely separate from client/vendor auth."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.admin_token_fingerprint import verify_pwf, PWF_CLAIM
from app.models.admin_user import AdminUser

admin_security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: AsyncSession = Depends(get_db)
) -> AdminUser:
    """Dependency to get current authenticated admin from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    user_type = payload.get("type")

    if user_id is None or user_type != "admin":
        raise credentials_exception

    result = await db.execute(
        select(AdminUser).where(AdminUser.admin_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if admin is None or not admin.is_active:
        raise credentials_exception

    # Verify password-state fingerprint.  Constant-time comparison; missing,
    # malformed or mismatched claim yields the same 401 as any other failure.
    # RuntimeError means JWT_SECRET_KEY is absent/insecure — treat as 401
    # (fail closed: the token cannot be validated, same outcome as mismatch).
    try:
        pwf_valid = verify_pwf(payload.get(PWF_CLAIM), admin.password_hash)
    except RuntimeError:
        raise credentials_exception  # 401 — fail closed, no secret in message
    if not pwf_valid:
        raise credentials_exception

    return admin
