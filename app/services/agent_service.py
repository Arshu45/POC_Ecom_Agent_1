"""Agent service for LLM-powered product search responses."""

import os
import logging
import json
from typing import Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_classic.agents import create_react_agent, AgentExecutor
from langsmith import Client

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def create_product_search_tool(product_service):
    """Create product search tool for the agent."""
    
    @tool
    def search_products(query: str) -> str:
        """
        Search for products in the e-commerce catalog using semantic search.
        Use this tool when the user is asking about products, items, clothing, dresses, or wants to buy something.
        
        Args:
            query: Product search query (e.g., "maroon dress for birthday", "dresses under 5000")
            
        Returns:
            JSON string with product search results including titles, prices, and metadata
        """
        try:
            products = product_service.search_products(query, n_results=5)
            
            if not products:
                return json.dumps({
                    "found": False,
                    "message": f"No products found matching '{query}'",
                    "products": []
                })
            
            # Format products for agent
            formatted_products = []
            for product in products:
                try:
                    doc = json.loads(product["document"])
                    metadata = product["metadata"]
                    
                    formatted_product = {
                        "title": doc.get("title", "Unknown Product"),
                        "product_id": product.get("id", ""),
                        "price": metadata.get("price", 0),
                        "mrp": metadata.get("mrp", 0),
                        "color": metadata.get("color", ""),
                        "size": metadata.get("size", ""),
                        "gender": metadata.get("gender", ""),
                        "occasion": metadata.get("occasion", ""),
                        "brand": metadata.get("brand", ""),
                        "stock_status": metadata.get("stock_status", ""),
                        "description": doc.get("embedding_text", "")
                    }
                    formatted_products.append(formatted_product)
                except Exception as e:
                    logger.warning(f"Error formatting product: {e}")
                    continue
            
            return json.dumps({
                "found": True,
                "count": len(formatted_products),
                "products": formatted_products
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Error in search_products tool: {str(e)}")
            return json.dumps({
                "found": False,
                "error": str(e),
                "products": []
            })
    
    return search_products


class AgentService:
    """Service for LLM agent orchestration with product search tool."""
    
    def __init__(self, product_service):
        """Initialize agent service with LLM and product search tool.
        
        Args:
            product_service: ProductRetrievalService instance (required)
        """
        if not product_service:
            raise ValueError("ProductRetrievalService is required for AgentService")
        
        try:
            # Configure Groq LLM
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=os.getenv("GROQ_API_KEY"),
                temperature=0,
            )
            
            # Create product search tool
            self.product_search_tool = create_product_search_tool(product_service)
            tools = [self.product_search_tool]
            
            logger.info("Product search tool added to agent")
            
            # Pull ReAct prompt template
            try:
                client = Client()
                self.prompt = client.pull_prompt("hwchase17/react")
            except Exception as e:
                logger.warning(f"Could not pull prompt from LangSmith: {e}. Using default.")
                self.prompt = None
            
            # Create ReAct agent
            self.agent = create_react_agent(
                llm=self.llm,
                tools=tools,
                prompt=self.prompt,
            )
            
            # Create agent executor
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=tools,
                verbose=False,
            )
            
            logger.info("Agent service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent service: {str(e)}")
            self.agent_executor = None
            self.llm = None
    
    def generate_response(self, query: str) -> str:
        """
        Generate chatbot response using LLM agent.
        
        Args:
            query: User search query
            
        Returns:
            Generated response text
        """
        if not self.agent_executor:
            return self._get_fallback_response(query)
        
        try:
            # Invoke agent
            result = self.agent_executor.invoke({"input": query})
            
            # Extract response text
            response_text = result.get("output", "")
            
            if not response_text:
                return self._get_fallback_response(query)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating agent response: {str(e)}")
            return self._get_fallback_response(query)
    
    def _get_fallback_response(self, query: str) -> str:
        """
        Generate fallback response when LLM fails.
        
        Args:
            query: User search query
            
        Returns:
            Fallback response text
        """
        return (
            f"I apologize, but I'm having trouble processing your query: '{query}'. "
            "Please try again or rephrase your question."
        )

