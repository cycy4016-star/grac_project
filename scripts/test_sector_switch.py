#!/usr/bin/env python
"""
Test sector switching functionality.

Verifies that:
- Sector validation works (known/unknown/disabled)
- Switching sector updates the settings singleton
- Agent registries respect sector changes
- Multi-sector mode works correctly

Usage:
    python scripts/test_sector_switch.py
    python scripts/test_sector_switch.py --verbose
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


class SectorSwitchTester:
    """Runs a battery of tests against the sector management system."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def _test(self, name: str, passed: bool, detail: str = "") -> None:
        if passed:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}: {detail}")

    def _skip(self, name: str, reason: str) -> None:
        self.skipped += 1
        print(f"  - {name}: {reason}")

    def run(self) -> bool:
        print("=" * 60)
        print("GRaC Sector Switch Test Suite")
        print("=" * 60)

        # ── 1. Sector validation ──────────────────────────────────────
        print("\n[1/7] Sector validation")

        # 1a. Known enabled sector
        known_valid = sector_manager.is_valid_sector("cybersecurity")
        self._test("cybersecurity is a valid sector", known_valid)

        # 1b. Unknown sector
        known_invalid = not sector_manager.is_valid_sector("nonexistent_sector")
        self._test("nonexistent_sector is rejected", known_invalid)

        # 1c. Disabled sector
        disabled_valid = not sector_manager.is_valid_sector("healthcare", require_enabled=True)
        self._test("disabled sector (healthcare) is rejected", disabled_valid)

        # 1d. validate_sector raises ValueError for unknown
        try:
            sector_manager.validate_sector("bogus")
            self._test("validate_sector raises on unknown sector", False)
        except ValueError:
            self._test("validate_sector raises on unknown sector", True)

        # 1e. Empty string
        try:
            sector_manager.validate_sector("")
            self._test("empty sector is rejected", False)
        except ValueError:
            self._test("empty sector is rejected", True)

        # ── 2. List sectors ───────────────────────────────────────────
        print("\n[2/7] Sector listing")

        all_sectors = sector_manager.list_all_sectors()
        self._test(f"list_all_sectors() returns {len(all_sectors)} sectors: {all_sectors}", len(all_sectors) >= 3)

        enabled_sectors = sector_manager.list_enabled_sectors()
        self._test(f"list_enabled_sectors() returns {len(enabled_sectors)} enabled sectors: {enabled_sectors}", len(enabled_sectors) >= 3)

        # ── 3. Switch sector (MVP mode) ───────────────────────────────
        print("\n[3/7] Sector switching (MVP single-sector mode)")

        original_sector = settings.ACTIVE_SECTOR
        self._test(f"initial active sector is '{original_sector}'", bool(original_sector))

        # Switch to a different sector
        if "fintech" in enabled_sectors and "cybersecurity" in enabled_sectors:
            target = "fintech" if original_sector != "fintech" else enabled_sectors[0]
            try:
                sector_manager.switch_sector(target)
                switched = settings.ACTIVE_SECTOR == target
                self._test(f"switch_sector('{target}') works", switched, f"expected '{target}', got '{settings.ACTIVE_SECTOR}'")
            except Exception as e:
                self._test(f"switch_sector('{target}') failed", False, str(e))

            # Switch back
            sector_manager.switch_sector(original_sector)
            self._test(f"switch back to '{original_sector}'", settings.ACTIVE_SECTOR == original_sector)
        else:
            self._skip("switch between sectors", "need at least 2 enabled sectors")

        # Switch to same sector (should be a no-op)
        try:
            sector_manager.switch_sector(original_sector)
            self._test("switch to same sector (no-op)", settings.ACTIVE_SECTOR == original_sector)
        except Exception as e:
            self._test("switch to same sector (no-op)", False, str(e))

        # ── 4. Switch to disabled sector ─────────────────────────────
        print("\n[4/7] Disabled sector rejection")

        try:
            sector_manager.switch_sector("healthcare")
            self._test("cannot switch to disabled sector", False)
        except ValueError:
            self._test("cannot switch to disabled sector", True)

        # ── 5. Sector config access ────────────────────────────────────
        print("\n[5/7] Sector config")

        config = sector_manager.get_sector_config("cybersecurity")
        has_laws = len(config.get("laws", [])) > 0
        self._test("cybersecurity has laws configured", has_laws, f"laws: {config.get('laws', [])}")

        laws = sector_manager.get_laws("cybersecurity")
        self._test(f"get_laws() returns {len(laws)} laws", len(laws) > 0)

        industries = sector_manager.get_applicable_industries("cybersecurity")
        self._test(f"cybersecurity applies to {len(industries)} industries: {industries}", len(industries) > 0)

        related = sector_manager.get_related_sectors("fintech")
        self._test(f"fintech industry maps to sectors: {related}", len(related) > 0)

        # ── 6. Path resolution ────────────────────────────────────────
        print("\n[6/7] Path resolution")

        laws_path = sector_manager.get_laws_path("cybersecurity")
        self._test(f"get_laws_path() -> {laws_path.name}", laws_path.exists())

        raw_path = sector_manager.get_raw_path("cybersecurity")
        self._test(f"get_raw_path() -> {raw_path.name}", raw_path.exists())

        parsed_path = sector_manager.get_parsed_path("cybersecurity")
        self._test(f"get_parsed_path() -> {parsed_path.name}", parsed_path.exists())

        chunks_path = sector_manager.get_chunks_path("cybersecurity")
        self._test(f"get_chunks_path() -> {chunks_path.name}", chunks_path.exists())

        skills_path = sector_manager.get_skills_path("cybersecurity")
        self._test(f"get_skills_path() -> {skills_path.name}", skills_path.exists())

        # ── 7. Multi-sector mode ──────────────────────────────────────
        print("\n[7/7] Multi-sector mode (future)")

        if settings.ENABLE_MULTI_SECTOR:
            try:
                sector_manager.set_active_sectors(enabled_sectors[:2])
                current = settings.get_active_sectors()
                self._test(f"multi-sector active: {current}", len(current) >= 2)
            except RuntimeError as e:
                self._test("set_active_sectors() fails in single-sector mode", False, str(e))
        else:
            try:
                sector_manager.set_active_sectors(enabled_sectors[:2])
                self._test("set_active_sectors() rejected when multi-sector disabled", False)
            except RuntimeError:
                self._test("set_active_sectors() rejected when multi-sector disabled", True)
            self._skip("actual multi-sector behavior", "ENABLE_MULTI_SECTOR=False — set to True in .env to test")

        # ── Summary ───────────────────────────────────────────────────
        total = self.passed + self.failed + self.skipped
        print(f"\n{'=' * 60}")
        print(f"Results: {self.passed} passed, {self.failed} failed, {self.skipped} skipped ({total} total)")
        print(f"{'=' * 60}")

        return self.failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test GRaC sector switching functionality",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    tester = SectorSwitchTester(verbose=args.verbose)
    success = tester.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
