"""
Refactored search endpoint for conversational agent.

This file contains the new search endpoint implementation.
Copy this into app/main.py to replace the existing search endpoint.
"""

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Product search endpoint with conversational agent support.
    
    Supports both:
    - Conversational mode (with session_id, memory, rejection tracking)
    - Legacy stateless mode (backward compatibility)
    """
    try:
        # Determine which mode to use
        use_conversational = (
            ENABLE_CONVERSATIONAL_MODE and 
            conversational_agent is not None
        )
        
        if use_conversational:
            # ============================================
            # CONVERSATIONAL MODE (NEW)
            # ============================================
            
            # 1. Session handling
            session_id = request.session_id or session_manager.create_session()
            logger.info(f"Processing conversational search for session: {session_id}")
            
            # 2. Call conversational agent
            result = conversational_agent.generate_response(
                session_id=session_id,
                message=request.query
            )
            
            # 3. Batch retrieval for recommended products
            recommended_products = []
            if result["recommended_product_ids"]:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/products/batch",
                            json=result["recommended_product_ids"],
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            recommended_products = response.json()
                            logger.info(f"Retrieved {len(recommended_products)} recommended products")
                except Exception as e:
                    logger.error(f"Error fetching recommended products: {e}")
            
            # 4. Return conversational response
            return SearchResponse(
                response_text=result["response_text"],
                products=[],  # Legacy field, can be deprecated
                recommended_products=recommended_products,
                follow_up_questions=result["follow_up_questions"],
                session_id=session_id,
                metadata={
                    "recommended_count": len(recommended_products),
                    "session_stats": session_manager.get_stats(session_id) if session_manager else {},
                    "mode": "conversational"
                },
                success=True
            )
        
        else:
            # ============================================
            # LEGACY STATELESS MODE (BACKWARD COMPATIBILITY)
            # ============================================
            
            logger.info("Processing legacy stateless search")
            
            products = []
            if product_service:
                products = product_service.search_products(
                    request.query, n_results=5
                )

            recommendations = {}
            if agent_service:
                recommendations = agent_service.generate_recommendations(
                    query=request.query,
                    products=products,
                )

            response_text = recommendations.get(
                "response_text",
                f"I found {len(products)} products matching your search.",
            )

            follow_up_questions = recommendations.get(
                "follow_up_questions",
                generate_follow_up_questions(products),
            )

            # Legacy: Format minimal products for chat display
            formatted_products = []
            for p in products:
                try:
                    doc = json.loads(p.get("document", "{}"))
                    metadata = p.get("metadata", {})

                    formatted_products.append(
                        ProductResult(
                            id=p.get("id"),
                            title=doc.get("title", "Unknown Product"),
                            price=format_price(metadata),
                            key_features=extract_key_features(metadata),
                        )
                    )
                except Exception:
                    continue

            # Get full product data for recommended products
            recommended_products = []
            recommended_product_ids = recommendations.get("recommended_product_ids", [])
            
            if recommended_product_ids:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/products/batch",
                            json=recommended_product_ids,
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            recommended_products = response.json()
                            logger.info(f"Retrieved {len(recommended_products)} recommended products")
                except Exception as e:
                    logger.error(f"Error fetching recommended products: {e}")

            return SearchResponse(
                response_text=response_text,
                products=formatted_products,
                recommended_products=recommended_products,
                follow_up_questions=follow_up_questions,
                session_id="stateless",  # Indicate stateless mode
                metadata={
                    "total_results": len(formatted_products),
                    "recommended_count": len(recommended_products),
                    "mode": "stateless"
                },
                success=True,
            )

    except Exception as e:
        logger.error(f"Search error: {e}")
        return SearchResponse(
            response_text="Something went wrong. Please try again.",
            products=[],
            recommended_products=[],
            follow_up_questions=[],
            session_id=request.session_id or "error",
            metadata={"mode": "error"},
            success=False,
            error_message=str(e),
        )
