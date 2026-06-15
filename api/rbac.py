"""Document-level role-based access control."""

import logging

logger = logging.getLogger(__name__)

PERMISSION_LEVELS = ("viewer", "editor", "owner")
_LEVEL_RANK = {level: i for i, level in enumerate(PERMISSION_LEVELS)}


def check_document_access(user_id: str, document_id: str, required_level: str, conn) -> bool:
    """Check if user has at least the required permission level on a document."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT permission_level FROM document_permissions WHERE document_id=%s AND user_id=%s",
            (document_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return False
        return _LEVEL_RANK.get(row[0], -1) >= _LEVEL_RANK.get(required_level, 999)


def user_has_document_access(user: dict, document_id: str, conn, required_level: str = "viewer") -> bool:
    """Check document access with admin bypass and legacy fallback.

    Documents that have no ACL rows yet remain tenant-visible so existing
    deployments do not lose access immediately. Once a document has at least
    one ACL row, explicit permissions are enforced for non-admin users.
    """
    if user.get("role") == "admin":
        return True

    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM document_permissions WHERE document_id=%s)", (document_id,))
        row = cur.fetchone()
    has_acl = bool(row and row[0])
    if not has_acl:
        return True

    return check_document_access(user["id"], document_id, required_level, conn)


def user_has_document_management_access(user: dict, document_id: str, conn, required_level: str = "owner") -> bool:
    """Check write/manage access without the legacy-read fallback."""
    if user.get("role") == "admin":
        return True
    return check_document_access(user["id"], document_id, required_level, conn)


def grant_access(document_id: str, user_id: str, level: str, granted_by: str, conn):
    """Grant or update access level for a user on a document."""
    if level not in PERMISSION_LEVELS:
        raise ValueError(f"Invalid permission level: {level}. Must be one of {PERMISSION_LEVELS}")
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO document_permissions (document_id, user_id, permission_level, granted_by)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (document_id, user_id)
               DO UPDATE SET permission_level = EXCLUDED.permission_level, granted_by = EXCLUDED.granted_by""",
            (document_id, user_id, level, granted_by),
        )


def revoke_access(document_id: str, user_id: str, conn) -> bool:
    """Revoke user's access to a document. Returns True if a row was deleted."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM document_permissions WHERE document_id=%s AND user_id=%s",
            (document_id, user_id),
        )
        return cur.rowcount > 0


def get_accessible_document_ids(user_id: str, tenant_id: str, conn) -> list[str]:
    """Get all document IDs a non-admin user can access within a tenant.

    Legacy documents with no ACL rows remain visible to all tenant members.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id
            FROM documents d
            WHERE d.tenant_id=%s
              AND (
                NOT EXISTS (
                    SELECT 1 FROM document_permissions dp_any
                    WHERE dp_any.document_id = d.id
                )
                OR EXISTS (
                    SELECT 1 FROM document_permissions dp_user
                    WHERE dp_user.document_id = d.id
                      AND dp_user.user_id=%s
                      AND dp_user.permission_level IN ('viewer', 'editor', 'owner')
                )
              )
            ORDER BY d.created_at DESC
            """,
            (tenant_id, user_id),
        )
        return [str(row[0]) for row in cur.fetchall()]


def list_document_permissions(document_id: str, conn) -> list[dict]:
    """List all permissions for a document."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT user_id, permission_level, granted_by, created_at
               FROM document_permissions WHERE document_id=%s ORDER BY created_at""",
            (document_id,),
        )
        return [
            {"user_id": r[0], "level": r[1], "granted_by": r[2], "created_at": str(r[3])}
            for r in cur.fetchall()
        ]
