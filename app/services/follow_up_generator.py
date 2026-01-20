"""
Follow-Up Question Generator for Conversational Product Search Agent

Generates context-aware follow-up questions to help narrow user intent
and refine product search.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class FollowUpQuestionGenerator:
    """
    Generates context-aware follow-up questions.
    
    Questions are designed to:
    - Narrow down user intent
    - Refine constraints progressively
    - Avoid redundant questions about known constraints
    - Suggest related categories or features
    """
    
    def __init__(self, llm: ChatGroq):
        """
        Initialize follow-up question generator.
        
        Args:
            llm: ChatGroq LLM instance for question generation
        """
        self.llm = llm
        logger.info("FollowUpQuestionGenerator initialized")
    
    def generate(
        self,
        session_id: str,
        conversation_history: List[Dict[str, str]],
        current_products: List[Dict[str, Any]],
        accumulated_constraints: Dict[str, Any],
        max_questions: int = 4
    ) -> List[str]:
        """
        Generate context-aware follow-up questions.
        
        Args:
            session_id: Session identifier
            conversation_history: Full conversation history
            current_products: Products shown in current response
            accumulated_constraints: Constraints extracted from history
            max_questions: Maximum number of questions to generate (default: 4)
            
        Returns:
            List of follow-up questions (2-4 questions)
        """
        try:
            # Build prompt with context
            prompt = self._build_prompt(
                conversation_history,
                current_products,
                accumulated_constraints
            )
            
            # Call LLM
            response = self.llm.invoke(prompt)
            response_text = response.content.strip()
            
            # Parse questions
            questions = self._parse_questions(response_text)
            
            # Limit to max_questions
            questions = questions[:max_questions]
            
            logger.info(f"Generated {len(questions)} follow-up questions for session {session_id}")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {e}")
            return self._get_fallback_questions(accumulated_constraints)
    
    def _build_prompt(
        self,
        conversation_history: List[Dict[str, str]],
        current_products: List[Dict[str, Any]],
        accumulated_constraints: Dict[str, Any]
    ) -> List:
        """
        Build prompt for follow-up question generation.
        
        Args:
            conversation_history: Full conversation history
            current_products: Products shown in current response
            accumulated_constraints: Known constraints
            
        Returns:
            List of LangChain messages
        """
        system_prompt = """You are a follow-up question generator for a product search assistant.

Your task is to generate 2-4 follow-up questions that help the user narrow down their search.

RULES:
1. **Don't repeat known constraints**: If we already know the color is pink, don't ask about color
2. **Progressive narrowing**: Ask questions that refine the search further
3. **Relevant to products shown**: Base questions on the current product results
4. **Natural and conversational**: Questions should feel helpful, not interrogative
5. **Actionable**: Each question should lead to a more specific search

QUESTION TYPES (in order of priority):
1. **Refinement**: Price range, specific features, size/age
2. **Alternatives**: Different colors, brands, styles
3. **Context**: Occasion, recipient, preferences
4. **Related**: Similar categories or complementary items

Return ONLY a JSON array of questions:
["Question 1?", "Question 2?", "Question 3?", "Question 4?"]

No markdown, no explanations, just the JSON array."""
        
        # Format conversation history
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history[-6:]  # Last 3 turns
        ])
        
        # Format current products
        products_text = "\n".join([
            f"- {p.get('title', 'Unknown')} (₹{p.get('metadata', {}).get('price', 'N/A')})"
            for p in current_products[:5]
        ])
        
        # Format known constraints
        constraints_text = json.dumps(accumulated_constraints, indent=2) if accumulated_constraints else "None"
        
        user_prompt = f"""Recent Conversation:
{history_text}

Products Shown:
{products_text}

Known Constraints (DON'T ask about these):
{constraints_text}

Generate 2-4 follow-up questions as JSON array:"""
        
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
    
    def _parse_questions(self, response_text: str) -> List[str]:
        """
        Parse questions from LLM response.
        
        Args:
            response_text: LLM response text
            
        Returns:
            List of questions
        """
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?", "", response_text)
            response_text = re.sub(r"```$", "", response_text)
            response_text = response_text.strip()
        
        try:
            # Parse JSON array
            questions = json.loads(response_text)
            
            if isinstance(questions, list):
                # Filter out non-string items and empty strings
                questions = [q for q in questions if isinstance(q, str) and q.strip()]
                return questions
            else:
                logger.warning(f"Expected list, got {type(questions)}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse questions JSON: {e}")
            logger.error(f"Response text: {response_text}")
            
            # Fallback: try to extract questions manually
            return self._extract_questions_manually(response_text)
    
    def _extract_questions_manually(self, text: str) -> List[str]:
        """
        Manually extract questions from text (fallback).
        
        Args:
            text: Text containing questions
            
        Returns:
            List of questions
        """
        # Look for lines ending with '?'
        lines = text.split('\n')
        questions = []
        
        for line in lines:
            line = line.strip()
            # Remove list markers (1., -, *, etc.)
            line = re.sub(r'^[\d\-\*\•]+[\.\)]\s*', '', line)
            line = line.strip('"\'')
            
            if line.endswith('?'):
                questions.append(line)
        
        return questions[:4]
    
    def _get_fallback_questions(self, accumulated_constraints: Dict[str, Any]) -> List[str]:
        """
        Generate fallback questions when LLM fails.
        
        Args:
            accumulated_constraints: Known constraints
            
        Returns:
            List of generic follow-up questions
        """
        questions = []
        
        # Check what constraints are missing and ask about them
        if "price" not in accumulated_constraints:
            questions.append("What's your budget range for this purchase?")
        
        if "occasion" not in accumulated_constraints:
            questions.append("What occasion is this for?")
        
        if "color" not in accumulated_constraints:
            questions.append("Do you have a preferred color?")
        
        if "brand" not in accumulated_constraints:
            questions.append("Are you looking for any specific brand?")
        
        # Generic questions
        if len(questions) < 2:
            questions.extend([
                "Would you like to see more options?",
                "Do you need help with size selection?",
            ])
        
        return questions[:4]
