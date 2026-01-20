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
from app.services.session_manager import SessionManager
from app.services.conversation_memory import ConversationMemoryManager
from app.services.rejection_tracker import RejectionTracker
from app.services.conversational_agent_service import ConversationalAgentService
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

# Legacy agent (kept for backward compatibility)
agent_service: AgentService | None = None
product_service: ProductRetrievalService | None = None

# NEW: Conversational agent components
session_manager: SessionManager | None = None
memory_manager: ConversationMemoryManager | None = None
rejection_tracker: RejectionTracker | None = None
conversational_agent: ConversationalAgentService | None = None

# Feature flag for conversational mode
ENABLE_CONVERSATIONAL_MODE = os.getenv("ENABLE_CONVERSATIONAL_MODE", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_service, product_service
    global session_manager, memory_manager, rejection_tracker, conversational_agent

    logger.info("Initializing services...")
    try:
        # Initialize product retrieval service (shared by both agents)
        product_service = ProductRetrievalService()
        
        # Initialize legacy agent (for backward compatibility)
        agent_service = AgentService(product_service=product_service)
        
        # Initialize conversational agent components (if enabled)
        if ENABLE_CONVERSATIONAL_MODE:
            logger.info("Initializing conversational agent components...")
            
            # Session management
            session_manager = SessionManager(session_timeout_seconds=3600)
            
            # Memory management
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=os.getenv("GROQ_API_KEY"),
                temperature=0,
            )
            memory_manager = ConversationMemoryManager(session_manager, llm)
            
            # Rejection tracking
            rejection_tracker = RejectionTracker(session_manager)
            
            # Conversational agent
            conversational_agent = ConversationalAgentService(
                product_service=product_service,
                session_manager=session_manager,
                memory_manager=memory_manager,
                rejection_tracker=rejection_tracker
            )
            
            logger.info("Conversational agent initialized successfully")
        else:
            logger.info("Conversational mode disabled, using legacy agent only")
        
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        product_service = None
        agent_service = None
        conversational_agent = None

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
        "conversational_agent": conversational_agent is not None,
        "conversational_mode_enabled": ENABLE_CONVERSATIONAL_MODE,
    }


# ============================================================
# Session Management Endpoints
# ============================================================

@app.post("/session/create")
async def create_session():
    """
    Create a new conversation session.
    
    Returns:
        Session ID and metadata
    """
    if not session_manager:
        return {
            "success": False,
            "error": "Session management not available"
        }
    
    session_id = session_manager.create_session()
    return {
        "success": True,
        "session_id": session_id,
        "created_at": session_manager.get_session(session_id).created_at.isoformat(),
        "expires_in_seconds": 3600
    }


@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """
    Get information about a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session statistics and metadata
    """
    if not session_manager:
        return {
            "success": False,
            "error": "Session management not available"
        }
    
    session = session_manager.get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": "Session not found or expired"
        }
    
    stats = session_manager.get_stats(session_id)
    
    return {
        "success": True,
        "session_id": session_id,
        "created_at": session.created_at.isoformat(),
        "last_updated": session.last_updated.isoformat(),
        "stats": stats,
        "conversation_history": session.conversation_history,
        "shown_products": list(session.shown_products),
        "rejected_products": list(session.rejected_products),
        "accumulated_constraints": session.accumulated_constraints
    }


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success status
    """
    if not session_manager:
        return {
            "success": False,
            "error": "Session management not available"
        }
    
    session_manager.delete_session(session_id)
    return {
        "success": True,
        "message": f"Session {session_id} deleted"
    }


# ============================================================
# SEARCH ENDPOINT
# ============================================================

# @app.post("/search", response_model=SearchResponse)
# async def search(request: SearchRequest) -> SearchResponse:
#     try:
#         products = []
#         if product_service:
#             products = product_service.search_products(
#                 request.query, n_results=5
#             )

#         recommendations = {}
#         if agent_service:
#             recommendations = agent_service.generate_recommendations(
#                 query=request.query,
#                 products=products,
#             )

#         response_text = recommendations.get(
#             "response_text",
#             f"I found {len(products)} products matching your search.",
#         )

#         follow_up_questions = recommendations.get(
#             "follow_up_questions",
#             generate_follow_up_questions(products),
#         )

#         # Legacy: Format minimal products for chat display
#         formatted_products = []
#         for p in products:
#             try:
#                 doc = json.loads(p.get("document", "{}"))
#                 metadata = p.get("metadata", {})

#                 formatted_products.append(
#                     ProductResult(
#                         id=p.get("id"),
#                         title=doc.get("title", "Unknown Product"),
#                         price=format_price(metadata),
#                         key_features=extract_key_features(metadata),
#                     )
#                 )
#             except Exception:
#                 continue

#         # NEW: Get full product data for recommended products
#         recommended_products = []
#         recommended_product_ids = recommendations.get("recommended_product_ids", [])
        
#         if recommended_product_ids:
#             try:
#                 # Call batch retrieval endpoint
#                 async with httpx.AsyncClient() as client:
#                     response = await client.post(
#                         "http://localhost:8000/products/batch",
#                         json=recommended_product_ids,
#                         timeout=10.0
#                     )
                    
#                     if response.status_code == 200:
#                         recommended_products = response.json()
#                         logger.info(f"Retrieved {len(recommended_products)} recommended products")
#                     else:
#                         logger.warning(f"Batch retrieval failed with status {response.status_code}")
#             except Exception as e:
#                 logger.error(f"Error fetching recommended products: {e}")

#         return SearchResponse(
#             response_text=response_text,
#             products=formatted_products,
#             recommended_products=recommended_products,
#             follow_up_questions=follow_up_questions,
#             metadata={
#                 "total_results": len(formatted_products),
#                 "recommended_count": len(recommended_products)
#             },
#             success=True,
#         )

#     except Exception as e:
#         logger.error(f"Search error: {e}")
#         return SearchResponse(
#             response_text="Something went wrong. Please try again.",
#             products=[],
#             recommended_products=[],
#             follow_up_questions=[],
#             metadata={},
#             success=False,
#             error_message=str(e),
#         )

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Product search endpoint with conversational agent support.
    
    Supports both:
    - Conversational mode (with session_id, memory, rejection tracking)
    - Legacy stateless mode (backward compatibility)
    """
    try:
        # Determine which mode to use
        use_conversational = (
            ENABLE_CONVERSATIONAL_MODE and 
            conversational_agent is not None
        )
        
        if use_conversational:
            # ============================================
            # CONVERSATIONAL MODE (NEW)
            # ============================================
            
            # 1. Session handling
            session_id = request.session_id or session_manager.create_session()
            logger.info(f"Processing conversational search for session: {session_id}")
            
            # 2. Call conversational agent
            result = conversational_agent.generate_response(
                session_id=session_id,
                message=request.query
            )
            
            # 3. Batch retrieval for recommended products
            recommended_products = []
            if result["recommended_product_ids"]:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/products/batch",
                            json=result["recommended_product_ids"],
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            recommended_products = response.json()
                            logger.info(f"Retrieved {len(recommended_products)} recommended products")
                except Exception as e:
                    logger.error(f"Error fetching recommended products: {e}")
            
            # 4. Return conversational response
            return SearchResponse(
                response_text=result["response_text"],
                products=[],  # Legacy field, can be deprecated
                recommended_products=recommended_products,
                follow_up_questions=result["follow_up_questions"],
                session_id=session_id,
                metadata={
                    "recommended_count": len(recommended_products),
                    "session_stats": session_manager.get_stats(session_id) if session_manager else {},
                    "mode": "conversational"
                },
                success=True
            )
        
        else:
            # ============================================
            # LEGACY STATELESS MODE (BACKWARD COMPATIBILITY)
            # ============================================
            
            logger.info("Processing legacy stateless search")
            
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

            # Get full product data for recommended products
            recommended_products = []
            recommended_product_ids = recommendations.get("recommended_product_ids", [])
            
            if recommended_product_ids:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/products/batch",
                            json=recommended_product_ids,
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            recommended_products = response.json()
                            logger.info(f"Retrieved {len(recommended_products)} recommended products")
                except Exception as e:
                    logger.error(f"Error fetching recommended products: {e}")

            return SearchResponse(
                response_text=response_text,
                products=formatted_products,
                recommended_products=recommended_products,
                follow_up_questions=follow_up_questions,
                session_id="stateless",  # Indicate stateless mode
                metadata={
                    "total_results": len(formatted_products),
                    "recommended_count": len(recommended_products),
                    "mode": "stateless"
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
            session_id=request.session_id or "error",
            metadata={"mode": "error"},
            success=False,
            error_message=str(e),
        )



# ============================================================
# Run locally
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
