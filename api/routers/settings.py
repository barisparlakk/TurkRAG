"""User interface settings for the dashboard."""

import json

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.db import get_conn
from api.schemas import UiSettings, UiSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_payload(raw: dict | None, updated_at=None) -> UiSettingsResponse:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    settings = UiSettings(**(raw or {}))
    return UiSettingsResponse(**settings.model_dump(), updated_at=str(updated_at) if updated_at else None)


@router.get("/ui", response_model=UiSettingsResponse)
async def get_ui_settings(user: dict = Depends(get_current_user)):
    """Return stored dashboard preferences for the current user and tenant."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT settings_json, updated_at
                   FROM tenant_ui_settings
                   WHERE tenant_id=%s AND user_id=%s""",
                (user["tenant_id"], user["id"]),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return _settings_payload(None)
    return _settings_payload(row[0], row[1])


@router.put("/ui", response_model=UiSettingsResponse)
async def update_ui_settings(body: UiSettings, user: dict = Depends(get_current_user)):
    """Persist safe dashboard preferences. Does not mutate model/runtime env."""
    payload = body.model_dump()
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_ui_settings (tenant_id, user_id, settings_json, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (tenant_id, user_id)
                DO UPDATE SET settings_json=EXCLUDED.settings_json, updated_at=NOW()
                RETURNING settings_json, updated_at
                """,
                (user["tenant_id"], user["id"], json.dumps(payload)),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return _settings_payload(row[0], row[1])
