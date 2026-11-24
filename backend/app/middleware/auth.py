# ============================================================
# app/middleware/auth.py — JWT Authentication Middleware
#
# ARCHITECT'S NOTE:
#   FastAPI uses a "dependency injection" pattern for auth.
#   Instead of a traditional middleware that wraps every route,
#   we define reusable dependency functions that routes opt into.
#
#   This gives us three levels of protection:
#     - get_current_user       → any authenticated user
#     - require_team_admin     → team admins and above
#     - require_super_admin    → platform-wide admins only
#
#   Usage in a route:
#     @router.get("/protected")
#     async def protected(user: TokenData = Depends(get_current_user)):
#         return {"user_id": user.user_id}
# ============================================================

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.schemas.auth import TokenData
from app.services.auth_service import decode_access_token


# HTTPBearer extracts the token from the "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    """
    Validate the JWT Bearer token and return the decoded user data.
    Raises 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials

    token_data = decode_access_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def require_team_admin(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    """
    Require the user to be at least a team admin.
    Use this on team management endpoints.
    """
    if current_user.role not in ("team_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team admin privileges required.",
        )
    return current_user


async def require_super_admin(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    """
    Require super_admin role.
    Use this on platform-wide admin endpoints (user creation, team creation).
    """
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required.",
        )
    return current_user
