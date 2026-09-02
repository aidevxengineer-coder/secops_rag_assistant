from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from .schemas import RegisterRequest, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, UserOut
from .security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, generate_reset_token, hash_reset_token,
)
from .db import (
    get_user_by_email, get_user_by_id, create_user, store_reset_token,
    get_valid_reset, mark_reset_used, update_password,
)
from .email_service import send_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


@router.post("/register", response_model=UserOut)
def register(req: RegisterRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(req.email, hash_password(req.password))
    return UserOut(id=str(user["id"]), email=user["email"], role=user["role"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, response: Response):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account has been disabled")

    access = create_access_token(str(user["id"]), user["role"])
    refresh = create_refresh_token(str(user["id"]), user["role"])

    response.set_cookie(
        REFRESH_COOKIE_NAME, refresh, httponly=True, secure=False,  # secure=True once on HTTPS in prod
        samesite="lax", max_age=60 * 60 * 24 * 7,
    )
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = get_user_by_id(payload["sub"])
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled or not found")
    access = create_access_token(payload["sub"], payload["role"])
    return TokenResponse(access_token=access)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"status": "logged out"}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    user = get_user_by_email(req.email)
    if user:
        raw, hashed = generate_reset_token()
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        store_reset_token(str(user["id"]), hashed, expires)
        try:
            send_reset_email(user["email"], raw)
        except Exception as e:
            print(f"[forgot_password] FAILED to send email to {user['email']}: {e}")
    else:
        print(f"[forgot_password] no user found for {req.email}")
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    token_hash = hash_reset_token(req.token)
    reset = get_valid_reset(token_hash)
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    update_password(str(reset["user_id"]), hash_password(req.new_password))
    mark_reset_used(str(reset["id"]))
    return {"message": "Password updated. You can now log in."}


def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(auth_header.removeprefix("Bearer "))
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account has been disabled")
    return user


def require_role(*roles: str):
    def _check(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _check


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(id=str(user["id"]), email=user["email"], role=user["role"])