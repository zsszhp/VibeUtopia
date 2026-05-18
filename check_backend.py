import urllib.request, json, sys

try:
    req = urllib.request.urlopen("http://localhost:8000/api/v3/available-models", timeout=5)
    data = json.loads(req.read().decode())
    print("BACKEND_OK")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
except Exception as e:
    print(f"BACKEND_ERROR: {e}")
    sys.exit(1)
