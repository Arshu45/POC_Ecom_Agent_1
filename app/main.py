"""
FastAPI application main file.
Aligned with dynamic category & attribute architecture.
"""

import logging
import json
import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.schemas import SearchRequest, SearchResponse, ProductResult
from app.services.agent_service import AgentService
from app.services.product_retrieval_service import ProductRetrievalService
from app.routers import products as products_router, filters, categories


# ============================================================
# Utility helpers
# ============================================================

def format_price(metadata: dict) -> str:
    price = metadata.get("price")
    mrp = metadata.get("mrp")

    if price is None:
        return "Price not available"

    price_str = f"₹{int(price):,}"

    if mrp and mrp > price:
        discount = int(((mrp - price) / mrp) * 100)
        return f"{price_str} ({discount}% off)"

    return price_str


def extract_key_features(metadata: dict) -> list:
    """
    Extract safe, dynamic key features from metadata.
    Does NOT assume fixed attributes.
    """
    features = []

    if brand := metadata.get("brand"):
        features.append(f"Brand: {str(brand).title()}")

    if stock := metadata.get("stock_status"):
        features.append(f"Stock: {str(stock).replace('_', ' ').title()}")

    # Optional dynamic attributes (only if present)
    for attr in ["size", "age_group", "color", "occasion", "fit_type"]:
        if val := metadata.get(attr):
            features.append(f"{attr.replace('_',' ').title()}: {str(val).title()}")

    return features[:4]  # keep UI compact


def generate_follow_up_questions(products: list) -> list:
    questions = []

    brands = {p.get("metadata", {}).get("brand") for p in products if p.get("metadata")}
    if len(brands) > 1:
        questions.append("Would you like to explore other brands?")

    questions.append("Would you like to apply filters like price or color?")
    questions.append("Do you want help choosing the best option?")

    return questions[:2]


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Global services
# ============================================================

agent_service: AgentService | None = None
product_service: ProductRetrievalService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_service, product_service

    logger.info("Initializing services...")
    try:
        product_service = ProductRetrievalService()
        agent_service = AgentService(product_service=product_service)
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        product_service = None
        agent_service = None

    yield
    logger.info("Shutting down services...")


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="E-commerce Product Search Agent API",
    description="Dynamic product search with category-based filters",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(products_router.router)
app.include_router(filters.router)

app.include_router(categories.router)


# Static & templates
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals["url_for_static"] = lambda p: f"/static/{p}"


# ============================================================
# Frontend pages
# ============================================================

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


@app.get("/product/{product_id}")
async def read_product_page(request: Request, product_id: str):
    return templates.TemplateResponse(
        "product.html",
        {"request": request, "product_id": product_id},
    )


# ============================================================
# Health & Info
# ============================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent_service": agent_service is not None,
        "product_service": product_service is not None,
    }


# ============================================================
# SEARCH ENDPOINT
# ============================================================

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    try:
        products = []
        if product_service:
            products = product_service.search_products(
                request.query, n_results=5
            )

        recommendations = {}
        if agent_service:
            recommendations = agent_service.generate_recommendations(
                query=request.query,
                products=products,
            )

        response_text = recommendations.get(
            "response_text",
            f"I found {len(products)} products matching your search.",
        )

        follow_up_questions = recommendations.get(
            "follow_up_questions",
            generate_follow_up_questions(products),
        )

        # Legacy: Format minimal products for chat display
        formatted_products = []
        for p in products:
            try:
                doc = json.loads(p.get("document", "{}"))
                metadata = p.get("metadata", {})

                formatted_products.append(
                    ProductResult(
                        id=p.get("id"),
                        title=doc.get("title", "Unknown Product"),
                        price=format_price(metadata),
                        key_features=extract_key_features(metadata),
                    )
                )
            except Exception:
                continue

        # NEW: Get full product data for recommended products
        recommended_products = []
        recommended_product_ids = recommendations.get("recommended_product_ids", [])
        
        if recommended_product_ids:
            try:
                # Call batch retrieval endpoint
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/products/batch",
                        json=recommended_product_ids,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        recommended_products = response.json()
                        logger.info(f"Retrieved {len(recommended_products)} recommended products")
                    else:
                        logger.warning(f"Batch retrieval failed with status {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching recommended products: {e}")

        return SearchResponse(
            response_text=response_text,
            products=formatted_products,
            recommended_products=recommended_products,
            follow_up_questions=follow_up_questions,
            metadata={
                "total_results": len(formatted_products),
                "recommended_count": len(recommended_products)
            },
            success=True,
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        return SearchResponse(
            response_text="Something went wrong. Please try again.",
            products=[],
            recommended_products=[],
            follow_up_questions=[],
            metadata={},
            success=False,
            error_message=str(e),
        )


# ============================================================
# Run locally
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
