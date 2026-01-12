"""Product retrieval service using ChromaDB semantic search."""

import os
import json
import re
import logging
import time
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from groq import Groq
from groq import APIConnectionError, RateLimitError, InternalServerError

load_dotenv()

logger = logging.getLogger(__name__)


class ProductRetrievalService:
    """Service for product retrieval using ChromaDB semantic search."""
    
    def __init__(self):
        """Initialize ChromaDB client and embedding function."""
        try:
            self.db_dir = os.path.abspath(os.getenv("CHROMA_DB_DIR"))
            self.collection_name = os.getenv("COLLECTION_NAME")
            self.embedding_model = os.getenv("EMBEDDING_MODEL")
            
            if not self.db_dir or not self.collection_name or not self.embedding_model:
                raise ValueError("Missing required env variables: CHROMA_DB_DIR, COLLECTION_NAME, EMBEDDING_MODEL")
            
            # Initialize embedding function
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=self.db_dir)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
            
            # Initialize Groq client for attribute extraction
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            
            logger.info(f"ProductRetrievalService initialized: {self.collection.count()} vectors in collection")
            
        except Exception as e:
            logger.error(f"Failed to initialize ProductRetrievalService: {str(e)}")
            raise
    
    def normalize_filter_value(self, val):
        """Normalize filter value (must match ingest logic)."""
        if isinstance(val, str):
            return val.strip().lower()
        return val
    
    def rewrite_query_llm(self, user_query: str) -> str:
        """
        Rewrite query for semantic search optimization.
        Currently returns query as-is, can be enhanced with LLM.
        """
        return user_query.strip()
    
    def extract_attributes_llm(self, user_query: str) -> dict:
        """
        Extract attributes from user query for Chroma where filter.
        Uses Groq LLM to extract structured filters.
        """
        prompt_template = os.getenv("EXTRACT_ATTRIBUTES_SYSTEM_PROMPT")
        if not prompt_template:
            raise ValueError("EXTRACT_ATTRIBUTES_SYSTEM_PROMPT not found in .env")
        
        max_retries = 3
        sleep_seconds = 3
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": prompt_template},
                        {"role": "user", "content": user_query}
                    ]
                )
                
                raw = response.choices[0].message.content.strip()
                return json.loads(raw)
            
            except (APIConnectionError, RateLimitError, InternalServerError) as e:
                last_error = e
                logger.warning(f"[Retry {attempt}/{max_retries}] Groq error: {e}")
                
                if attempt < max_retries:
                    time.sleep(sleep_seconds)
                else:
                    break
            
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON returned from Groq: {raw}")
                raise ValueError(f"Invalid JSON returned:\n{raw}")
            
            except Exception as e:
                logger.error(f"Unexpected error in extract_attributes_llm: {e}")
                raise RuntimeError(f"Unexpected error: {e}")
        
        raise RuntimeError(
            f"Groq API failed after {max_retries} attempts: {last_error}"
        )
    
    def build_chroma_filter(self, raw_filters: dict) -> dict:
        """
        Convert extracted filters to Chroma-compatible where clause.
        Handles age ranges and other filter types.
        Validates that numeric values are not None before creating filters.
        """
        filters = []
        
        for key, value in raw_filters.items():
            if value is None:
                continue
            
            # Age handling
            if key == "age":
                if "$gte" in value and "$lte" in value:
                    min_age = value["$gte"]
                    max_age = value["$lte"]
                    # Validate that values are not None and are numeric
                    if min_age is not None and max_age is not None and isinstance(min_age, (int, float)) and isinstance(max_age, (int, float)):
                        filters.append({"age_max": {"$lte": max_age}})
                        filters.append({"age_min": {"$gte": min_age}})
                elif "$eq" in value:
                    age = value["$eq"]
                    # Validate age is not None and is numeric
                    if age is not None and isinstance(age, (int, float)):
                        filters.append({"age_min": {"$lte": age}})
                        filters.append({"age_max": {"$gte": age}})
                elif "$lt" in value:
                    age_lt = value["$lt"]
                    # Validate age_lt is not None and is numeric
                    if age_lt is not None and isinstance(age_lt, (int, float)):
                        filters.append({"age_min": {"$lt": age_lt}})
                elif "$gt" in value:
                    age_gt = value["$gt"]
                    # Validate age_gt is not None and is numeric
                    if age_gt is not None and isinstance(age_gt, (int, float)):
                        filters.append({"age_max": {"$gt": age_gt}})
                continue
            
            # Range filters (e.g., price: {"$lte": 5000})
            if isinstance(value, dict):
                for op, num in value.items():
                    # Validate that num is not None and is numeric
                    if num is not None and isinstance(num, (int, float)):
                        filters.append({key: {op: num}})
            else:
                filters.append({key: self.normalize_filter_value(value)})
        
        # Build final Chroma where clause
        if not filters:
            return {}
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}
    
    def search_products(
        self, 
        query: str, 
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search products using semantic search with attribute filtering.
        
        Args:
            query: User search query
            n_results: Number of results to return
            
        Returns:
            List of product dictionaries with document and metadata
        """
        try:
            # Step 1: Rewrite query for semantic search
            rewritten_query = self.rewrite_query_llm(query)
            
            # Step 2: Extract attributes using LLM
            raw_filters = self.extract_attributes_llm(query)
            logger.info(f"Extracted filters: {raw_filters}")
            
            # Step 3: Build Chroma filter
            where_filter = self.build_chroma_filter(raw_filters)
            logger.info(f"Chroma filter: {json.dumps(where_filter, indent=2)}")
            
            # Step 4: Perform vector search
            results = self.collection.query(
                query_texts=[rewritten_query],
                n_results=n_results,
                where=where_filter if where_filter else None
            )
            
            # Step 5: Format results
            products = []
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    product = {
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {},
                        "id": results["ids"][0][i] if results.get("ids") and results["ids"][0] else None,
                        "distance": results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                    }
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            raise

