import requests, json

resp = requests.post("http://127.0.0.1:8000/api/admin/test", data={
    "question": "What are the notification requirements for disease outbreaks under Ghanaian public health law?",
    "sector": "healthcare"
}, timeout=60)
print(f"Status: {resp.status_code}")
print(f"Headers: {dict(resp.headers)}")
raw = resp.text[:3000]
print(f"Raw response: {raw}")
