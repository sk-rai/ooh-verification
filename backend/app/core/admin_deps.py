"""Admin authentication dependencies.
Completely separate from client/vendor auth."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
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

    return admin
