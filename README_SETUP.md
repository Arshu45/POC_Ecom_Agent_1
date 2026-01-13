# E-commerce POC Setup Guide

## Prerequisites

1. PostgreSQL database installed and running
2. Python 3.12+ with virtual environment
3. All dependencies installed

## Database Setup

1. **Create PostgreSQL database:**
```bash
createdb ecommerce_db
# Or using psql:
psql -U postgres
CREATE DATABASE ecommerce_db;
```

2. **Set environment variables in `.env` file:**
```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecommerce_db

# Existing variables (keep your existing ones)
GROQ_API_KEY=your_key
CHROMA_DB_DIR=./chroma_db_ingest_few
COLLECTION_NAME=catalog_ai
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
# ... etc
```

## Installation

1. **Install dependencies:**
```bash
source env/bin/activate  # or your venv activation
pip install -r requirements.txt
```

2. **Run database migration:**
```bash
python migrate_csv_to_db.py
```

This will:
- Create all database tables
- Import products from `data/catalog_corrected.csv`
- Create categories from product types
- Store all attributes in `product_attributes` table
- Create placeholder images

## Running the Application

```bash
python run_server.py
# Or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Access the Application

- **Frontend:** http://localhost:8000/
- **Product Listing:** http://localhost:8000/
- **Product Detail:** http://localhost:8000/product/{product_id}
- **API Docs:** http://localhost:8000/docs
- **Products API:** http://localhost:8000/products

## API Endpoints

### GET /products
List all products with filtering and pagination.

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20, max: 100)
- `brand` (string): Filter by brand
- `stock_status` (string): Filter by stock status
- `category_id` (int): Filter by category ID
- `min_price` (float): Minimum price filter
- `max_price` (float): Maximum price filter
- `sort_by` (string): Sort field (product_id, price, title)
- `sort_order` (string): Sort order (asc, desc)

**Example:**
```
GET /products?brand=H&M Kids&min_price=500&max_price=2000&sort_by=price&sort_order=asc
```

### GET /products/{product_id}
Get single product details with all attributes.

**Example:**
```
GET /products/PRD1
```

## Database Schema

### Tables Created:
1. **products** - Core product information
2. **categories** - Product categories (derived from product_type)
3. **product_attributes** - All other CSV columns as key-value pairs
4. **product_images** - Product images (placeholder URLs for now)

## Frontend Features

1. **Product Listing Page** (`/`)
   - Grid layout with product cards
   - Filters sidebar (brand, price, stock, category)
   - Sorting options
   - Pagination
   - Responsive design

2. **Product Detail Page** (`/product/{product_id}`)
   - Full product information
   - Image gallery
   - All attributes displayed in table
   - Stock status and pricing

3. **Chat Sidebar** (Placeholder)
   - Collapsible sidebar on right
   - UI ready for future agent integration

## Notes

- The agent search functionality (`/search`) is still available but separate from the product catalog
- Product images are currently placeholder URLs - update `product_images` table with real image URLs
- Categories are automatically created from `product_type` column during migration

