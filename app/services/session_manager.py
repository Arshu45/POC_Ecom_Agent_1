"""
Session Management for Conversational Product Search Agent

Manages conversation sessions with in-memory storage.
Future: Migrate to Redis for production scalability.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Any
from threading import Lock

logger = logging.getLogger(__name__)


class SessionState:
    """State for a single conversation session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.conversation_history: list[Dict[str, str]] = []
        self.shown_products: Set[str] = set()
        self.rejected_products: Set[str] = set()
        self.accumulated_constraints: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "conversation_history": self.conversation_history,
            "shown_products": list(self.shown_products),
            "rejected_products": list(self.rejected_products),
            "accumulated_constraints": self.accumulated_constraints,
            "metadata": self.metadata
        }
    
    def update_timestamp(self):
        """Update last_updated timestamp."""
        self.last_updated = datetime.now()


class SessionManager:
    """
    Manages conversation sessions with in-memory storage.
    
    Thread-safe implementation with automatic cleanup of expired sessions.
    """
    
    def __init__(self, session_timeout_seconds: int = 3600):
        """
        Initialize session manager.
        
        Args:
            session_timeout_seconds: Session expiry time in seconds (default: 1 hour)
        """
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = timedelta(seconds=session_timeout_seconds)
        self.lock = Lock()
        
        logger.info(f"SessionManager initialized with {session_timeout_seconds}s timeout")
    
    def create_session(self) -> str:
        """
        Generate new session ID and create session state.
        
        Returns:
            New session ID (UUID4)
        """
        session_id = str(uuid.uuid4())
        
        with self.lock:
            self.sessions[session_id] = SessionState(session_id)
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Retrieve session state by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionState if found and not expired, None otherwise
        """
        with self.lock:
            session = self.sessions.get(session_id)
            
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None
            
            # Check if expired
            if self._is_expired(session):
                logger.info(f"Session expired: {session_id}")
                del self.sessions[session_id]
                return None
            
            return session
    
    def update_session(self, session_id: str, state: SessionState):
        """
        Update session state.
        
        Args:
            session_id: Session identifier
            state: Updated session state
        """
        with self.lock:
            if session_id in self.sessions:
                state.update_timestamp()
                self.sessions[session_id] = state
                logger.debug(f"Updated session: {session_id}")
            else:
                logger.warning(f"Cannot update non-existent session: {session_id}")
    
    def delete_session(self, session_id: str):
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
        """
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Deleted session: {session_id}")
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove all expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with self.lock:
            expired_sessions = [
                sid for sid, session in self.sessions.items()
                if self._is_expired(session)
            ]
            
            for sid in expired_sessions:
                del self.sessions[sid]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
            return len(expired_sessions)
    
    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session statistics
        """
        session = self.get_session(session_id)
        if not session:
            return {}
        
        return {
            "message_count": len(session.conversation_history),
            "shown_products_count": len(session.shown_products),
            "rejected_products_count": len(session.rejected_products),
            "session_duration_seconds": (
                datetime.now() - session.created_at
            ).total_seconds(),
            "constraints_count": len(session.accumulated_constraints)
        }
    
    def get_all_session_ids(self) -> list[str]:
        """
        Get all active session IDs.
        
        Returns:
            List of session IDs
        """
        with self.lock:
            return list(self.sessions.keys())
    
    def get_session_count(self) -> int:
        """
        Get count of active sessions.
        
        Returns:
            Number of active sessions
        """
        with self.lock:
            return len(self.sessions)
    
    def _is_expired(self, session: SessionState) -> bool:
        """
        Check if session is expired.
        
        Args:
            session: Session state to check
            
        Returns:
            True if expired, False otherwise
        """
        return datetime.now() - session.last_updated > self.session_timeout
