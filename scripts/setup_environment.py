#!/usr/bin/env python
"""
Setup script for GRaC environment.

Initializes:
- Directory structure
- Configuration
- Logging
- Database
"""
import json
import sys
from pathlib import Path
from config.settings import settings, ensure_directories


def setup():
    """Run setup routine."""
    print("=" * 60)
    print("GRaC Setup")
    print("=" * 60)
    
    # Step 1: Create directories
    print("\n[1/4] Creating directories...")
    try:
        ensure_directories()
        print("✓ All directories created")
    except Exception as e:
        print(f"✗ Error creating directories: {e}")
        return False
    
    # Step 2: Verify configuration
    print("\n[2/4] Verifying configuration...")
    try:
        config_file = Path(settings.SECTOR_CONFIG_PATH)
        if not config_file.exists():
            print(f"✗ Sector config not found: {config_file}")
            return False
        
        with open(config_file) as f:
            config = json.load(f)
        
        sectors = [s["id"] for s in config["sectors"]]
        print(f"✓ Configuration valid")
        print(f"  Available sectors: {', '.join(sectors)}")
        print(f"  Default sector: {settings.DEFAULT_SECTOR}")
    except Exception as e:
        print(f"✗ Error verifying configuration: {e}")
        return False
    
    # Step 3: Initialize logging
    print("\n[3/4] Initializing logging...")
    try:
        log_file = settings.LOGS_DIR / "setup.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"✓ Logging initialized")
        print(f"  Log directory: {settings.LOGS_DIR}")
    except Exception as e:
        print(f"✗ Error initializing logging: {e}")
        return False
    
    # Step 4: Display configuration
    print("\n[4/4] Configuration Summary")
    print("-" * 60)
    print(f"Project Root:        {settings.PROJECT_ROOT}")
    print(f"Laws Directory:      {settings.LAWS_DIR}")
    print(f"VectorStore:         {settings.VECTORSTORE_DIR}")
    print(f"Skills Directory:    {settings.SKILLS_DIR}")
    print(f"Active Sector:       {settings.ACTIVE_SECTOR}")
    print(f"LLM Model:           {settings.ANTHROPIC_MODEL}")
    print(f"Multi-Sector Mode:   {settings.ENABLE_MULTI_SECTOR}")
    print("-" * 60)
    
    print("\n✓ Setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and add your API keys")
    print("2. Download law PDFs from Ghana Laws Online")
    print("3. Place PDFs in data/laws/{sector}/raw/")
    print("4. Run: python scripts/ingest_laws.py --sector cybersecurity")
    print("5. Run: python main.py api  # Start API server")
    
    return True


if __name__ == "__main__":
    success = setup()
    sys.exit(0 if success else 1)
