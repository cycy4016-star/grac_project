"""GRaC Configuration Module"""
from config.settings import settings, ensure_directories

__all__ = ["settings", "ensure_directories"]

# Ensure all directories exist on import
ensure_directories()
