import os
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # Windows: консоль по умолчанию не UTF-8

BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-flash")
PROXY = os.getenv("HTTPS_PROXY") or None

payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Ответь одним словом: столица Франции?"}],
    "temperature": 0,
    "usage": {"include": True},
}

with httpx.Client(proxy=PROXY, timeout=60) as client:
    response = client.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json=payload,
    )

print("HTTP", response.status_code)
data = response.json()

if "error" in data:
    print("ERROR:", data["error"])
    raise SystemExit(1)

choice = data["choices"][0]
usage = data.get("usage", {})
print("Ответ:", choice["message"].get("content"))
print("finish_reason:", choice["finish_reason"])
print("Токены вход/выход:", usage.get("prompt_tokens"), "/", usage.get("completion_tokens"))
print("Стоимость, $:", usage.get("cost"))
