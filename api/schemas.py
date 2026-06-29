"""Pydantic request/response models for the TurkRAG API."""

import re

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    session_id: str | None = None  # omit to start a new session


class ChatStreamRequest(QueryRequest):
    token: str = Field(..., min_length=1, max_length=8192)


class CitationSource(BaseModel):
    filename: str
    chunk_index: int
    text_preview: str        # first 120 chars
    score: float | None = None  # reranker score; None for legacy/loaded sessions


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationSource]
    query_time_ms: int
    tenant_id: str
    session_id: str        # continue the conversation
    message_id: str | None = None  # assistant message DB id — used for feedback


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str | None = None
    filename: str
    status: str


class DocumentListItem(BaseModel):
    id: str
    filename: str
    chunk_count: int | None
    status: str
    created_at: str
    collection_id: str | None = None
    collection_name: str | None = None
    file_type: str | None = None
    size_bytes: int | None = None


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    color: str | None = Field(default=None, max_length=24)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    color: str | None = Field(default=None, max_length=24)


class CollectionResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None = None
    color: str
    document_count: int = 0
    ready_count: int = 0
    created_at: str
    updated_at: str | None = None


class UiSettings(BaseModel):
    default_model: str = Field(default="turkrag-model", max_length=80)
    default_language: str = Field(default="tr", pattern="^(tr|en|auto)$")
    hybrid_search: bool = True
    results_per_page: int = Field(default=10, ge=5, le=50)
    notifications_enabled: bool = True
    theme: str = Field(default="dark", pattern="^(dark|light|system)$")


class UiSettingsResponse(UiSettings):
    updated_at: str | None = None


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50)

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
            raise ValueError("slug must be lowercase alphanumeric with hyphens, no leading/trailing hyphens")
        return v


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: str


class DevTokenRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)


class MockAdminLoginRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AdminTenantSwitchRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserCreateRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    role: str = Field(default="member", pattern="^(admin|member)$")


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    is_active: bool
    created_at: str


class AuthUser(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    is_active: bool


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    postgres: str
    llm_available: bool
    redis: str = "not_configured"
    worker: str = "unknown"
    uptime_seconds: int | None = None
    details: dict = Field(default_factory=dict)
    version: str = "1.0.0"
