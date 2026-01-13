"""Migration script to import CSV data into PostgreSQL database."""

import os
import pandas as pd
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Product, Category, ProductAttribute, ProductImage

# CSV file path
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "catalog_corrected.csv")

# Core columns that go directly to products table
CORE_COLUMNS = [
    "product_id",
    "title",
    "brand",
    "product_type",
    "price",
    "mrp",
    "discount_percent",
    "currency",
    "stock_status"
]

# Columns to exclude from attributes (already in products or special handling)
EXCLUDE_COLUMNS = CORE_COLUMNS + ["keyword_tags", "embedding_text"]


def get_or_create_category(db: Session, category_name: str) -> Category:
    """Get or create a category."""
    if not category_name or pd.isna(category_name):
        return None
    
    category = db.query(Category).filter(Category.name == str(category_name).strip()).first()
    if not category:
        category = Category(name=str(category_name).strip())
        db.add(category)
        db.commit()
        db.refresh(category)
    return category


def migrate_csv_to_db():
    """Migrate CSV data to PostgreSQL database."""
    print("📂 Reading CSV file...")
    df = pd.read_csv(CSV_FILE_PATH).fillna("")
    
    print(f"✅ Loaded {len(df)} products from CSV")
    print("🗄️  Initializing database...")
    init_db()
    
    db: Session = SessionLocal()
    
    try:
        # Track categories
        categories_created = set()
        
        for idx, row in df.iterrows():
            try:
                # Extract core product data
                product_id = str(row["product_id"]).strip()
                
                # Get or create category from product_type
                category = None
                if "product_type" in row and not pd.isna(row["product_type"]):
                    product_type = str(row["product_type"]).strip()
                    category = get_or_create_category(db, product_type)
                    if category:
                        categories_created.add(category.name)
                
                # Create product
                product = Product(
                    product_id=product_id,
                    title=str(row["title"]).strip() if not pd.isna(row.get("title")) else "",
                    brand=str(row["brand"]).strip() if not pd.isna(row.get("brand")) else None,
                    product_type=str(row["product_type"]).strip() if not pd.isna(row.get("product_type")) else None,
                    category_id=category.id if category else None,
                    price=float(row["price"]) if not pd.isna(row.get("price")) else 0.0,
                    mrp=float(row["mrp"]) if not pd.isna(row.get("mrp")) else None,
                    discount_percent=float(row["discount_percent"]) if not pd.isna(row.get("discount_percent")) else None,
                    currency=str(row["currency"]).strip() if not pd.isna(row.get("currency")) else "INR",
                    stock_status=str(row["stock_status"]).strip() if not pd.isna(row.get("stock_status")) else None
                )
                
                db.add(product)
                db.flush()  # Get product_id without committing
                
                # Add all other columns as attributes
                for col_name, col_value in row.items():
                    if col_name in EXCLUDE_COLUMNS:
                        continue
                    
                    # Skip empty values
                    if pd.isna(col_value) or str(col_value).strip() == "":
                        continue
                    
                    # Determine attribute type
                    value_str = str(col_value).strip()
                    if value_str.lower() in ["true", "false", "yes", "no"]:
                        attr_type = "boolean"
                    elif value_str.replace(".", "").replace("-", "").isdigit():
                        attr_type = "number"
                    else:
                        attr_type = "string"
                    
                    # Create attribute
                    attribute = ProductAttribute(
                        product_id=product_id,
                        attribute_name=col_name,
                        attribute_value=value_str,
                        attribute_type=attr_type
                    )
                    db.add(attribute)
                
                # Add placeholder image (can be updated later)
                image = ProductImage(
                    product_id=product_id,
                    image_url=f"https://via.placeholder.com/400x400?text={product_id}",
                    is_primary=True,
                    display_order=0
                )
                db.add(image)
                
                if (idx + 1) % 10 == 0:
                    print(f"  Processed {idx + 1}/{len(df)} products...")
                    db.commit()
                
            except Exception as e:
                print(f"❌ Error processing row {idx + 1} (product_id: {row.get('product_id', 'unknown')}): {e}")
                db.rollback()
                continue
        
        # Final commit
        db.commit()
        print(f"\n✅ Migration complete!")
        print(f"   - Products: {db.query(Product).count()}")
        print(f"   - Categories: {db.query(Category).count()}")
        print(f"   - Attributes: {db.query(ProductAttribute).count()}")
        print(f"   - Images: {db.query(ProductImage).count()}")
        print(f"   - Categories created: {', '.join(sorted(categories_created))}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_csv_to_db()

