"""Pydantic request/response schemas for the API."""

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    topic: str = Field(default="", description="Topic context for the conversation")
    message: str = Field(..., min_length=1, description="User message")
    history: list[dict] = Field(default_factory=list, description="Previous turns")
    stream: bool = Field(default=True, description="Stream the response")
    use_rag: bool = Field(default=True, description="Use Qdrant RAG context")


class ImageRequest(BaseModel):
    topic: Optional[str] = Field(default=None, description="Search term for the image")
    context: Optional[str] = Field(
        default=None,
        description="Finished post text; ranks the candidates the topic found",
    )
    count: Optional[int] = Field(
        default=None, description="How many candidates to shortlist (/images only)"
    )


class EmoteRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to pick an emote for")


class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to ingest into Qdrant")


class RarePepeRequest(BaseModel):
    query: Optional[str] = Field(
        default="rare pepe",
        description="Search term for the rare pepe collection",
    )
    language: Optional[str] = Field(
        default=None,
        description="Target language for the description/explanation",
    )
    history: list[dict] = Field(
        default_factory=list,
        description="Previous conversation turns to infer user language",
    )


class EventRequest(BaseModel):
    event_type: str = Field(..., description="Type of event, e.g. command_click, message_send, feedback, conversion")
    command: Optional[str] = Field(default=None, description="Command identifier if applicable")
    message: Optional[str] = Field(default=None, description="User message if applicable")
    session_id: Optional[str] = Field(default=None, description="Frontend session cookie id")
    user_agent: Optional[str] = Field(default=None, description="Browser user agent string")
    feedback: Optional[str] = Field(default=None, description=" thumbs_up or thumbs_down")
    user_message: Optional[str] = Field(
        default=None, description="Preceding user message, for feedback events"
    )
    conversion_type: Optional[str] = Field(default=None, description="e.g. support, discord, faucet, wallet")
    latency_ms: Optional[int] = Field(default=None, description="Request latency in milliseconds")
    metadata: Optional[dict] = Field(default=None, description="Additional event metadata")
    wallet_address: Optional[str] = Field(default=None, description="Connected Peppool wallet address")


class ArtUpdateRequest(BaseModel):
    status: str = Field(..., description="Status (pending, approved, rejected)")
    label: str = Field(..., description="Label for the art")
