"""FastAPI application main file."""

import logging
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.schemas import SearchRequest, SearchResponse, ProductResult
from app.services.agent_service import AgentService
from app.services.product_retrieval_service import ProductRetrievalService


def extract_key_features(metadata: dict, document: str) -> list:
    """
    Extract key features from product metadata and document.
    
    Args:
        metadata: Product metadata dictionary
        document: Product document JSON string
        
    Returns:
        List of key feature strings (concise and user-friendly)
    """
    features = []
    
    # Extract key metadata fields in priority order
    # Price
    price = metadata.get("price")
    mrp = metadata.get("mrp")
    if price:
        if mrp and mrp > price:
            discount = int(((mrp - price) / mrp) * 100)
            features.append(f"₹{int(price)} (MRP: ₹{int(mrp)}, {discount}% off)")
        else:
            features.append(f"₹{int(price)}")
    
    # Color
    color = metadata.get("color")
    if color:
        features.append(f"Color: {str(color).title()}")
    
    # Size
    size = metadata.get("size")
    if size:
        features.append(f"Size: {str(size).upper()}")
    
    # Brand
    brand = metadata.get("brand")
    if brand:
        features.append(f"Brand: {str(brand).title()}")
    
    # Occasion
    occasion = metadata.get("occasion")
    if occasion:
        features.append(f"Occasion: {str(occasion).title()}")
    
    # Stock status
    stock_status = metadata.get("stock_status")
    if stock_status:
        stock_display = str(stock_status).replace("_", " ").title()
        features.append(f"Stock: {stock_display}")
    
    # Gender/Age group
    gender = metadata.get("gender")
    age_group = metadata.get("age_group")
    if gender or age_group:
        if gender and age_group:
            features.append(f"For: {str(gender).title()} ({str(age_group).upper()})")
        elif gender:
            features.append(f"For: {str(gender).title()}")
        elif age_group:
            features.append(f"Age: {str(age_group).upper()}")
    
    return features[:7]  # Limit to 7 key features

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
        
        # Step 2: Generate chatbot response using agent
        response_text = ""
        try:
            if agent_service:
                response_text = agent_service.generate_response(query=request.query)
            else:
                logger.warning("Agent service not available, using fallback response")
                response_text = "I'm having trouble processing your request. Please try again."
        except Exception as e:
            logger.error(f"Agent response generation failed: {str(e)}")
            # Use fallback response
            if agent_service:
                try:
                    response_text = agent_service._get_fallback_response(request.query)
                except Exception:
                    response_text = (
                        f"I apologize, but I encountered an error processing your query: '{request.query}'. "
                        "Please try again."
                    )
            else:
                response_text = (
                    f"I apologize, but I encountered an error processing your query: '{request.query}'. "
                    "Please try again."
                )
        
        # Step 3: Format products for response (only essential info)
        formatted_products = []
        for product in products:
            try:
                # Parse document to get title
                document = product.get("document", "{}")
                metadata = product.get("metadata", {})
                
                try:
                    doc = json.loads(document)
                    title = doc.get("title", "Unknown Product")
                except:
                    title = "Unknown Product"
                
                # Extract key features
                key_features = extract_key_features(metadata, document)
                
                formatted_products.append(ProductResult(
                    id=product.get("id", ""),
                    title=title,
                    key_features=key_features
                ))
            except Exception as e:
                logger.warning(f"Error formatting product: {e}")
                continue
        
        # Step 4: Return successful response
        return SearchResponse(
            response_text=response_text,
            products=formatted_products,
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
            success=False,
            error_message=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

