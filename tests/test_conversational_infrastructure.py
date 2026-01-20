"""
Test script for conversational agent infrastructure.

Tests:
1. SessionManager - session creation, retrieval, expiry
2. ConversationMemoryManager - message storage, constraint extraction
3. RejectionTracker - shown/rejected tracking, implicit detection
4. ConversationalAgentService - end-to-end conversation flow

Run this script to validate all components before integration.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

from app.services.session_manager import SessionManager
from app.services.conversation_memory import ConversationMemoryManager
from app.services.rejection_tracker import RejectionTracker
from app.services.product_retrieval_service import ProductRetrievalService
from app.services.conversational_agent_service import ConversationalAgentService


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_session_manager():
    """Test SessionManager functionality."""
    print_section("TEST 1: Session Manager")
    
    # Initialize
    session_mgr = SessionManager(session_timeout_seconds=5)  # 5 seconds for testing
    
    # Test 1: Create session
    print("✓ Creating new session...")
    session_id = session_mgr.create_session()
    print(f"  Session ID: {session_id}")
    
    # Test 2: Retrieve session
    print("\n✓ Retrieving session...")
    session = session_mgr.get_session(session_id)
    assert session is not None, "Session should exist"
    print(f"  Session found: {session.session_id}")
    print(f"  Created at: {session.created_at}")
    
    # Test 3: Update session
    print("\n✓ Updating session...")
    session.shown_products.add("PRD1")
    session.shown_products.add("PRD2")
    session_mgr.update_session(session_id, session)
    
    updated_session = session_mgr.get_session(session_id)
    assert "PRD1" in updated_session.shown_products
    print(f"  Shown products: {updated_session.shown_products}")
    
    # Test 4: Session stats
    print("\n✓ Getting session stats...")
    stats = session_mgr.get_stats(session_id)
    print(f"  Stats: {stats}")
    
    # Test 5: Session expiry
    print("\n✓ Testing session expiry (waiting 6 seconds)...")
    time.sleep(6)
    expired_session = session_mgr.get_session(session_id)
    assert expired_session is None, "Session should be expired"
    print("  Session expired successfully")
    
    # Test 6: Cleanup
    print("\n✓ Testing cleanup...")
    session_id1 = session_mgr.create_session()
    session_id2 = session_mgr.create_session()
    print(f"  Active sessions: {session_mgr.get_session_count()}")
    time.sleep(6)
    cleaned = session_mgr.cleanup_expired_sessions()
    print(f"  Cleaned up {cleaned} sessions")
    print(f"  Active sessions: {session_mgr.get_session_count()}")
    
    print("\n✅ SessionManager tests passed!")
    return session_mgr


def test_conversation_memory(session_mgr):
    """Test ConversationMemoryManager functionality."""
    print_section("TEST 2: Conversation Memory Manager")
    
    # Initialize
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )
    memory_mgr = ConversationMemoryManager(session_mgr, llm)
    
    # Create new session
    session_id = session_mgr.create_session()
    print(f"✓ Created session: {session_id}")
    
    # Test 1: Add messages
    print("\n✓ Adding conversation messages...")
    memory_mgr.add_user_message(session_id, "I want a pink dress for my daughter's birthday")
    memory_mgr.add_ai_message(session_id, "I found 5 beautiful pink dresses perfect for a birthday!")
    memory_mgr.add_user_message(session_id, "Show me ones under 3000 rupees")
    memory_mgr.add_ai_message(session_id, "Here are 3 pink dresses under ₹3000")
    
    # Test 2: Get history
    print("\n✓ Retrieving conversation history...")
    history = memory_mgr.get_conversation_history(session_id)
    print(f"  Messages: {len(history)}")
    for i, msg in enumerate(history, 1):
        print(f"  {i}. {msg['role']}: {msg['content'][:50]}...")
    
    # Test 3: Extract constraints
    print("\n✓ Extracting accumulated constraints...")
    constraints = memory_mgr.extract_accumulated_constraints(session_id)
    print(f"  Constraints: {constraints}")
    
    # Verify constraints
    assert "color" in constraints or "pink" in str(constraints).lower(), "Should extract color"
    assert "price" in constraints or "3000" in str(constraints), "Should extract price"
    
    print("\n✅ ConversationMemoryManager tests passed!")
    return memory_mgr


def test_rejection_tracker(session_mgr):
    """Test RejectionTracker functionality."""
    print_section("TEST 3: Rejection Tracker")
    
    # Initialize
    tracker = RejectionTracker(session_mgr)
    session_id = session_mgr.create_session()
    print(f"✓ Created session: {session_id}")
    
    # Test 1: Mark shown
    print("\n✓ Marking products as shown...")
    tracker.mark_shown(session_id, ["PRD1", "PRD2", "PRD3", "PRD4", "PRD5"])
    shown = tracker.get_shown_products(session_id)
    print(f"  Shown products: {shown}")
    assert len(shown) == 5
    
    # Test 2: Explicit rejection
    print("\n✓ Marking explicit rejection...")
    tracker.mark_rejected(session_id, ["PRD1"])
    rejected = tracker.get_rejected_products(session_id)
    print(f"  Rejected products: {rejected}")
    assert "PRD1" in rejected
    
    # Test 3: Implicit rejection - ordinal
    print("\n✓ Testing implicit rejection (ordinal)...")
    shown_products = [{"id": f"PRD{i}"} for i in range(1, 6)]
    implicit = tracker.detect_implicit_rejection(
        session_id, 
        "not the first one",
        shown_products
    )
    print(f"  Detected implicit rejections: {implicit}")
    assert "PRD1" in implicit
    
    # Test 4: Implicit rejection - phrase
    print("\n✓ Testing implicit rejection (phrase)...")
    implicit = tracker.detect_implicit_rejection(
        session_id,
        "not these, show different",
        shown_products
    )
    print(f"  Detected implicit rejections: {implicit}")
    assert len(implicit) > 0
    
    # Test 5: Implicit rejection - price
    print("\n✓ Testing implicit rejection (price)...")
    implicit = tracker.detect_implicit_rejection(
        session_id,
        "too expensive, show cheaper options",
        shown_products
    )
    print(f"  Detected implicit rejections: {implicit}")
    assert len(implicit) > 0
    
    # Test 6: Filter products
    print("\n✓ Testing product filtering...")
    tracker.mark_rejected(session_id, ["PRD2", "PRD3"])
    products = [{"id": f"PRD{i}", "title": f"Product {i}"} for i in range(1, 6)]
    filtered = tracker.filter_products(session_id, products)
    print(f"  Original count: {len(products)}")
    print(f"  Filtered count: {len(filtered)}")
    print(f"  Filtered IDs: {[p['id'] for p in filtered]}")
    assert len(filtered) < len(products)
    
    # Test 7: Rejection stats
    print("\n✓ Getting rejection stats...")
    stats = tracker.get_rejection_stats(session_id)
    print(f"  Stats: {stats}")
    
    print("\n✅ RejectionTracker tests passed!")
    return tracker


def test_conversational_agent():
    """Test ConversationalAgentService end-to-end."""
    print_section("TEST 4: Conversational Agent Service")
    
    print("✓ Initializing all components...")
    
    # Initialize components
    session_mgr = SessionManager(session_timeout_seconds=3600)
    
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )
    
    memory_mgr = ConversationMemoryManager(session_mgr, llm)
    rejection_tracker = RejectionTracker(session_mgr)
    product_service = ProductRetrievalService()
    
    agent = ConversationalAgentService(
        product_service=product_service,
        session_manager=session_mgr,
        memory_manager=memory_mgr,
        rejection_tracker=rejection_tracker
    )
    
    print("  All components initialized!")
    
    # Create session
    session_id = session_mgr.create_session()
    print(f"\n✓ Created session: {session_id}")
    
    # Test conversation flow
    print("\n✓ Testing multi-turn conversation...")
    
    # Turn 1
    print("\n  Turn 1: User asks for pink dress")
    result1 = agent.generate_response(
        session_id=session_id,
        message="I want a pink dress for birthday"
    )
    print(f"  Response: {result1['response_text'][:100]}...")
    print(f"  Products: {len(result1['recommended_product_ids'])}")
    print(f"  Follow-ups: {result1['follow_up_questions']}")
    
    # Turn 2
    print("\n  Turn 2: User adds price constraint")
    result2 = agent.generate_response(
        session_id=session_id,
        message="under 3000 rupees"
    )
    print(f"  Response: {result2['response_text'][:100]}...")
    print(f"  Products: {len(result2['recommended_product_ids'])}")
    print(f"  Metadata: {result2['metadata']}")
    
    # Turn 3
    print("\n  Turn 3: User rejects first product")
    result3 = agent.generate_response(
        session_id=session_id,
        message="not the first one, show different"
    )
    print(f"  Response: {result3['response_text'][:100]}...")
    print(f"  Products: {len(result3['recommended_product_ids'])}")
    
    # Verify rejection tracking
    rejection_stats = rejection_tracker.get_rejection_stats(session_id)
    print(f"\n  Rejection stats: {rejection_stats}")
    assert rejection_stats['rejected_count'] > 0, "Should have rejected products"
    
    # Verify memory
    history = memory_mgr.get_conversation_history(session_id)
    print(f"\n  Conversation history: {len(history)} messages")
    assert len(history) == 6, "Should have 6 messages (3 turns)"
    
    # Verify constraints
    constraints = result2['metadata'].get('constraints', {})
    print(f"\n  Accumulated constraints: {constraints}")
    
    print("\n✅ ConversationalAgentService tests passed!")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  CONVERSATIONAL AGENT INFRASTRUCTURE TESTS")
    print("="*60)
    
    try:
        # Test 1: SessionManager
        session_mgr = test_session_manager()
        
        # Test 2: ConversationMemoryManager
        memory_mgr = test_conversation_memory(session_mgr)
        
        # Test 3: RejectionTracker
        tracker = test_rejection_tracker(session_mgr)
        
        # Test 4: ConversationalAgentService (end-to-end)
        test_conversational_agent()
        
        # Summary
        print_section("TEST SUMMARY")
        print("✅ All tests passed successfully!")
        print("\nInfrastructure is ready for integration.")
        print("\nNext steps:")
        print("1. Integrate the new search endpoint into app/main.py")
        print("2. Update frontend to send session_id")
        print("3. Test end-to-end with browser")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
