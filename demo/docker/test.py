import os

from agents import Agent, Runner, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

set_tracing_disabled(True)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11500/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")  # ignored locally by Ollama

client = AsyncOpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key=OLLAMA_API_KEY,
)

model = OpenAIChatCompletionsModel(
    model=OLLAMA_MODEL,
    openai_client=client,
)

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    model=model,
)

result = Runner.run_sync(agent, "Say hello and confirm the model you are using.")
print(result.final_output)
