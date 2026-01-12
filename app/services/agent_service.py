"""Agent service for LLM-powered responses with search and weather tools."""

import os
import logging
import requests
from typing import Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_classic.agents import create_react_agent, AgentExecutor
from langsmith import Client

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@tool
def get_weather_data(city: str) -> dict:
    """Fetch current weather for `city` using Weatherstack API.

    The API key can be provided via the `WEATHERSTACK_KEY` environment
    variable. The function returns the parsed JSON response.
    """
    access_key = os.getenv("WEATHERSTACK_KEY")
    url = f"https://api.weatherstack.com/current?access_key={access_key}&query={city}"

    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


class AgentService:
    """Service for LLM agent orchestration with search and weather tools."""
    
    def __init__(self):
        """Initialize agent service with LLM and tools."""
        try:
            # Configure Groq LLM
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=os.getenv("GROQ_API_KEY"),
                temperature=0,
            )
            
            # Initialize tools - DuckDuckGo search and weather
            self.search_tool = DuckDuckGoSearchRun()
            self.weather_tool = get_weather_data
            
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
                tools=[self.search_tool, self.weather_tool],
                prompt=self.prompt,
            )
            
            # Create agent executor
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=[self.search_tool, self.weather_tool],
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

