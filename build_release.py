#!/usr/bin/env python3
"""
Build script: erstellt EXE + optional ZIP + Windows Installer (Inno Setup).

Voraussetzungen:
- build.py mit Funktionen:
  - clean_build_dirs()
  - build_exe() -> bool
  - create_distribution_package() (optional)
  - create_zip_archive() (optional)
- installer.iss im Projektroot
- Inno Setup 6 (ISCC.exe)
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INSTALLER_SCRIPT = ROOT / "installer.iss"


def _find_iscc() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]

    for path in candidates:
        if path.exists():
            return path
    return None


def build_installer() -> bool:
    """Build Windows Installer using Inno Setup compiler."""
    print("\n[3/3] Baue Windows Installer...")

    if not INSTALLER_SCRIPT.exists():
        print(f"❌ installer.iss nicht gefunden: {INSTALLER_SCRIPT}")
        return False

    iscc_path = _find_iscc()
    if iscc_path is None:
        print("❌ Inno Setup Compiler (ISCC.exe) nicht gefunden.")
        print("   Installieren: https://jrsoftware.org/isdl.php")
        return False

    cmd = [str(iscc_path), str(INSTALLER_SCRIPT)]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Installer erfolgreich erstellt.")
        return True

    print("❌ Installer-Erstellung fehlgeschlagen.")
    if result.stdout.strip():
        print("\n--- ISCC stdout ---")
        print(result.stdout)
    if result.stderr.strip():
        print("\n--- ISCC stderr ---")
        print(result.stderr)
    return False


def main() -> int:
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║             MeinPortfolio-App Release Build                 ║
╚══════════════════════════════════════════════════════════════╝
        """.rstrip()
    )

    try:
        build = importlib.import_module("build")
    except Exception as exc:
        print("❌ build.py konnte nicht importiert werden.")
        print(f"   Fehler: {exc}")
        print("   Lege eine build.py mit den Build-Funktionen an oder passe das Script an.")
        return 1

    print("\n[1/3] Baue EXE...")
    try:
        build.clean_build_dirs()
        ok = bool(build.build_exe())
    except Exception as exc:
        print(f"❌ EXE-Build fehlgeschlagen: {exc}")
        return 1

    if not ok:
        print("❌ EXE-Build meldet Fehler.")
        return 1

    print("✅ EXE erfolgreich erstellt.")

    print("\n[2/3] Erzeuge Paket/ZIP (falls verfügbar)...")
    try:
        if hasattr(build, "create_distribution_package"):
            build.create_distribution_package()
        if hasattr(build, "create_zip_archive"):
            build.create_zip_archive()
        print("✅ Paket/ZIP Schritt abgeschlossen.")
    except Exception as exc:
        print(f"⚠️ Paket/ZIP konnte nicht vollständig erstellt werden: {exc}")

    installer_ok = build_installer()

    print("\n══════════════════════════════════════════════════════════════")
    if installer_ok:
        print("✅ BUILD KOMPLETT")
        print("- Portable ZIP: dist/")
        print("- Installer: installer_output/")
        return 0

    print("⚠️ EXE/ZIP fertig, Installer fehlgeschlagen.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
