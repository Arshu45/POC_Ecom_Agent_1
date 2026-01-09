from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_classic.agents import create_react_agent, AgentExecutor
from langsmith import Client
from dotenv import load_dotenv
import os
from langchain_core.prompts import PromptTemplate

# from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import requests

load_dotenv()



search_tool = DuckDuckGoSearchRun()



@tool
def get_weather_data(city):
    """
    This function fetches the current weather data for a given city
    """
    url = f'https://api.weatherstack.com/current?access_key=4d1d8ae207a8c845a52df8a67bf3623e&query={city}'

    response = requests.get(url)

    return response.json()


llm = HuggingFaceEndpoint(
    model="meta-llama/Llama-3.1-70B-Instruct",
    task="text-generation",
    huggingfacehub_api_token=os.getenv("HUGGING_FACE_ACCESS_TOKEN"),
)

# Step 2: Pull the ReAct prompt from LangChain Hub
client = Client()
prompt = client.pull_prompt("hwchase17/react")

# Step 3: Create the ReAct agent manually with the pulled prompt
agent = create_react_agent(
    llm=llm,
    tools=[search_tool, get_weather_data],
    prompt=prompt
)

# Step 4: Wrap it with AgentExecutor
agent_executor = AgentExecutor(
    agent=agent,
    tools=[search_tool, get_weather_data],
    verbose=True
)

# Step 5: Invoke
response = agent_executor.invoke({"input": "Find the capital of Madhya Pradesh, then find it's current weather condition"})
print(response)


