"""Quick API connectivity test. Run: python scripts/test_api.py"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

provider = os.environ.get("LLM_PROVIDER", "gemini")
print(f"Provider : {provider}")

if provider == "gemini":
    key = os.environ.get("GEMINI_API_KEY", "")
    print(f"Key set  : {'yes (' + key[:8] + '...)' if key else 'NO — add GEMINI_API_KEY to .env'}")
    print(f"Base URL : https://generativelanguage.googleapis.com/v1beta/openai/")
elif provider == "groq":
    key = os.environ.get("GROQ_API_KEY", "")
    print(f"Key set  : {'yes (' + key[:8] + '...)' if key else 'NO — add GROQ_API_KEY to .env'}")

print("\nTesting simple call...")
try:
    from llm import call
    text, tokens = call([{"role": "user", "content": "Reply with just the word: OK"}])
    print(f"SUCCESS  : {repr(text.strip())} ({tokens} tokens)")
except Exception as e:
    print(f"FAILED   : {e}")
