from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..routes import require_role, get_current_user
from ..db import list_all_users, set_user_active, set_user_role, delete_user, admin_reset_user_password
from ..security import hash_password
from ingestion.trace_store import (
    get_latency_percentiles, get_failure_rates,
    get_token_usage_by_model, get_usage_by_user, get_node_wall_latency
)
from ingestion.pricing import calculate_cost
from ...chat_history.db import get_daily_activity

router = APIRouter(prefix="/admin", tags=["admin"])


# --- analytics ---
@router.get("/stats/latency")
def latency_stats(hours: int = 24, admin: dict = Depends(require_role("admin"))):
    return get_latency_percentiles(hours)


@router.get("/stats/failures")
def failure_stats(hours: int = 24, admin: dict = Depends(require_role("admin"))):
    return get_failure_rates(hours)


@router.get("/stats/costs")
def cost_stats(hours: int = 24, admin: dict = Depends(require_role("admin"))):
    usage = get_token_usage_by_model(hours)
    for row in usage:
        row["estimated_cost_usd"] = round(
            calculate_cost(row["model"], row["total_input_tokens"] or 0, row["total_output_tokens"] or 0), 4
        )
    return usage


@router.get("/stats/users")
def user_usage_stats(hours: int = 24, admin: dict = Depends(require_role("admin"))):
    return get_usage_by_user(hours)


@router.get("/stats/activity")
def daily_activity(days: int = 14, admin: dict = Depends(require_role("admin"))):
    return get_daily_activity(days)

@router.get("/stats/wall-latency")
def wall_latency_stats(hours: int = 24, admin: dict = Depends(require_role("admin"))):
    return get_node_wall_latency(hours)


# --- user management ---
@router.get("/users")
def get_all_users(admin: dict = Depends(require_role("admin"))):
    return list_all_users()


class SetActiveRequest(BaseModel):
    is_active: bool

@router.patch("/users/{user_id}/active")
def toggle_user_active(user_id: str, req: SetActiveRequest, admin: dict = Depends(require_role("admin"))):
    set_user_active(user_id, req.is_active)
    return {"status": "updated"}


class SetRoleRequest(BaseModel):
    role: str  # "user" | "admin"

@router.patch("/users/{user_id}/role")
def toggle_user_role(user_id: str, req: SetRoleRequest, admin: dict = Depends(require_role("admin")), current: dict = Depends(get_current_user)):
    if str(current["id"]) == user_id and req.role != "admin":
        raise HTTPException(status_code=400, detail="Can't demote your own account")
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    set_user_role(user_id, req.role)
    return {"status": "updated"}


class AdminResetPasswordRequest(BaseModel):
    new_password: str

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, req: AdminResetPasswordRequest, admin: dict = Depends(require_role("admin"))):
    admin_reset_user_password(user_id, hash_password(req.new_password))
    return {"status": "password reset"}


@router.delete("/users/{user_id}")
def remove_user(user_id: str, admin: dict = Depends(require_role("admin")), current: dict = Depends(get_current_user)):
    if str(current["id"]) == user_id:
        raise HTTPException(status_code=400, detail="Can't delete your own account")
    delete_user(user_id)
    return {"status": "deleted"}