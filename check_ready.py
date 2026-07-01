import sys; sys.path.insert(0,'.')
from config.settings import settings
import os

print('=== ENV KEY CHECK ===')
print('NVIDIA_API_KEY:', 'SET' if os.getenv('NVIDIA_API_KEY') else 'MISSING')
print('ANTHROPIC_API_KEY:', 'SET' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING')
print('OPENAI_API_KEY:', 'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING')
print()

print('=== SECTOR DIRECTORIES ===')
for sector in ['cybersecurity', 'fintech', 'data_protection']:
    for d in ['raw', 'parsed', 'chunks']:
        p = settings.get_sector_laws_path(sector) / d
        files = list(p.glob('*')) if p.exists() else []
        status = 'EXISTS' if p.exists() else 'MISSING'
        print(f'  {sector}/{d}/: {status} ({len(files)} files)')
print()

print('=== VECTORSTORE ===')
try:
    from tools.embedding_tools import get_chroma_client, get_collection_name
    client = get_chroma_client(str(settings.VECTORSTORE_DIR))
    collections = [c.name for c in client.list_collections()]
    print(f'  Collections: {collections}')
    for sector in ['cybersecurity', 'fintech', 'data_protection']:
        cname = get_collection_name(sector)
        if cname in collections:
            coll = client.get_collection(cname)
            print(f'  {cname}: {coll.count()} chunks')
        else:
            print(f'  {cname}: NOT FOUND')
except Exception as e:
    print(f'  Error checking ChromaDB: {e}')
