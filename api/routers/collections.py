"""Tenant-scoped document collections."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, require_admin
from api.db import get_conn
from api.rbac import get_accessible_document_ids, user_has_document_management_access
from api.schemas import CollectionCreate, CollectionResponse, CollectionUpdate

router = APIRouter(prefix="/collections", tags=["collections"])

DEFAULT_COLLECTION_COLORS = ["#4f8cff", "#35d0ba", "#8b5cf6", "#f97316", "#ec4899", "#22c55e"]


def _row_to_collection(row) -> CollectionResponse:
    return CollectionResponse(
        id=str(row[0]),
        tenant_id=str(row[1]),
        name=row[2],
        description=row[3],
        color=row[4] or DEFAULT_COLLECTION_COLORS[0],
        document_count=int(row[5] or 0),
        ready_count=int(row[6] or 0),
        created_at=str(row[7]),
        updated_at=str(row[8]) if row[8] else None,
    )


@router.get("", response_model=list[CollectionResponse])
async def list_collections(user: dict = Depends(get_current_user)):
    """List collections for the current tenant with document readiness counts."""
    tenant_id = user["tenant_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user.get("role") == "admin":
                cur.execute(
                    """
                    SELECT c.id, c.tenant_id, c.name, c.description, c.color,
                           COUNT(d.id) AS document_count,
                           COUNT(d.id) FILTER (WHERE d.status='ready') AS ready_count,
                           c.created_at, c.updated_at
                    FROM collections c
                    LEFT JOIN documents d ON d.collection_id = c.id AND d.tenant_id = c.tenant_id
                    WHERE c.tenant_id=%s
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    """,
                    (tenant_id,),
                )
            else:
                accessible_ids = get_accessible_document_ids(user["id"], tenant_id, conn)
                if accessible_ids:
                    cur.execute(
                        """
                        SELECT c.id, c.tenant_id, c.name, c.description, c.color,
                               COUNT(d.id) AS document_count,
                               COUNT(d.id) FILTER (WHERE d.status='ready') AS ready_count,
                               c.created_at, c.updated_at
                        FROM collections c
                        LEFT JOIN documents d
                          ON d.collection_id = c.id
                         AND d.tenant_id = c.tenant_id
                         AND d.id = ANY(%s)
                        WHERE c.tenant_id=%s
                        GROUP BY c.id
                        ORDER BY c.created_at DESC
                        """,
                        (accessible_ids, tenant_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT c.id, c.tenant_id, c.name, c.description, c.color,
                               0 AS document_count, 0 AS ready_count,
                               c.created_at, c.updated_at
                        FROM collections c
                        WHERE c.tenant_id=%s
                        ORDER BY c.created_at DESC
                        """,
                        (tenant_id,),
                    )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [_row_to_collection(row) for row in rows]


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(body: CollectionCreate, user: dict = Depends(require_admin)):
    """Create a collection for the current tenant."""
    tenant_id = user["tenant_id"]
    color_index = sum(ord(ch) for ch in body.name) % len(DEFAULT_COLLECTION_COLORS)
    color = body.color or DEFAULT_COLLECTION_COLORS[color_index]
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collections (tenant_id, name, description, color)
                VALUES (%s, %s, %s, %s)
                RETURNING id, tenant_id, name, description, color,
                          0 AS document_count, 0 AS ready_count, created_at, updated_at
                """,
                (tenant_id, body.name.strip(), body.description, color),
            )
            row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Collection could not be created") from exc
    finally:
        conn.close()

    return _row_to_collection(row)


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    body: CollectionUpdate,
    user: dict = Depends(require_admin),
):
    """Update collection metadata."""
    fields = []
    values = []
    if body.name is not None:
        fields.append("name=%s")
        values.append(body.name.strip())
    if body.description is not None:
        fields.append("description=%s")
        values.append(body.description)
    if body.color is not None:
        fields.append("color=%s")
        values.append(body.color)
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    values.extend([collection_id, user["tenant_id"]])
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE collections
                SET {', '.join(fields)}, updated_at=NOW()
                WHERE id=%s AND tenant_id=%s
                RETURNING id
                """,
                tuple(values),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Collection not found")
            cur.execute(
                """
                SELECT c.id, c.tenant_id, c.name, c.description, c.color,
                       COUNT(d.id), COUNT(d.id) FILTER (WHERE d.status='ready'),
                       c.created_at, c.updated_at
                FROM collections c
                LEFT JOIN documents d ON d.collection_id = c.id AND d.tenant_id = c.tenant_id
                WHERE c.id=%s AND c.tenant_id=%s
                GROUP BY c.id
                """,
                (collection_id, user["tenant_id"]),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_collection(row)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: str, user: dict = Depends(require_admin)):
    """Delete a collection. Documents remain available and become unassigned."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM collections WHERE id=%s AND tenant_id=%s",
                (collection_id, user["tenant_id"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Collection not found")
    finally:
        conn.close()


@router.post("/{collection_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_document_to_collection(
    collection_id: str,
    doc_id: str,
    user: dict = Depends(get_current_user),
):
    """Assign a document to a collection when the user can manage the document."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM collections WHERE id=%s AND tenant_id=%s",
                (collection_id, user["tenant_id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Collection not found")
            if not user_has_document_management_access(user, doc_id, conn, required_level="editor"):
                raise HTTPException(status_code=403, detail="Document editor or admin access required")
            cur.execute(
                "UPDATE documents SET collection_id=%s WHERE id=%s AND tenant_id=%s",
                (collection_id, doc_id, user["tenant_id"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Document not found")
    finally:
        conn.close()
