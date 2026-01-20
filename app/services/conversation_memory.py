"""
Conversation Memory Management for Conversational Product Search Agent

Manages LangChain memory per session and extracts accumulated constraints
from conversation history.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage

from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ConversationMemoryManager:
    """
    Manages LangChain conversation memory per session.
    
    Provides:
    - Message history storage
    - Constraint extraction from conversation history
    - Memory retrieval for agent use
    """
    
    def __init__(self, session_manager: SessionManager, llm: Optional[ChatGroq] = None):
        """
        Initialize conversation memory manager.
        
        Args:
            session_manager: SessionManager instance
            llm: Optional LLM for constraint extraction (uses default if None)
        """
        self.session_manager = session_manager
        self.memories: Dict[str, ChatMessageHistory] = {}
        self.llm = llm
        
        logger.info("ConversationMemoryManager initialized")
    
    def get_memory(self, session_id: str) -> ChatMessageHistory:
        """
        Get or create LangChain memory for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatMessageHistory instance
        """
        if session_id not in self.memories:
            # Create new memory
            memory = ChatMessageHistory()
            
            # Load existing history from session if available
            session = self.session_manager.get_session(session_id)
            if session and session.conversation_history:
                self._load_history_into_memory(memory, session.conversation_history)
            
            self.memories[session_id] = memory
            logger.debug(f"Created new memory for session: {session_id}")
        
        return self.memories[session_id]
    
    def add_user_message(self, session_id: str, message: str):
        """
        Add user message to memory and session.
        
        Args:
            session_id: Session identifier
            message: User message text
        """
        memory = self.get_memory(session_id)
        memory.add_user_message(message)
        
        # Also update session state
        session = self.session_manager.get_session(session_id)
        if session:
            session.conversation_history.append({
                "role": "user",
                "content": message
            })
            self.session_manager.update_session(session_id, session)
        
        logger.debug(f"Added user message to session {session_id}")
    
    def add_ai_message(self, session_id: str, message: str):
        """
        Add AI message to memory and session.
        
        Args:
            session_id: Session identifier
            message: AI message text
        """
        memory = self.get_memory(session_id)
        memory.add_ai_message(message)
        
        # Also update session state
        session = self.session_manager.get_session(session_id)
        if session:
            session.conversation_history.append({
                "role": "assistant",
                "content": message
            })
            self.session_manager.update_session(session_id, session)
        
        logger.debug(f"Added AI message to session {session_id}")
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get full conversation history for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dictionaries with 'role' and 'content'
        """
        session = self.session_manager.get_session(session_id)
        if session:
            return session.conversation_history
        return []
    
    def extract_accumulated_constraints(self, session_id: str) -> Dict[str, Any]:
        """
        Extract accumulated constraints from conversation history using LLM.
        
        Analyzes the full conversation to extract:
        - Price range (min/max from all turns)
        - Preferred brands
        - Category narrowing
        - Exclusions (e.g., "not red", "no sleeveless")
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary of accumulated constraints
        """
        if not self.llm:
            logger.warning("No LLM available for constraint extraction")
            return {}
        
        history = self.get_conversation_history(session_id)
        if not history:
            return {}
        
        # Check if constraints are cached in session
        session = self.session_manager.get_session(session_id)
        if session and session.accumulated_constraints:
            # Return cached constraints (will be updated with new message)
            return session.accumulated_constraints
        
        try:
            # Build prompt for constraint extraction
            system_prompt = """You are a constraint extraction assistant.
Analyze the conversation history and extract ALL product search constraints mentioned.

Extract the following types of constraints:
1. **Price**: min/max price mentioned across all turns
2. **Color**: any color preferences or exclusions
3. **Brand**: preferred or excluded brands
4. **Category/Type**: product type narrowing (e.g., "casual" → "party wear")
5. **Occasion**: birthday, wedding, casual, etc.
6. **Age/Size**: age group or size preferences
7. **Gender**: boys, girls, unisex
8. **Features**: specific features (sleeves, pockets, etc.)
9. **Exclusions**: things to avoid (e.g., "not red", "no party wear")

Return ONLY valid JSON in this format:
{
  "price": {"min": 1000, "max": 5000},
  "color": "pink",
  "excluded_colors": ["red", "black"],
  "brand": "H&M",
  "occasion": "birthday",
  "age_group": "2-3Y",
  "gender": "girls",
  "features": {"sleeve_type": "full_sleeve"},
  "exclusions": ["party wear", "sleeveless"]
}

If a constraint is not mentioned, omit it from the JSON.
"""
            
            # Format conversation history
            history_text = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in history
            ])
            
            user_prompt = f"""Conversation History:
{history_text}

Extract all constraints as JSON:"""
            
            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON (handle markdown code blocks)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text)
                response_text = response_text.strip()
            
            constraints = json.loads(response_text)
            
            # Cache in session
            if session:
                session.accumulated_constraints = constraints
                self.session_manager.update_session(session_id, session)
            
            logger.info(f"Extracted constraints for session {session_id}: {constraints}")
            return constraints
            
        except Exception as e:
            logger.error(f"Error extracting constraints: {e}")
            return {}
    
    def clear_memory(self, session_id: str):
        """
        Clear memory for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.memories:
            del self.memories[session_id]
            logger.info(f"Cleared memory for session: {session_id}")
    
    def _load_history_into_memory(
        self,
        memory: ChatMessageHistory,
        history: List[Dict[str, str]]
    ):
        """
        Load existing conversation history into LangChain memory.
        
        Args:
            memory: ChatMessageHistory instance
            history: List of message dictionaries
        """
        for msg in history:
            if msg["role"] == "user":
                memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                memory.add_ai_message(msg["content"])
