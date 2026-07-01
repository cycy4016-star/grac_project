#!/usr/bin/env python
"""
Validate the GRaC project structure.

Checks that all required directories, config files, and data files exist
in their expected locations. Exits with code 0 if everything is valid,
or 1 if any issues are found.

Usage:
    python scripts/validate_structure.py
    python scripts/validate_structure.py --verbose
    python scripts/validate_structure.py --fix
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from utils.sector_manager import sector_manager


class StructureValidator:
    """Checks project structure and reports issues."""

    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def _ok(self, msg: str) -> None:
        if self.verbose:
            print(f"  [OK] {msg}")

    def _err(self, msg: str) -> None:
        self.errors.append(msg)
        print(f"  [ERR] {msg}")

    def _warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [WARN] {msg}")

    def _ensure_dir(self, path: Path, label: str) -> bool:
        if path.exists():
            if path.is_dir():
                self._ok(f"{label}: {path}")
                return True
            else:
                self._err(f"{label}: exists but is not a directory: {path}")
                return False
        else:
            if self.fix:
                path.mkdir(parents=True, exist_ok=True)
                self._warn(f"{label}: created missing directory: {path}")
                return True
            else:
                self._err(f"{label}: missing: {path}")
                return False

    def _ensure_file(self, path: Path, label: str) -> bool:
        if path.exists():
            if path.is_file():
                self._ok(f"{label}: {path}")
                return True
            else:
                self._err(f"{label}: exists but is not a file: {path}")
                return False
        else:
            self._err(f"{label}: missing: {path}")
            return False

    def run(self) -> bool:
        print("\nValidating GRaC project structure...\n")

        # 1. Project root directories
        print("[1/5] Core directories")
        core_dirs = [
            (settings.DATA_DIR, "Data directory"),
            (settings.LAWS_DIR, "Laws directory"),
            (settings.VECTORSTORE_DIR, "Vectorstore directory"),
            (settings.SKILLS_DIR, "Skills directory"),
            (settings.LOGS_DIR, "Logs directory"),
            (settings.CACHE_DIR, "Cache directory"),
        ]
        for path, label in core_dirs:
            self._ensure_dir(path, label)

        # 2. Config files
        print("\n[2/5] Configuration files")
        config_files = [
            (settings.SECTOR_CONFIG_PATH, "Sector config"),
            (PROJECT_ROOT / ".env.example", "Environment template"),
        ]
        for path, label in config_files:
            self._ensure_file(path, label)
        self._ensure_file(PROJECT_ROOT / ".env", ".env file (optional)")

        # 3. Sector directories and config
        print("\n[3/5] Sector structure")
        try:
            sectors = sector_manager.list_all_sectors()
            enabled = sector_manager.list_enabled_sectors()

            for sector in sectors:
                is_enabled = sector in enabled
                status = "[ENABLED]" if is_enabled else "[DISABLED]"
                print(f"  {status} Sector: {sector}")

                # Build path list without triggering validation on disabled sectors
                laws_base = settings.get_sector_laws_path(sector)
                skills_base = settings.get_sector_skills_path(sector)
                sector_dirs = [
                    (laws_base, f"  laws/{sector}"),
                    (laws_base / "raw", f"  laws/{sector}/raw"),
                    (laws_base / "parsed", f"  laws/{sector}/parsed"),
                    (laws_base / "chunks", f"  laws/{sector}/chunks"),
                    (skills_base, f"  skills/{sector}"),
                ]
                for path, label in sector_dirs:
                    if is_enabled or path.exists():
                        self._ensure_dir(path, f"  {label}")

                # Check for law PDFs in enabled sectors
                if is_enabled:
                    raw_dir = sector_manager.get_raw_path(sector)
                    if raw_dir.exists():
                        pdfs = list(raw_dir.glob("*.pdf"))
                        if pdfs:
                            self._ok(f"    {len(pdfs)} law PDF(s) in raw/")
                        else:
                            self._warn(f"    No law PDFs in raw/ -- place PDFs here before ingesting")

                    # Check for parsed files
                    parsed_dir = sector_manager.get_parsed_path(sector)
                    if parsed_dir.exists():
                        parsed_files = list(parsed_dir.glob("*.txt"))
                        if parsed_files:
                            self._ok(f"    {len(parsed_files)} parsed text file(s)")
        except Exception as e:
            self._err(f"Failed to validate sectors: {e}")

        # 4. Skills templates
        print("\n[4/5] Skills templates")
        expected_templates = {
            "cybersecurity": ["pentest_report", "incident_response", "policy_draft", "audit_report"],
            "fintech": ["vendor_assessment", "compliance_audit", "regulatory_response", "gap_analysis"],
            "data_protection": ["dpia_template", "breach_notice", "compliance_checklist"],
        }
        for sector, templates in expected_templates.items():
            skills_path = settings.get_sector_skills_path(sector)
            if not skills_path.exists():
                continue
            for name in templates:
                path = skills_path / f"{name}.md"
                if path.exists():
                    self._ok(f"  {sector}/{name}.md")
                else:
                    self._warn(f"  {sector}/{name}.md — template not yet created")

        # 5. Path configuration sanity checks
        print("\n[5/5] Configuration sanity")
        if not settings.ANTHROPIC_API_KEY:
            self._warn("ANTHROPIC_API_KEY is not set in .env")
        if not settings.OPENAI_API_KEY:
            self._warn("OPENAI_API_KEY is not set in .env (required for voice transcription)")
        if settings.PDF_CHUNK_SIZE <= settings.PDF_OVERLAP:
            self._warn(f"PDF_CHUNK_SIZE ({settings.PDF_CHUNK_SIZE}) <= PDF_OVERLAP ({settings.PDF_OVERLAP}) — chunks will not overlap correctly")
        if not sector_manager.is_valid_sector(settings.ACTIVE_SECTOR):
            self._err(f"ACTIVE_SECTOR '{settings.ACTIVE_SECTOR}' is not a valid enabled sector")

        # Summary
        print(f"\n{'=' * 50}")
        if self.errors:
            print(f"Validation COMPLETE — {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
            for e in self.errors:
                print(f"  [ERR] {e}")
        elif self.warnings:
            print(f"Validation COMPLETE — {len(self.warnings)} warning(s), no errors")
        else:
            print("Validation COMPLETE — all checks passed")

        for w in self.warnings:
            print(f"  [WARN] {w}")
        print(f"{'=' * 50}")

        return len(self.errors) == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate GRaC project structure",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all checks including passing")
    parser.add_argument("--fix", action="store_true", help="Create missing directories automatically")
    args = parser.parse_args()

    validator = StructureValidator(verbose=args.verbose, fix=args.fix)
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
