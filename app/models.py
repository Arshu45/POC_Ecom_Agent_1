"""SQLAlchemy database models."""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Text, Enum, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class AttributeDataType(enum.Enum):
    """Attribute data type enumeration."""
    STRING = 'string'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    ENUM = 'enum'


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
    attribute_values = relationship("AttributeValue", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class Attribute(Base):
    """Attribute model - defines attribute metadata."""
    __tablename__ = "attributes"
    
    attribute_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    data_type = Column(Enum(AttributeDataType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    attribute_values = relationship("AttributeValue", back_populates="attribute", cascade="all, delete-orphan")
    options = relationship("AttributeOption", back_populates="attribute", cascade="all, delete-orphan")


class AttributeValue(Base):
    """AttributeValue model - stores actual attribute values for products."""
    __tablename__ = "attribute_values"
    
    value_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(String(50), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_id = Column(Integer, ForeignKey("attributes.attribute_id", ondelete="CASCADE"), nullable=False, index=True)
    value_string = Column(String(255), nullable=True)
    value_number = Column(Numeric(10, 2), nullable=True)
    value_boolean = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Unique constraint: one value per product per attribute
    __table_args__ = (
        UniqueConstraint('product_id', 'attribute_id', name='uq_product_attribute'),
    )
    
    # Relationships
    product = relationship("Product", back_populates="attribute_values")
    attribute = relationship("Attribute", back_populates="attribute_values")


class AttributeOption(Base):
    """AttributeOption model - stores options for enum-type attributes."""
    __tablename__ = "attribute_options"
    
    option_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    attribute_id = Column(Integer, ForeignKey("attributes.attribute_id", ondelete="CASCADE"), nullable=False, index=True)
    option_value = Column(String(100), nullable=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    attribute = relationship("Attribute", back_populates="options")


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

