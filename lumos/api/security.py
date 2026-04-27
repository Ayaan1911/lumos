import hmac

from fastapi import Header, HTTPException, status

from lumos.config import settings


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = _bearer_token(authorization)
    if not settings.admin_token or token is None or not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin authorization required",
        )


def session_token_from_header(authorization: str | None) -> str:
    token = _bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session authorization required",
        )
    return token
