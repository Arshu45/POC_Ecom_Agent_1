"""SQLAlchemy database models."""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Category(Base):
    """Category model."""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    parent_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")


class Product(Base):
    """Product model."""
    __tablename__ = "products"
    
    product_id = Column(String(50), primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    brand = Column(String(255), nullable=True, index=True)
    product_type = Column(String(255), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    currency = Column(String(10), default="INR")
    stock_status = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="products")
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class ProductAttribute(Base):
    """Product attribute model (key-value pairs for all other CSV columns)."""
    __tablename__ = "product_attributes"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(50), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name = Column(String(255), nullable=False, index=True)
    attribute_value = Column(Text, nullable=True)
    attribute_type = Column(String(50), nullable=True)  # 'string', 'number', 'boolean', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="attributes")


class ProductImage(Base):
    """Product image model."""
    __tablename__ = "product_images"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(50), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(1000), nullable=False)
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="images")

