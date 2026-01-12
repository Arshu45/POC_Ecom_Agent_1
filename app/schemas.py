"""Pydantic schemas for request/response models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request schema for search endpoint."""
    query: str = Field(..., description="User search query", min_length=1, max_length=500)


class ProductResult(BaseModel):
    """Product result schema with essential information only."""
    id: str = Field(..., description="Product ID")
    title: str = Field(..., description="Product title")
    price: str = Field(..., description="Formatted price string")
    key_features: List[str] = Field(default_factory=list, description="Key product features")


class SearchResponse(BaseModel):
    """Response schema for search endpoint."""
    response_text: str = Field(..., description="Chatbot response text with recommendations")
    products: List[ProductResult] = Field(default_factory=list, description="List of matching products")
    follow_up_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    success: bool = Field(True, description="Whether the request was successful")
    error_message: Optional[str] = Field(None, description="Error message if request failed")

