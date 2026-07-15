import urllib.request
import json

payload = {
    "model": "llama3.1:8b",
    "messages": [
        {"role": "system", "content": "You MUST output exactly this: {\"msg\": \"hello\"} and nothing else."},
        {"role": "user", "content": "Say hello"}
    ],
    "max_tokens": 20,
    "temperature": 0.0,
}

req = urllib.request.Request(
    "http://localhost:11434/v1/chat/completions",
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=30.0) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("RAW:", json.dumps(data, indent=2))
        
        content = data["choices"][0]["message"].get("content")
        reasoning = data["choices"][0]["message"].get("reasoning")
        
        print("CONTENT:", repr(content))
        print("REASONING:", repr(reasoning))
except Exception as e:
    print("Error:", e)
