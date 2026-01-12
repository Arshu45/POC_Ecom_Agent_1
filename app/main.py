"""FastAPI application main file."""

import logging
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.schemas import SearchRequest, SearchResponse, ProductResult
from app.services.agent_service import AgentService
from app.services.product_retrieval_service import ProductRetrievalService


def format_price(metadata: dict) -> str:
    """
    Format price string with discount information.
    
    Args:
        metadata: Product metadata dictionary
        
    Returns:
        Formatted price string (e.g., "₹1,632 (2% off)")
    """
    price = metadata.get("price")
    mrp = metadata.get("mrp")
    
    if not price:
        return "Price not available"
    
    # Format price with commas
    price_str = f"₹{int(price):,}"
    
    # Add discount if available
    if mrp and mrp > price:
        discount = int(((mrp - price) / mrp) * 100)
        return f"{price_str} ({discount}% off)"
    
    return price_str


def extract_key_features(metadata: dict, document: str) -> list:
    """
    Extract key features from product metadata (Brand, Size, Stock, Occasion).
    
    Args:
        metadata: Product metadata dictionary
        document: Product document JSON string
        
    Returns:
        List of key feature strings
    """
    features = []
    
    # Brand
    brand = metadata.get("brand")
    if brand:
        features.append(f"Brand: {str(brand).title()}")
    
    # Size with age group
    size = metadata.get("size")
    age_group = metadata.get("age_group")
    if size:
        size_str = f"Size: {str(size).upper()}"
        if age_group:
            size_str += f" ({str(age_group).upper()})"
        features.append(size_str)
    elif age_group:
        features.append(f"Age: {str(age_group).upper()}")
    
    # Stock status
    stock_status = metadata.get("stock_status")
    if stock_status:
        stock_display = str(stock_status).replace("_", " ").title()
        features.append(f"Stock: {stock_display}")
    
    # Occasion
    occasion = metadata.get("occasion")
    if occasion:
        features.append(f"Occasion: {str(occasion).title()}")
    
    return features


def generate_response_text(products: list, query: str) -> str:
    """
    Generate structured response text with recommendations.
    
    Args:
        products: List of product dictionaries
        query: Original user query
        
    Returns:
        Structured response text highlighting best option
    """
    if not products:
        return f"I couldn't find any products matching '{query}'. Please try different keywords."
    
    total = len(products)
    
    # Find best product (prioritize in stock, then by price/value)
    best_product = None
    for product in products:
        metadata = product.get("metadata", {})
        stock_status = str(metadata.get("stock_status", "")).lower()
        
        if stock_status == "in stock":
            best_product = product
            break
    
    # If no in-stock product, use first one
    if not best_product:
        best_product = products[0]
    
    # Extract best product details
    try:
        doc = json.loads(best_product.get("document", "{}"))
        best_title = doc.get("title", "product")
    except:
        best_title = "product"
    
    best_metadata = best_product.get("metadata", {})
    best_price = format_price(best_metadata)
    best_age = best_metadata.get("age_group", "")
    
    # Determine product type and extract color/occasion from products
    product_type = "product"
    color = None
    occasion = None
    
    if products:
        try:
            first_doc = json.loads(products[0].get("document", "{}"))
            title = first_doc.get("title", "").lower()
            if "dress" in title:
                product_type = "dress" if total == 1 else "dresses"
            
            # Extract color and occasion from metadata
            first_metadata = products[0].get("metadata", {})
            color = first_metadata.get("color")
            occasion = first_metadata.get("occasion")
        except:
            pass
    
    # Build response with color and occasion if available
    parts = []
    if color:
        parts.append(str(color).lower())
    if product_type != "product":
        parts.append(product_type)
    elif total == 1:
        parts.append("matching product")
    else:
        parts.append("matching products")
    
    if occasion:
        parts.append(f"for {str(occasion).lower()}")
    
    product_desc = " ".join(parts) if parts else f"{product_type}{'s' if total > 1 else ''}"
    response = f"I found {total} {product_desc}!"
    
    if best_product:
        response += f" The **{best_title}** ({best_price})"
        if best_metadata.get("stock_status", "").lower() == "in stock":
            response += " is your best option - it's in stock"
        if best_age:
            response += f" and perfect for {best_age.upper()}"
        response += "."
    
    return response


def generate_follow_up_questions(products: list, query: str) -> list:
    """
    Generate relevant follow-up questions based on products.
    
    Args:
        products: List of product dictionaries
        query: Original user query
        
    Returns:
        List of follow-up question strings
    """
    questions = []
    
    if not products:
        return questions
    
    # Extract unique brands
    brands = set()
    fit_types = set()
    for product in products:
        metadata = product.get("metadata", {})
        brand = metadata.get("brand")
        fit_type = metadata.get("fit_type")
        if brand:
            brands.add(brand)
        if fit_type:
            fit_types.add(fit_type)
    
    # Generate questions based on diversity
    if len(brands) > 1:
        questions.append("Would you like to see dresses from other brands?")
    
    if len(fit_types) > 1:
        fit_str = " or ".join([str(f).title() for f in list(fit_types)[:2]])
        questions.append(f"Do you prefer {fit_str} fit?")
    
    # Default questions if not enough diversity
    if len(questions) < 2:
        questions.append("Would you like to filter by size or price range?")
    
    if len(questions) < 2:
        questions.append("Do you need help with anything else?")
    
    return questions[:2]  # Limit to 2 questions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services
agent_service: AgentService = None
product_service: ProductRetrievalService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global agent_service, product_service
    
    # Startup
    logger.info("Initializing services...")
    try:
        # Initialize product retrieval service (required)
        product_service = ProductRetrievalService()
        logger.info("Product retrieval service initialized successfully")
        
        # Initialize agent service with product service (required)
        agent_service = AgentService(product_service=product_service)
        logger.info("Agent service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        product_service = None
        agent_service = None
        # Continue anyway - will use fallback responses
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")


# Create FastAPI app
app = FastAPI(
    title="E-commerce Product Search Agent API",
    description="FastAPI backend for product search POC using ReAct agent with semantic search",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "E-commerce Product Search Agent API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_service": agent_service is not None,
        "product_service": product_service is not None
    }


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Process user query using LLM agent with product search tool.
    
    This endpoint:
    1. Searches products using semantic search
    2. Processes the query using the ReAct agent (agent uses product search tool)
    3. Returns chatbot response text with product results
    
    Args:
        request: Search request with query
        
    Returns:
        SearchResponse with chatbot text and product results
    """
    try:
        # Step 1: Search products directly (for response formatting)
        products = []
        try:
            if product_service:
                products = product_service.search_products(request.query, n_results=5)
                logger.info(f"Found {len(products)} products for query: {request.query}")
        except Exception as e:
            logger.error(f"Product search failed: {str(e)}")
            # Continue without products - agent may still find them via tool
        
        # Step 2: Generate recommendations using LLM
        recommendations = {}
        try:
            if agent_service:
                recommendations = agent_service.generate_recommendations(
                    query=request.query,
                    products=products
                )
            else:
                logger.warning("Agent service not available, using fallback")
                recommendations = {
                    "response_text": f"I found {len(products)} product(s) matching '{request.query}'.",
                    "recommended_product_ids": [],
                    "reasoning": "",
                    "follow_up_questions": []
                }
        except Exception as e:
            logger.error(f"Recommendation generation failed: {str(e)}")
            recommendations = {
                "response_text": f"I found {len(products)} product(s) matching '{request.query}'.",
                "recommended_product_ids": [],
                "reasoning": "",
                "follow_up_questions": []
            }
        
        response_text = recommendations.get("response_text", "")
        recommended_ids = recommendations.get("recommended_product_ids", [])
        follow_up_questions = recommendations.get("follow_up_questions", [])
        
        # Step 3: Format products for response (only essential info)
        formatted_products = []
        # Create a map of product IDs for quick lookup
        product_map = {p.get("id", ""): p for p in products}
        
        # Sort products: recommended first (in order), then others
        all_product_ids = [p.get("id", "") for p in products]
        sorted_ids = recommended_ids + [pid for pid in all_product_ids if pid not in recommended_ids]
        
        for product_id in sorted_ids:
            if product_id not in product_map:
                continue
                
            product = product_map[product_id]
            try:
                # Parse document to get title
                document = product.get("document", "{}")
                metadata = product.get("metadata", {})
                
                try:
                    doc = json.loads(document)
                    title = doc.get("title", "Unknown Product")
                except:
                    title = "Unknown Product"
                
                # Format price
                price_str = format_price(metadata)
                
                # Extract key features (Brand, Size, Stock, Occasion)
                key_features = extract_key_features(metadata, document)
                
                formatted_products.append(ProductResult(
                    id=product_id,
                    title=title,
                    price=price_str,
                    key_features=key_features
                ))
            except Exception as e:
                logger.warning(f"Error formatting product: {e}")
                continue
        
        # Step 4: Calculate metadata
        in_stock_count = sum(
            1 for p in products 
            if str(p.get("metadata", {}).get("stock_status", "")).lower() == "in stock"
        )
        metadata = {
            "total_results": len(formatted_products),
            "in_stock_count": in_stock_count
        }
        
        # Step 7: Return successful response
        return SearchResponse(
            response_text=response_text,
            products=formatted_products,
            follow_up_questions=follow_up_questions,
            metadata=metadata,
            success=True,
            error_message=None
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in search endpoint: {str(e)}")
        # Return graceful error response
        return SearchResponse(
            response_text=(
                "I apologize, but I'm experiencing technical difficulties. "
                "Please try again in a moment."
            ),
            products=[],
            follow_up_questions=[],
            metadata={"total_results": 0, "in_stock_count": 0},
            success=False,
            error_message=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

