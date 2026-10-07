import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
PROMPT_FILE = PROJECT_ROOT / "prompts"
DEFAULT_MEMORY_PATH = PROJECT_ROOT / "memory.md"


class Settings:
    api_key: str
    model: str = "gpt-5.6"
    prompt_file: Path = PROMPT_FILE
    memory_file = Path = DEFAULT_MEMORY_PATH

    def __init__(self, api_key: str):
        self.api_key = api_key


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY was not found in .env")

    return Settings(api_key=api_key)


settings = load_settings()

# print(PROJECT_ROOT)
# print(settings.model)
# print(settings.prompt_file)