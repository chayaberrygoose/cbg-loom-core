# [FILE_ID]: scripts/LIST_GEMINI_MODELS // VERSION: 2.0 // STATUS: STABLE
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
client = genai.Client(api_key=api_key)

print("[SYSTEM_LOG]: Listing available models...")
for m in client.models.list():
    print(f"{m.name}: {m.supported_actions if hasattr(m, 'supported_actions') else 'N/A'}")
