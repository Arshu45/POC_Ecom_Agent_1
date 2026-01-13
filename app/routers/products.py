"""Product API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.models import Product, ProductAttribute, ProductImage, Category
from app.schemas import ProductListItem, ProductDetail, ProductListResponse

router = APIRouter(prefix="/products", tags=["products"])


def get_primary_image_url(product_id: str, db: Session) -> Optional[str]:
    """Get primary image URL for a product."""
    image = db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.is_primary == True
    ).first()
    return image.image_url if image else None


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    stock_status: Optional[str] = Query(None, description="Filter by stock status"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    sort_by: str = Query("product_id", description="Sort field (product_id, price, title)"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """
    List all products with filtering and sorting.
    
    Supports filtering by:
    - brand
    - stock_status
    - category_id
    - price range (min_price, max_price)
    
    Supports sorting by:
    - product_id
    - price
    - title
    """
    # Build query
    query = db.query(Product)
    
    # Apply filters
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    
    if stock_status:
        query = query.filter(Product.stock_status.ilike(f"%{stock_status}%"))
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    # Apply sorting
    if sort_by == "price":
        order_by = Product.price.desc() if sort_order == "desc" else Product.price.asc()
    elif sort_by == "title":
        order_by = Product.title.desc() if sort_order == "desc" else Product.title.asc()
    else:  # product_id
        order_by = Product.product_id.desc() if sort_order == "desc" else Product.product_id.asc()
    
    query = query.order_by(order_by)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    products = query.offset(offset).limit(page_size).all()
    
    # Format response
    product_items = []
    for product in products:
        primary_image = get_primary_image_url(product.product_id, db)
        product_items.append(ProductListItem(
            product_id=product.product_id,
            title=product.title,
            brand=product.brand,
            product_type=product.product_type,
            price=product.price,
            mrp=product.mrp,
            discount_percent=product.discount_percent,
            currency=product.currency,
            stock_status=product.stock_status,
            primary_image=primary_image
        ))
    
    return ProductListResponse(
        products=product_items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Get single product details with all attributes.
    """
    product = db.query(Product).filter(Product.product_id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Get related data
    attributes = db.query(ProductAttribute).filter(
        ProductAttribute.product_id == product_id
    ).all()
    
    images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.display_order, ProductImage.is_primary.desc()).all()
    
    category = None
    if product.category_id:
        category = db.query(Category).filter(Category.id == product.category_id).first()
    
    # Build response
    primary_image = get_primary_image_url(product_id, db)
    
    return ProductDetail(
        product_id=product.product_id,
        title=product.title,
        brand=product.brand,
        product_type=product.product_type,
        price=product.price,
        mrp=product.mrp,
        discount_percent=product.discount_percent,
        currency=product.currency,
        stock_status=product.stock_status,
        primary_image=primary_image,
        category=category,
        attributes=attributes,
        images=images,
        created_at=product.created_at,
        updated_at=product.updated_at
    )

