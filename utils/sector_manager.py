"""
Sector Manager

Centralises all sector-related logic so agents, the supervisor, and the API
all use one consistent source of truth instead of each re-implementing
validation and config lookups.

Usage:
    from utils.sector_manager import SectorManager

    sm = SectorManager()

    # Validate & switch
    sm.validate_sector("fintech")           # raises ValueError if unknown/disabled
    sm.switch_sector("fintech")             # updates settings singleton

    # Inspect
    sm.get_sector_config("fintech")         # full config dict from sector_config.json
    sm.get_laws("fintech")                  # list of law names for a sector
    sm.get_related_sectors("fintech")       # ["data_protection", "cybersecurity"]
    sm.list_enabled_sectors()               # ["cybersecurity", "fintech", "data_protection"]
    sm.is_enabled("healthcare")             # False
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class SectorManager:
    """
    Manages sector lifecycle: validation, switching, config access.

    Wraps ``config.settings`` so callers never reach into it directly for
    sector operations — all state changes go through this class.
    """

    def __init__(self):
        # Import here to avoid circular imports at module load time
        from config.settings import settings
        self._settings = settings

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_sector(
        self,
        sector: str,
        *,
        require_enabled: bool = True,
    ) -> None:
        """
        Assert that *sector* is a known sector, raising ``ValueError`` otherwise.

        Args:
            sector: Sector ID string (e.g. ``"cybersecurity"``).
            require_enabled: If True (default), also raise if the sector exists
                but is currently disabled in ``sector_config.json``.

        Raises:
            ValueError: Unknown sector, or disabled sector when
                ``require_enabled=True``.
        """
        config = self._get_sector_config_entry(sector)
        if config is None:
            valid = [s["id"] for s in self._settings.SECTOR_CONFIG["sectors"]]
            raise ValueError(
                f"Unknown sector '{sector}'. "
                f"Valid sectors are: {', '.join(valid)}"
            )
        if require_enabled and not config.get("enabled", False):
            raise ValueError(
                f"Sector '{sector}' exists but is currently disabled. "
                "Set enabled=true in sector_config.json to activate it."
            )

    def is_valid_sector(self, sector: str, *, require_enabled: bool = True) -> bool:
        """Return True/False rather than raising — useful for conditional checks."""
        try:
            self.validate_sector(sector, require_enabled=require_enabled)
            return True
        except ValueError:
            return False

    def is_enabled(self, sector: str) -> bool:
        """Return True if the sector exists and is enabled."""
        config = self._get_sector_config_entry(sector)
        return config is not None and config.get("enabled", False)

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_sector(self, new_sector: str) -> str:
        """
        Validate *new_sector* and update the active sector in settings.

        Respects ``ENABLE_MULTI_SECTOR``: in MVP single-sector mode only one
        sector is active at a time.

        Args:
            new_sector: Sector ID to switch to.

        Returns:
            The new active sector ID.

        Raises:
            ValueError: If the sector is unknown or disabled.
            RuntimeError: If called in multi-sector mode where switching is
                not meaningful.
        """
        self.validate_sector(new_sector)

        if self._settings.ENABLE_MULTI_SECTOR:
            raise RuntimeError(
                "switch_sector() operates in single-sector (MVP) mode only. "
                "Use set_active_sectors() for multi-sector mode."
            )

        previous = self._settings.ACTIVE_SECTOR
        self._settings.set_active_sector(new_sector)

        # Ensure the sector's directory tree exists
        self._ensure_sector_dirs(new_sector)

        return new_sector

    def set_active_sectors(self, sectors: list[str]) -> list[str]:
        """
        Set multiple active sectors (multi-sector mode only).

        Args:
            sectors: List of sector IDs.

        Returns:
            The validated list of sector IDs.

        Raises:
            RuntimeError: If called when ``ENABLE_MULTI_SECTOR`` is False.
            ValueError: If any sector in the list is unknown or disabled.
        """
        if not self._settings.ENABLE_MULTI_SECTOR:
            raise RuntimeError(
                "set_active_sectors() requires ENABLE_MULTI_SECTOR=True. "
                "Set it in your .env file."
            )

        for sector in sectors:
            self.validate_sector(sector)

        self._settings.set_active_sectors(sectors)
        for sector in sectors:
            self._ensure_sector_dirs(sector)

        return sectors

    # ------------------------------------------------------------------
    # Config access
    # ------------------------------------------------------------------

    def get_sector_config(self, sector: str) -> dict:
        """
        Return the full config dict for a sector from ``sector_config.json``.

        Example return value::

            {
                "id": "cybersecurity",
                "name": "Cybersecurity",
                "description": "...",
                "laws": ["Act 1038 ...", ...],
                "applicable_industries": ["fintech", ...],
                "enabled": true
            }

        Raises:
            ValueError: If sector is unknown.
        """
        config = self._get_sector_config_entry(sector)
        if config is None:
            raise ValueError(f"Unknown sector: '{sector}'")
        return config

    def get_laws(self, sector: str) -> list[str]:
        """Return the list of law names associated with a sector."""
        return self.get_sector_config(sector).get("laws", [])

    def get_related_sectors(self, industry: str) -> list[str]:
        """
        Given an *industry* identifier, return which sectors apply to it.

        Uses the ``sector_mapping`` table in ``sector_config.json``.

        Example::

            sm.get_related_sectors("fintech")
            # → ["data_protection", "cybersecurity"]
        """
        mapping: dict = self._settings.SECTOR_CONFIG.get("sector_mapping", {})
        return mapping.get(industry, [])

    def get_applicable_industries(self, sector: str) -> list[str]:
        """Return industries that the sector applies to."""
        return self.get_sector_config(sector).get("applicable_industries", [])

    def list_enabled_sectors(self) -> list[str]:
        """Return IDs of all currently enabled sectors."""
        return [
            s["id"]
            for s in self._settings.SECTOR_CONFIG["sectors"]
            if s.get("enabled", False)
        ]

    def list_all_sectors(self) -> list[str]:
        """Return IDs of all sectors (enabled and disabled)."""
        return [s["id"] for s in self._settings.SECTOR_CONFIG["sectors"]]

    # ------------------------------------------------------------------
    # Path helpers  (thin wrappers that keep callers decoupled from settings)
    # ------------------------------------------------------------------

    def get_laws_path(self, sector: str, *, require_enabled: bool = False) -> Path:
        """Return the ``data/laws/<sector>/`` path, creating it if absent."""
        self.validate_sector(sector, require_enabled=require_enabled)
        path = self._settings.get_sector_laws_path(sector)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_skills_path(self, sector: str) -> Path:
        """Return the ``skills/<sector>/`` path, creating it if absent."""
        self.validate_sector(sector)
        path = self._settings.get_sector_skills_path(sector)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_raw_path(self, sector: str, *, require_enabled: bool = False) -> Path:
        """Return ``data/laws/<sector>/raw/``."""
        return self.get_laws_path(sector, require_enabled=require_enabled) / "raw"

    def get_parsed_path(self, sector: str, *, require_enabled: bool = False) -> Path:
        """Return ``data/laws/<sector>/parsed/``."""
        return self.get_laws_path(sector, require_enabled=require_enabled) / "parsed"

    def get_chunks_path(self, sector: str, *, require_enabled: bool = False) -> Path:
        """Return ``data/laws/<sector>/chunks/``."""
        return self.get_laws_path(sector, require_enabled=require_enabled) / "chunks"

    # ------------------------------------------------------------------
    # Active sector convenience properties
    # ------------------------------------------------------------------

    @property
    def active_sector(self) -> str:
        """The currently active sector ID."""
        return self._settings.ACTIVE_SECTOR

    @property
    def active_sectors(self) -> list[str]:
        """All currently active sector IDs (list of one in MVP mode)."""
        return self._settings.get_active_sectors()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_sector_config_entry(self, sector: str) -> Optional[dict]:
        """Return the raw config dict for *sector*, or None if not found."""
        for entry in self._settings.SECTOR_CONFIG.get("sectors", []):
            if entry["id"] == sector:
                return entry
        return None

    def _ensure_sector_dirs(self, sector: str) -> None:
        """Create the full directory tree for a sector if it doesn't exist."""
        base = self._settings.get_sector_laws_path(sector)
        for sub in ("raw", "parsed", "chunks"):
            (base / sub).mkdir(parents=True, exist_ok=True)
        self._settings.get_sector_skills_path(sector).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Module-level singleton — import this for convenience
# ---------------------------------------------------------------------------

sector_manager = SectorManager()
