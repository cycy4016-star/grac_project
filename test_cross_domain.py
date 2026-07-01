import requests, json

questions = [
    ("Healthcare", "What are the notification requirements for disease outbreaks under Ghanaian public health law?"),
    ("Healthcare", "What does Ghana's public health law say about quarantine and isolation measures?"),
    ("Healthcare", "What are the regulations regarding medical waste disposal in Ghana?"),
    ("Cybersecurity", "What are the data breach notification requirements under Ghana's cybersecurity law?"),
    ("Cross-domain", "How should a hospital handle a data breach involving patient health information under Ghanaian law?"),
]

for sector, q in questions:
    print(f"\n{'='*60}")
    print(f"SECTOR: {sector}")
    print(f"QUERY: {q[:80]}")
    print(f"{'='*60}")
    try:
        resp = requests.post("http://127.0.0.1:8000/api/admin/test", data={
            "question": q,
            "sector": sector if sector != "Cross-domain" else "healthcare"
        }, timeout=60)
        d = resp.json()
        answer = d.get("data", {}).get("answer", "N/A")
        sources = d.get("data", {}).get("sources", []) or []
        confidence = d.get("data", {}).get("confidence", "N/A")
        print(f"ANSWER (first 300 chars): {answer[:300]}")
        print(f"SOURCES ({len(sources)} found):")
        for s in sources[:5]:
            print(f"  - {s.get('law_name','?')} [{s.get('section','?')}] (score={s.get('score','?'):.4f})")
        print(f"CONFIDENCE: {confidence}")
    except Exception as e:
        print(f"ERROR: {e}")
