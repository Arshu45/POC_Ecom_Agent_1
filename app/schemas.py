"""Pydantic schemas for request/response models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================
# Agent Search Schemas
# ============================================================

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


# ============================================================
# Product API Schemas
# ============================================================

class CategoryResponse(BaseModel):
    """Category response schema."""
    id: int
    name: str
    parent_category_id: Optional[int] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ProductAttributeResponse(BaseModel):
    """Product attribute response schema."""
    id: int
    attribute_name: str
    attribute_value: Optional[str] = None
    attribute_type: Optional[str] = None

    class Config:
        from_attributes = True


class ProductImageResponse(BaseModel):
    """Product image response schema."""
    id: int
    image_url: str
    is_primary: bool
    display_order: int

    class Config:
        from_attributes = True


class ProductListItem(BaseModel):
    """Product list item schema (minimal info for listing)."""
    product_id: str
    title: str
    brand: Optional[str] = None
    product_type: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    discount_percent: Optional[float] = None
    currency: str
    stock_status: Optional[str] = None
    primary_image: Optional[str] = None

    class Config:
        from_attributes = True


class ProductDetail(ProductListItem):
    """Product detail schema (full product info)."""
    category: Optional[CategoryResponse] = None
    attributes: List[ProductAttributeResponse] = Field(default_factory=list)
    images: List[ProductImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Product list response schema."""
    products: List[ProductListItem]
    total: int
    page: int = 1
    page_size: int = 20

