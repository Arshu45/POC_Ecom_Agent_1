"""
Conversational Agent Service for Product Search

LangChain-based conversational agent with memory, rejection tracking,
and context-aware product recommendations.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import Client
from dotenv import load_dotenv

from app.services.product_retrieval_service import ProductRetrievalService
from app.services.session_manager import SessionManager
from app.services.conversation_memory import ConversationMemoryManager
from app.services.rejection_tracker import RejectionTracker
from app.services.follow_up_generator import FollowUpQuestionGenerator

load_dotenv()
logger = logging.getLogger(__name__)


class ConversationalAgentService:
    """
    LangChain-based conversational product search agent.
    
    Features:
    - Session-aware memory
    - Constraint accumulation across turns
    - Rejection tracking
    - Context-aware follow-up questions
    """
    
    def __init__(
        self,
        product_service: ProductRetrievalService,
        session_manager: SessionManager,
        memory_manager: ConversationMemoryManager,
        rejection_tracker: RejectionTracker
    ):
        """
        Initialize conversational agent service.
        
        Args:
            product_service: ProductRetrievalService instance
            session_manager: SessionManager instance
            memory_manager: ConversationMemoryManager instance
            rejection_tracker: RejectionTracker instance
        """
        self.product_service = product_service
        self.session_manager = session_manager
        self.memory_manager = memory_manager
        self.rejection_tracker = rejection_tracker
        
        # Initialize LLM
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )
        
        # Initialize follow-up question generator
        self.follow_up_generator = FollowUpQuestionGenerator(self.llm)
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent (optional - currently using direct LLM for structured output)
        self.agent_executor = None
        try:
            client = Client()
            prompt = client.pull_prompt("hwchase17/react")
            agent = create_react_agent(llm=self.llm, tools=self.tools, prompt=prompt)
            self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False)
        except Exception as e:
            logger.warning(f"Could not create agent executor: {e}")
        
        logger.info("ConversationalAgentService initialized")
    
    def _create_tools(self) -> List:
        """Create LangChain tools for agent."""
        return [self._create_product_search_tool()]
    
    def _create_product_search_tool(self):
        """Create memory-aware product search tool."""
        
        @tool
        def search_products_with_context(query: str, session_id: str) -> str:
            """
            Search for products with conversation context and rejection filtering.
            
            Args:
                query: Product search query
                session_id: Session identifier for context
                
            Returns:
                JSON string with product results
            """
            try:
                # 1. Get accumulated constraints from memory
                constraints = self.memory_manager.extract_accumulated_constraints(session_id)
                logger.info(f"Accumulated constraints: {constraints}")
                
                # 2. Search products (retrieval service handles constraint merging)
                products = self.product_service.search_products(query, n_results=10)
                
                # 3. Filter out rejected products
                products = self.rejection_tracker.filter_products(session_id, products)
                
                # 4. Mark top 5 as shown
                product_ids = [p.get("id") for p in products[:5] if p.get("id")]
                self.rejection_tracker.mark_shown(session_id, product_ids)
                
                # 5. Format for agent
                formatted = []
                for p in products[:5]:
                    try:
                        doc = json.loads(p.get("document", "{}"))
                        metadata = p.get("metadata", {})
                        formatted.append({
                            "id": p.get("id"),
                            "title": doc.get("title", "Unknown"),
                            "price": metadata.get("price", 0),
                            "stock_status": metadata.get("stock_status", ""),
                            "color": metadata.get("color", ""),
                            "brand": metadata.get("brand", "")
                        })
                    except Exception:
                        continue
                
                return json.dumps({
                    "found": True,
                    "count": len(formatted),
                    "products": formatted
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Error in search tool: {e}")
                return json.dumps({"found": False, "error": str(e)})
        
        return search_products_with_context
    
    def generate_response(
        self,
        session_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Generate conversational response with memory and context.
        
        Args:
            session_id: Session identifier
            message: User message
            
        Returns:
            Dictionary with response_text, recommended_product_ids, follow_up_questions
        """
        try:
            # 1. Detect and mark implicit rejections
            # Get recently shown products for context
            shown_ids = list(self.rejection_tracker.get_shown_products(session_id))
            recent_products = [{"id": pid} for pid in shown_ids[-5:]]  # Last 5 shown
            
            rejected_ids = self.rejection_tracker.detect_implicit_rejection(
                session_id, message, recent_products
            )
            if rejected_ids:
                self.rejection_tracker.mark_rejected(session_id, rejected_ids)
                logger.info(f"Detected {len(rejected_ids)} implicit rejections")
            
            # 2. Add user message to memory
            self.memory_manager.add_user_message(session_id, message)
            
            # 3. Get conversation context
            history = self.memory_manager.get_conversation_history(session_id)
            constraints = self.memory_manager.extract_accumulated_constraints(session_id)
            
            # 4. Search products with context
            products = self.product_service.search_products(message, n_results=10)
            products = self.rejection_tracker.filter_products(session_id, products)
            
            # 5. Mark as shown
            product_ids = [p.get("id") for p in products[:5] if p.get("id")]
            self.rejection_tracker.mark_shown(session_id, product_ids)
            
            # 6. Generate structured recommendation using LLM
            recommendation = self._generate_structured_recommendation(
                message, products[:5], history, constraints
            )
            
            # 7. Add AI response to memory
            self.memory_manager.add_ai_message(session_id, recommendation["response_text"])
            
            # 8. Generate follow-up questions
            follow_ups = self.follow_up_generator.generate(
                session_id=session_id,
                conversation_history=history,
                current_products=products[:5],
                accumulated_constraints=constraints,
                max_questions=4
            )
            
            return {
                "response_text": recommendation["response_text"],
                "recommended_product_ids": recommendation["recommended_product_ids"],
                "follow_up_questions": follow_ups,
                "session_id": session_id,
                "metadata": {
                    "constraints": constraints,
                    "rejection_stats": self.rejection_tracker.get_rejection_stats(session_id)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._get_fallback_response(session_id, message)
    
    def _generate_structured_recommendation(
        self,
        query: str,
        products: List[Dict],
        history: List[Dict],
        constraints: Dict
    ) -> Dict[str, Any]:
        """
        Generate structured recommendation using direct LLM call.
        
        Args:
            query: Current user query
            products: Retrieved products
            history: Conversation history
            constraints: Accumulated constraints
            
        Returns:
            Dictionary with response_text and recommended_product_ids
        """
        if not products:
            return {
                "response_text": f"I couldn't find any products matching '{query}'. Could you try different keywords?",
                "recommended_product_ids": []
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
                    
                    price_str = f"₹{int(price):,}" if price else "Price not available"
                    product_str = f"{i}. {product_id} - {title} ({price_str}, {stock_status})"
                    
                    formatted_products.append(product_str)
                except Exception as e:
                    logger.warning(f"Error formatting product: {e}")
                    continue
            
            if not formatted_products:
                return {
                    "response_text": "I found some products but couldn't format them. Please try again.",
                    "recommended_product_ids": []
                }
            
            # System prompt
            system_prompt = """You are a conversational product recommendation assistant.

RESPONSE FORMAT (JSON):
{
  "response_text": "Natural, conversational response highlighting the BEST match first",
  "recommended_product_ids": ["PRD148", "PRD72", "PRD66", "PRD45", "PRD89"]
}

RULES:
1. Include ALL retrieved products in recommended_product_ids
2. Sort by: in-stock first, then relevance
3. Be conversational and helpful (not robotic)
4. Mention stock status naturally
5. Highlight the #1 recommendation
6. Reference conversation context if relevant
7. Return ONLY valid JSON, no markdown"""
            
            # User prompt with context
            context_text = ""
            if constraints:
                context_text = f"\nKnown preferences: {json.dumps(constraints)}"
            
            user_prompt = f"""User Query: "{query}"{context_text}

Retrieved Products:
{chr(10).join(formatted_products)}

Generate recommendation response as JSON:"""
            
            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text)
                response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            return {
                "response_text": result.get("response_text", ""),
                "recommended_product_ids": result.get("recommended_product_ids", [])
            }
            
        except Exception as e:
            logger.error(f"Error generating structured recommendation: {e}")
            # Fallback
            return {
                "response_text": f"I found {len(products)} products for you. Here are my top recommendations!",
                "recommended_product_ids": [p.get("id") for p in products if p.get("id")]
            }
    
    def _get_fallback_response(self, session_id: str, message: str) -> Dict[str, Any]:
        """
        Generate fallback response when errors occur.
        
        Args:
            session_id: Session identifier
            message: User message
            
        Returns:
            Fallback response dictionary
        """
        return {
            "response_text": "I apologize, but I encountered an error processing your request. Could you please try rephrasing?",
            "recommended_product_ids": [],
            "follow_up_questions": [
                "Would you like to try a different search?",
                "Can you provide more details about what you're looking for?"
            ],
            "session_id": session_id,
            "metadata": {}
        }
