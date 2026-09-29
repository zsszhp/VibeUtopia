import os
import requests
import json

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

raw = os.getenv("LONGCAT_API_KEY", "")
keys = [k.strip() for k in raw.split(",") if k.strip()]
if not keys:
    raise SystemExit("LONGCAT_API_KEY 未配置，请在 .env 中设置后重试")
url = "https://api.longcat.chat/openai/v1/chat/completions"

for i, key in enumerate(keys):
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "LongCat-Flash-Thinking-2601",
                "messages": [{"role": "user", "content": "Hello, test"}],
                "max_tokens": 50,
            },
            timeout=30,
        )
        print(f"Key{i+1}: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"  Response: {content[:50]}")
        else:
            print(f"  Error: {resp.text[:200]}")
    except Exception as e:
        print(f"Key{i+1}: Exception {e}")
