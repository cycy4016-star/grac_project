import sys, time
t0 = time.time()
print(f"Python: {sys.version}", flush=True)

env_ok = True
for pkg in ["chromadb", "anthropic", "openai", "fastapi", "reportlab", "fitz", "pdfplumber", "dotenv"]:
    try:
        exec(f"import {pkg.replace('.','')}" if pkg != "fitz" and pkg != "dotenv" else 
             ("import fitz" if pkg == "fitz" else "from dotenv import load_dotenv"))
        print(f"  {pkg}: OK", flush=True)
    except Exception as e:
        print(f"  {pkg}: FAIL - {e}", flush=True)
        env_ok = False

print(f"\nChecks took {time.time()-t0:.1f}s", flush=True)
if env_ok:
    # Quick config check
    import os
    from pathlib import Path
    os.chdir(Path(__file__).parent)
    from dotenv import load_dotenv
    ep = Path("grac_project/.env")
    if ep.exists():
        load_dotenv(ep)
        print(f"\n.env: NVIDIA={'SET' if os.getenv('NVIDIA_API_KEY') else 'MISSING'} | ANTHROPIC={'SET' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING'} | SECTOR={os.getenv('ACTIVE_SECTOR','?')}")
