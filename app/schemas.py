"""Pydantic schemas for request/response models."""

from typing import Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request schema for search endpoint."""
    query: str = Field(..., description="User search query", min_length=1, max_length=500)


class SearchResponse(BaseModel):
    """Response schema for search endpoint."""
    response_text: str = Field(..., description="Chatbot response text")
    success: bool = Field(True, description="Whether the request was successful")
    error_message: Optional[str] = Field(None, description="Error message if request failed")

