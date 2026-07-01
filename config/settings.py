"""
Global settings for GRaC system.
Loads from .env and provides defaults.
"""
import os
import json
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file from project root
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

class Settings:
    """GRaC global configuration."""
    
    # Paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    LAWS_DIR = DATA_DIR / "laws"
    VECTORSTORE_DIR = DATA_DIR / "vectorstore"
    SKILLS_DIR = PROJECT_ROOT / "skills"
    LOGS_DIR = DATA_DIR / "logs"
    CACHE_DIR = DATA_DIR / "cache"
    
    # Sector configuration
    SECTOR_CONFIG_PATH = Path(__file__).parent / "sector_config.json"
    with open(SECTOR_CONFIG_PATH) as f:
        SECTOR_CONFIG = json.load(f)
    
    DEFAULT_SECTOR = SECTOR_CONFIG["default_sector"]
    ACTIVE_SECTOR = os.getenv("ACTIVE_SECTOR", DEFAULT_SECTOR)
    
    # API Configuration
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"
    
    # LLM Configuration — Multi-Provider
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")  # "anthropic", "openai", "nvidia", or "auto"
    LLM_FALLBACK_ENABLED = os.getenv("LLM_FALLBACK_ENABLED", "True").lower() == "true"
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # OpenAI (for Whisper voice transcription + chat completions)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # NVIDIA (free OpenAI-compatible API via build.nvidia.com)
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-4-maverick-17b-128e-instruct")

    # Embedding Configuration
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "auto")  # "local", "openai", "nvidia", or "auto"
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_API_MODEL = os.getenv("EMBEDDING_API_MODEL", "nvidia/nv-embed-v1")
    
    # ChromaDB Configuration
    CHROMA_DB_PATH = str(VECTORSTORE_DIR)
    CHROMA_COLLECTION_PREFIX = "grac"
    
    # Web Search
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

    # PDF Processing
    PDF_CHUNK_SIZE = int(os.getenv("PDF_CHUNK_SIZE", "500"))  # words
    PDF_OVERLAP = int(os.getenv("PDF_OVERLAP", "100"))  # words
    
    # Agent Configuration
    AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "300"))  # seconds
    AGENT_RETRY_ATTEMPTS = int(os.getenv("AGENT_RETRY_ATTEMPTS", "3"))
    DEFAULT_TOTAL_REQUIREMENTS = int(os.getenv("DEFAULT_TOTAL_REQUIREMENTS", "100"))
    
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'data' / 'grac.db'}"
    )
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Confidence thresholds
    MIN_RETRIEVAL_CONFIDENCE = float(os.getenv("MIN_RETRIEVAL_CONFIDENCE", "0.3"))
    MIN_ANSWER_CONFIDENCE = float(os.getenv("MIN_ANSWER_CONFIDENCE", "0.7"))
    
    # Multi-sector support
    ENABLE_MULTI_SECTOR = os.getenv("ENABLE_MULTI_SECTOR", "False").lower() == "true"
    ACTIVE_SECTORS: List[str] = (
        os.getenv("ACTIVE_SECTORS", DEFAULT_SECTOR).split(",")
        if ENABLE_MULTI_SECTOR
        else [DEFAULT_SECTOR]
    )
    
    @classmethod
    def get_sector_laws_path(cls, sector: str) -> Path:
        """Get the laws directory for a specific sector."""
        return cls.LAWS_DIR / sector
    
    @classmethod
    def get_sector_skills_path(cls, sector: str) -> Path:
        """Get the skills directory for a specific sector."""
        return cls.SKILLS_DIR / sector
    
    @classmethod
    def get_active_sectors(cls) -> List[str]:
        """Get list of active sectors."""
        if cls.ENABLE_MULTI_SECTOR:
            return cls.ACTIVE_SECTORS
        return [cls.ACTIVE_SECTOR]
    
    @classmethod
    def set_active_sector(cls, sector: str) -> None:
        """
        Switch to a different sector (MVP mode).
        In MVP, only one sector is active at a time.
        """
        if not cls.ENABLE_MULTI_SECTOR:
            cls.ACTIVE_SECTOR = sector
            cls.ACTIVE_SECTORS = [sector]
            os.environ["ACTIVE_SECTOR"] = sector
    
    @classmethod
    def set_active_sectors(cls, sectors: List[str]) -> None:
        """
        Set multiple active sectors (Future mode).
        Only works if ENABLE_MULTI_SECTOR is True.
        """
        if cls.ENABLE_MULTI_SECTOR:
            cls.ACTIVE_SECTORS = sectors
            os.environ["ACTIVE_SECTORS"] = ",".join(sectors)


# Create singleton instance
settings = Settings()

# Ensure all required directories exist
def ensure_directories():
    """Create all required directories if they don't exist."""
    dirs_to_create = [
        settings.DATA_DIR,
        settings.LAWS_DIR,
        settings.VECTORSTORE_DIR,
        settings.SKILLS_DIR,
        settings.LOGS_DIR,
        settings.CACHE_DIR,
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Print current configuration
    print("GRaC Configuration")
    print("=" * 50)
    print(f"Project Root: {settings.PROJECT_ROOT}")
    print(f"Active Sector: {settings.ACTIVE_SECTOR}")
    print(f"Laws Directory: {settings.LAWS_DIR}")
    print(f"Skills Directory: {settings.SKILLS_DIR}")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print(f"  Anthropic Model: {settings.ANTHROPIC_MODEL}")
    print(f"  OpenAI Model:    {settings.OPENAI_MODEL}")
    print(f"  NVIDIA Model:    {settings.NVIDIA_MODEL}")
    print(f"  Temperature:     {settings.LLM_TEMPERATURE}")
    print(f"  Max Tokens:      {settings.LLM_MAX_TOKENS}")
    print(f"Embedding Provider: {settings.EMBEDDING_PROVIDER}")
    print(f"  Local Model:     {settings.EMBEDDING_MODEL}")
    print(f"  API Model:       {settings.EMBEDDING_API_MODEL}")
    print(f"Multi-Sector Enabled: {settings.ENABLE_MULTI_SECTOR}")
    print("=" * 50)
