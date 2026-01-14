"""Migration script to import CSV data into PostgreSQL database."""

import os
import pandas as pd
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Product, Category, Attribute, AttributeValue, AttributeOption, ProductImage, AttributeDataType

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

# Define ENUM columns (should have dropdowns)
ENUM_COLUMNS = {
    'age_group', 'gender', 'primary_fabric', 'secondary_fabric', 
    'transparency', 'fabric_stretch', 'fit_type', 'length', 
    'sleeves', 'neckline', 'closure_type', 'hemline', 'waist_type',
    'pattern', 'embellishment', 'color', 'color_family', 
    'surface_styling', 'occasion', 'lining', 'weight', 
    'safety_compliance', 'size'
}

# Columns to exclude from attributes
EXCLUDE_COLUMNS = CORE_COLUMNS + ["embedding_text"]


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


def get_or_create_attribute(db: Session, attribute_name: str, data_type: AttributeDataType) -> Attribute:
    """Get or create an attribute."""
    if not attribute_name:
        return None
    
    attribute = db.query(Attribute).filter(Attribute.name == attribute_name).first()
    if not attribute:
        attribute = Attribute(
            name=attribute_name,
            data_type=data_type
        )
        db.add(attribute)
        db.commit()
        db.refresh(attribute)
    return attribute


def determine_attribute_type(col_name: str, value) -> AttributeDataType:
    """Determine attribute data type from column name and value."""
    if pd.isna(value) or str(value).strip() == "":
        # Default based on column name if value is empty
        if col_name in ENUM_COLUMNS:
            return AttributeDataType.ENUM
        return AttributeDataType.STRING
    
    # Check if column should be ENUM
    if col_name in ENUM_COLUMNS:
        return AttributeDataType.ENUM
    
    value_str = str(value).strip().lower()
    
    # Check for boolean
    if value_str in ["true", "false", "yes", "no", "1", "0"]:
        return AttributeDataType.BOOLEAN
    
    # Check for number
    try:
        float(value)
        return AttributeDataType.NUMBER
    except (ValueError, TypeError):
        pass
    
    # Default to string
    return AttributeDataType.STRING


def convert_value_to_appropriate_type(value, data_type: AttributeDataType):
    """Convert value to appropriate type for storage."""
    if pd.isna(value) or str(value).strip() == "":
        return None, None, None
    
    value_str = str(value).strip()
    
    if data_type == AttributeDataType.BOOLEAN:
        bool_val = value_str.lower() in ["true", "yes", "1"]
        return None, None, bool_val
    elif data_type == AttributeDataType.NUMBER:
        try:
            num_val = float(value)
            return None, num_val, None
        except (ValueError, TypeError):
            return value_str, None, None
    else:  # STRING or ENUM
        return value_str, None, None


def populate_attribute_options(db: Session, df: pd.DataFrame):
    """Populate attribute_option table for ENUM attributes."""
    print("📋 Creating attribute options for ENUM attributes...")
    
    for col_name in ENUM_COLUMNS:
        if col_name not in df.columns:
            continue
        
        # Get unique non-null values for this column
        unique_values = df[col_name].dropna().unique()
        
        # Get the attribute
        attribute = db.query(Attribute).filter(Attribute.name == col_name).first()
        if not attribute:
            continue
        
        # Create options
        for idx, value in enumerate(sorted(unique_values)):
            value_str = str(value).strip()
            if not value_str:
                continue
            
            # Check if option already exists
            existing = db.query(AttributeOption).filter(
                AttributeOption.attribute_id == attribute.attribute_id,
                AttributeOption.option_value == value_str
            ).first()
            
            if not existing:
                option = AttributeOption(
                    attribute_id=attribute.attribute_id,
                    option_value=value_str,
                    display_order=idx
                )
                db.add(option)
        
        db.commit()
    
    print(f"✅ Created {db.query(AttributeOption).count()} attribute options")


def migrate_csv_to_db():
    """Migrate CSV data to PostgreSQL database."""
    print("📂 Reading CSV file...")
    df = pd.read_csv(CSV_FILE_PATH).fillna("")
    
    print(f"✅ Loaded {len(df)} products from CSV")
    print(f"📊 CSV has {len(df.columns)} columns")
    print("🗄️  Initializing database...")
    init_db()
    
    db: Session = SessionLocal()
    
    try:
        # Track statistics
        categories_created = set()
        
        # PHASE 1: Create products and attribute values
        print("\n📦 Phase 1: Creating products and attributes...")
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
                db.flush()
                
                # Add all other columns as attributes
                for col_name, col_value in row.items():
                    if col_name in EXCLUDE_COLUMNS:
                        continue
                    
                    # Skip empty values
                    if pd.isna(col_value) or str(col_value).strip() == "":
                        continue
                    
                    # Determine attribute data type
                    data_type = determine_attribute_type(col_name, col_value)
                    
                    # Get or create attribute definition
                    attribute = get_or_create_attribute(db, col_name, data_type)
                    if not attribute:
                        continue
                    
                    # Convert value to appropriate type
                    value_string, value_number, value_boolean = convert_value_to_appropriate_type(col_value, data_type)
                    
                    # Create attribute value
                    attribute_value = AttributeValue(
                        product_id=product_id,
                        attribute_id=attribute.attribute_id,
                        value_string=value_string,
                        value_number=value_number,
                        value_boolean=value_boolean
                    )
                    db.add(attribute_value)
                
                # Add placeholder image
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
        
        db.commit()
        
        # PHASE 2: Populate attribute options for ENUM attributes
        print("\n📋 Phase 2: Creating attribute options...")
        populate_attribute_options(db, df)
        
        # Final summary
        print(f"\n✅ Migration complete!")
        print(f"   📦 Products: {db.query(Product).count()}")
        print(f"   📁 Categories: {db.query(Category).count()} ({', '.join(sorted(categories_created))})")
        print(f"   🏷️  Attributes: {db.query(Attribute).count()}")
        print(f"   💾 Attribute Values: {db.query(AttributeValue).count()}")
        print(f"   📋 Attribute Options: {db.query(AttributeOption).count()}")
        print(f"   🖼️  Images: {db.query(ProductImage).count()}")
        
        # Show ENUM attributes created
        enum_attrs = db.query(Attribute).filter(Attribute.data_type == AttributeDataType.ENUM).all()
        print(f"\n📋 ENUM Attributes Created ({len(enum_attrs)}):")
        for attr in enum_attrs:
            option_count = db.query(AttributeOption).filter(
                AttributeOption.attribute_id == attr.attribute_id
            ).count()
            print(f"   - {attr.name}: {option_count} options")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_csv_to_db()

