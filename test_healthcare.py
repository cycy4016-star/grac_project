import requests, json

resp = requests.post("http://127.0.0.1:8000/api/admin/test", data={
    "question": "What are the notification requirements for disease outbreaks under Ghanaian public health law?",
    "sector": "healthcare"
})
d = resp.json()
print("=== ANSWER ===")
print(d.get("data", {}).get("answer", "N/A")[:1500])
print("\n=== SOURCES ===")
for s in (d.get("data", {}).get("sources", []) or []):
    print(f"  - {s.get('law_name','?')} (score={s.get('score','?'):.4f})")
print("\n=== CONFIDENCE ===")
print(d.get("data", {}).get("confidence", "N/A"))
