"""
Rejection Tracking for Conversational Product Search Agent

Tracks shown and rejected products per session to avoid repetition
and improve user experience.
"""

import logging
import re
from typing import List, Dict, Set, Optional, Any

from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


class RejectionTracker:
    """
    Tracks shown and rejected products per session.
    
    Provides:
    - Marking products as shown
    - Marking products as rejected (explicit/implicit)
    - Filtering products to exclude rejected items
    - Rejection statistics
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize rejection tracker.
        
        Args:
            session_manager: SessionManager instance
        """
        self.session_manager = session_manager
        logger.info("RejectionTracker initialized")
    
    def mark_shown(self, session_id: str, product_ids: List[str]):
        """
        Mark products as shown to user.
        
        Args:
            session_id: Session identifier
            product_ids: List of product IDs shown
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"Cannot mark shown for non-existent session: {session_id}")
            return
        
        session.shown_products.update(product_ids)
        self.session_manager.update_session(session_id, session)
        
        logger.debug(f"Marked {len(product_ids)} products as shown in session {session_id}")
    
    def mark_rejected(self, session_id: str, product_ids: List[str]):
        """
        Mark products as explicitly rejected.
        
        Args:
            session_id: Session identifier
            product_ids: List of product IDs to reject
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"Cannot mark rejected for non-existent session: {session_id}")
            return
        
        session.rejected_products.update(product_ids)
        self.session_manager.update_session(session_id, session)
        
        logger.info(f"Marked {len(product_ids)} products as rejected in session {session_id}")
    
    def detect_implicit_rejection(
        self,
        session_id: str,
        message: str,
        shown_products: Optional[List[Dict]] = None
    ) -> List[str]:
        """
        Detect implicitly rejected products from user message.
        
        Patterns detected:
        - "not the first one" → reject product at index 0
        - "not these" / "show different" → reject all shown
        - "something cheaper" → reject all shown (price too high)
        - "different color" → reject all shown (color not right)
        - "not PRD123" → reject specific product
        
        Args:
            session_id: Session identifier
            message: User message to analyze
            shown_products: Optional list of recently shown products
            
        Returns:
            List of product IDs to reject
        """
        message_lower = message.lower().strip()
        rejected_ids = []
        
        session = self.session_manager.get_session(session_id)
        if not session:
            return rejected_ids
        
        # Get recently shown products
        if shown_products is None:
            shown_products = []
        
        # Pattern 1: "not the first/second/third one"
        ordinal_patterns = [
            (r'\bnot\s+(?:the\s+)?first\b', 0),
            (r'\bnot\s+(?:the\s+)?second\b', 1),
            (r'\bnot\s+(?:the\s+)?third\b', 2),
            (r'\bnot\s+(?:the\s+)?fourth\b', 3),
            (r'\bnot\s+(?:the\s+)?fifth\b', 4),
        ]
        
        for pattern, index in ordinal_patterns:
            if re.search(pattern, message_lower):
                if shown_products and index < len(shown_products):
                    product_id = shown_products[index].get("id")
                    if product_id:
                        rejected_ids.append(product_id)
                        logger.info(f"Implicit rejection (ordinal): {product_id}")
        
        # Pattern 2: "not these" / "show different" / "something else"
        rejection_phrases = [
            r'\bnot\s+these\b',
            r'\bshow\s+different\b',
            r'\bsomething\s+else\b',
            r'\bother\s+options\b',
            r'\bdifferent\s+ones\b',
            r'\bnot\s+interested\b',
            r'\bdon\'t\s+like\b',
        ]
        
        for phrase in rejection_phrases:
            if re.search(phrase, message_lower):
                # Reject all recently shown products
                if shown_products:
                    for product in shown_products:
                        product_id = product.get("id")
                        if product_id and product_id not in rejected_ids:
                            rejected_ids.append(product_id)
                    logger.info(f"Implicit rejection (phrase): {len(rejected_ids)} products")
                break
        
        # Pattern 3: Price-related rejections
        price_rejection_phrases = [
            r'\btoo\s+expensive\b',
            r'\btoo\s+costly\b',
            r'\bcheaper\b',
            r'\bless\s+expensive\b',
            r'\blower\s+price\b',
        ]
        
        for phrase in price_rejection_phrases:
            if re.search(phrase, message_lower):
                # Reject all shown products (price too high)
                if shown_products:
                    for product in shown_products:
                        product_id = product.get("id")
                        if product_id and product_id not in rejected_ids:
                            rejected_ids.append(product_id)
                    logger.info(f"Implicit rejection (price): {len(rejected_ids)} products")
                break
        
        # Pattern 4: Color/style rejections
        style_rejection_phrases = [
            r'\bdifferent\s+color\b',
            r'\bother\s+colors?\b',
            r'\bnot\s+this\s+color\b',
            r'\bdifferent\s+style\b',
        ]
        
        for phrase in style_rejection_phrases:
            if re.search(phrase, message_lower):
                # Reject all shown products
                if shown_products:
                    for product in shown_products:
                        product_id = product.get("id")
                        if product_id and product_id not in rejected_ids:
                            rejected_ids.append(product_id)
                    logger.info(f"Implicit rejection (style): {len(rejected_ids)} products")
                break
        
        # Pattern 5: Explicit product ID rejection
        # "not PRD123" or "except PRD123"
        product_id_pattern = r'\b(?:not|except)\s+(PRD\d+)\b'
        matches = re.findall(product_id_pattern, message_lower.upper())
        for product_id in matches:
            if product_id not in rejected_ids:
                rejected_ids.append(product_id)
                logger.info(f"Explicit rejection: {product_id}")
        
        return rejected_ids
    
    def filter_products(
        self,
        session_id: str,
        products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter out rejected products from results.
        
        Args:
            session_id: Session identifier
            products: List of product dictionaries
            
        Returns:
            Filtered list of products (rejected ones removed)
        """
        session = self.session_manager.get_session(session_id)
        if not session or not session.rejected_products:
            return products
        
        filtered = [
            p for p in products
            if p.get("id") not in session.rejected_products
        ]
        
        removed_count = len(products) - len(filtered)
        if removed_count > 0:
            logger.info(f"Filtered out {removed_count} rejected products from session {session_id}")
        
        return filtered
    
    def get_rejection_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get rejection statistics for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with rejection statistics
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {}
        
        return {
            "shown_count": len(session.shown_products),
            "rejected_count": len(session.rejected_products),
            "rejection_rate": (
                len(session.rejected_products) / len(session.shown_products)
                if session.shown_products else 0
            ),
            "rejected_product_ids": list(session.rejected_products)
        }
    
    def get_shown_products(self, session_id: str) -> Set[str]:
        """
        Get set of shown product IDs for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Set of product IDs
        """
        session = self.session_manager.get_session(session_id)
        if session:
            return session.shown_products
        return set()
    
    def get_rejected_products(self, session_id: str) -> Set[str]:
        """
        Get set of rejected product IDs for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Set of product IDs
        """
        session = self.session_manager.get_session(session_id)
        if session:
            return session.rejected_products
        return set()
