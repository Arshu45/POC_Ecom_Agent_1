"""Agent service for LLM-powered product search responses."""

import os
import logging
import json
import re
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
    
    def generate_recommendations(
        self, 
        query: str, 
        products: list
    ) -> dict:
        """
        Generate structured recommendations using LLM with system prompt.
        
        Args:
            query: User search query
            products: List of product dictionaries with document and metadata
            
        Returns:
            Dictionary with response_text, recommended_product_ids, reasoning, follow_up_questions
        """
        if not self.llm:
            return self._get_fallback_recommendations(query, products)
        
        if not products:
            return {
                "response_text": f"I couldn't find any products matching '{query}'. Please try different keywords.",
                "recommended_product_ids": [],
                "reasoning": "No products found",
                "follow_up_questions": ["Would you like to try a different search?", "Can you provide more details about what you're looking for?"]
            }
        
        try:
            # Format products for LLM
            formatted_products = []
            for i, product in enumerate(products, 1):
                try:
                    doc = json.loads(product.get("document", "{}"))
                    metadata = product.get("metadata", {})
                    
                    product_id = product.get("id", "")
                    title = doc.get("title", "Unknown Product")
                    price = metadata.get("price", 0)
                    stock_status = str(metadata.get("stock_status", "")).replace("_", " ").title()
                    age_group = metadata.get("age_group", "")
                    
                    # Format price with commas
                    price_str = f"₹{int(price):,}" if price else "Price not available"
                    
                    # Build product string
                    product_str = f"{i}. {product_id} - {title} ({price_str}, {stock_status}"
                    if age_group:
                        product_str += f", {age_group.upper()}"
                    product_str += ")"
                    
                    formatted_products.append(product_str)
                except Exception as e:
                    logger.warning(f"Error formatting product for recommendation: {e}")
                    continue
            
            if not formatted_products:
                return self._get_fallback_recommendations(query, products)
            
            # System prompt
            system_prompt = """You are a product recommendation assistant.

RESPONSE FORMAT (JSON):
{
  "response_text": "Natural language summary highlighting the BEST match first",
  "recommended_product_ids": ["PRD148", "PRD72", "PRD66"],  // Sorted by relevance
  "reasoning": "Why these products match the query",
  "follow_up_questions": ["Question 1?", "Question 2?"]
}

RULES:
1. Sort products: in-stock first, then by relevance
2. Mention stock status in response_text
3. Highlight the #1 recommendation
4. Include 2 follow-up questions
5. Be concise but helpful
6. Return ONLY valid JSON, no markdown or extra text"""
            
            # User prompt
            user_prompt = f"""User Query: "{query}"

Retrieved Products:
{chr(10).join(formatted_products)}

Generate recommendation response."""
            
            # Call LLM using LangChain format
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON response (handle markdown code blocks if present)
            if response_text.startswith("```"):
                # Remove markdown code blocks
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text)
                response_text = response_text.strip()
            
            # Parse JSON
            try:
                result = json.loads(response_text)
                
                # Validate structure
                if not isinstance(result, dict):
                    raise ValueError("Response is not a dictionary")
                
                return {
                    "response_text": result.get("response_text", ""),
                    "recommended_product_ids": result.get("recommended_product_ids", []),
                    "reasoning": result.get("reasoning", ""),
                    "follow_up_questions": result.get("follow_up_questions", [])
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.error(f"Response text: {response_text}")
                return self._get_fallback_recommendations(query, products)
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._get_fallback_recommendations(query, products)
    
    def _get_fallback_recommendations(self, query: str, products: list) -> dict:
        """
        Generate fallback recommendations when LLM fails.
        
        Args:
            query: User search query
            products: List of product dictionaries
            
        Returns:
            Dictionary with fallback recommendations
        """
        if not products:
            return {
                "response_text": f"I couldn't find any products matching '{query}'. Please try different keywords.",
                "recommended_product_ids": [],
                "reasoning": "No products found",
                "follow_up_questions": ["Would you like to try a different search?", "Can you provide more details?"]
            }
        
        # Sort products: in-stock first
        sorted_products = sorted(
            products,
            key=lambda p: (str(p.get("metadata", {}).get("stock_status", "")).lower() != "in stock", p.get("id", ""))
        )
        
        recommended_ids = [p.get("id", "") for p in sorted_products[:3] if p.get("id")]
        
        return {
            "response_text": f"I found {len(products)} product(s) matching '{query}'. Here are the top recommendations.",
            "recommended_product_ids": recommended_ids,
            "reasoning": "Products sorted by stock availability",
            "follow_up_questions": ["Would you like to see more options?", "Do you need help with anything else?"]
        }

