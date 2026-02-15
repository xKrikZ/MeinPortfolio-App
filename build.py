#!/usr/bin/env python3
"""
Build helpers for MeinPortfolio-App.
Used by build_release.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "MeinPortfolio-App"
APP_VERSION = "0.001v"
PACKAGE_DIR_NAME = "Portfolio-Manager"

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
TMP_WORK_DIR = BUILD_DIR / "pyinstaller"
TMP_DIST_DIR = BUILD_DIR / "dist_tmp"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def clean_build_dirs() -> None:
    """Remove previous build artifacts."""
    for path in [DIST_DIR, BUILD_DIR, ROOT / "__pycache__"]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def build_exe() -> bool:
    """Build Windows EXE using PyInstaller (onedir)."""
    try:
        import PyInstaller  # type: ignore
    except Exception:
        print("❌ PyInstaller nicht gefunden. Installiere mit: pip install pyinstaller")
        return False

    TMP_WORK_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIST_DIR.mkdir(parents=True, exist_ok=True)

    icon_path = ROOT / "assets" / "icons" / "app_icon.ico"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(TMP_DIST_DIR),
        "--workpath",
        str(TMP_WORK_DIR),
        "--specpath",
        str(TMP_WORK_DIR),
        "--hidden-import",
        "tkcalendar",
        "--collect-data",
        "tkcalendar",
        "main.py",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    def add_data(path: Path, target: str) -> None:
        if path.exists():
            sep = ";" if sys.platform.startswith("win") else ":"
            cmd.extend(["--add-data", f"{path}{sep}{target}"])

    add_data(ROOT / "assets", "assets")
    add_data(ROOT / "config", "config")
    add_data(ROOT / "schema.sql", ".")
    add_data(ROOT / "README.md", ".")
    add_data(ROOT / "LICENSE.txt", ".")

    print("▶ PyInstaller läuft...")
    result = _run(cmd)

    if result.returncode != 0:
        print("❌ PyInstaller Build fehlgeschlagen")
        if result.stdout.strip():
            print("\n--- stdout ---")
            print(result.stdout)
        if result.stderr.strip():
            print("\n--- stderr ---")
            print(result.stderr)
        return False

    print("✅ EXE Build erfolgreich")
    return True


def create_distribution_package() -> None:
    """Create installer-friendly folder dist/Portfolio-Manager."""
    source_dir = TMP_DIST_DIR / APP_NAME
    target_dir = DIST_DIR / PACKAGE_DIR_NAME

    if not source_dir.exists():
        raise FileNotFoundError(f"Build-Ausgabe nicht gefunden: {source_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source_dir.iterdir():
        destination = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)

    print(f"✅ Distribution-Paket erstellt: {target_dir}")


def create_zip_archive() -> Path:
    """Create portable ZIP from dist/Portfolio-Manager."""
    source_dir = DIST_DIR / PACKAGE_DIR_NAME
    if not source_dir.exists():
        raise FileNotFoundError(f"Paketordner fehlt: {source_dir}")

    zip_base = DIST_DIR / f"{PACKAGE_DIR_NAME}-v{APP_VERSION}-Windows"
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=source_dir))
    print(f"✅ ZIP erstellt: {zip_path}")
    return zip_path
