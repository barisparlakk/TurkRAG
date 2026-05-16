"""Pydantic request/response models for the TurkRAG API."""

import re

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    session_id: str | None = None  # omit to start a new session


class CitationSource(BaseModel):
    filename: str
    chunk_index: int
    text_preview: str  # first 120 chars


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationSource]
    query_time_ms: int
    tenant_id: str
    session_id: str        # continue the conversation
    message_id: str | None = None  # assistant message DB id — used for feedback


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str


class DocumentListItem(BaseModel):
    id: str
    filename: str
    chunk_count: int | None
    status: str
    created_at: str


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


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    postgres: str
    llm_available: bool
    version: str = "1.0.0"
