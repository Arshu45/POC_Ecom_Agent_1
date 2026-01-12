"""FastAPI application main file."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.schemas import SearchRequest, SearchResponse
from app.services.agent_service import AgentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service
agent_service: AgentService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global agent_service
    
    # Startup
    logger.info("Initializing agent service...")
    try:
        agent_service = AgentService()
        logger.info("Agent service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent service: {str(e)}")
        # Continue anyway - will use fallback responses
    
    yield
    
    # Shutdown
    logger.info("Shutting down agent service...")


# Create FastAPI app
app = FastAPI(
    title="Agent API",
    description="FastAPI backend for ReAct agent with search and weather tools",
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
        "message": "Agent API",
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
        "agent_service": agent_service is not None
    }


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Process user query using LLM agent with search and weather tools.
    
    This endpoint:
    1. Processes the query using the ReAct agent
    2. Agent can use DuckDuckGo search and weather API tools
    3. Returns chatbot response text
    
    Args:
        request: Search request with query
        
    Returns:
        SearchResponse with chatbot text
    """
    try:
        # Generate chatbot response using agent
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
        
        # Return successful response
        return SearchResponse(
            response_text=response_text,
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
            success=False,
            error_message=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

