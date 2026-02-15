from __future__ import annotations

import re
import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional

from exceptions import BackupError
from models import BackupInfo


class BackupService:
    """Service for creating, listing, restoring and cleaning database backups."""

    _DAILY_PATTERN = re.compile(r"^portfolio_backup_(\d{4}-\d{2}-\d{2})\.db$")
    _ACTION_PATTERN = re.compile(
        r"^portfolio_backup_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})_vor_([a-zA-Z0-9_\-]+)\.db$"
    )

    def __init__(self, db_path: Path, backup_dir: Path):
        """
        Args:
            db_path: Pfad zur Haupt-Datenbank (portfolio.db)
            backup_dir: Verzeichnis für Backups
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_days = 30
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, action_name: str = None) -> Path:
        """
        Erstellt Backup der Datenbank

        Args:
            action_name: Optional, Name der Aktion (z.B. "datenbank_leeren")

        Returns:
            Path zum erstellten Backup

        Raises:
            BackupError: Wenn Backup fehlschlägt
        """
        try:
            if not self.db_path.exists():
                raise BackupError(
                    "Datenbank nicht gefunden",
                    f"Die Datenbankdatei existiert nicht: {self.db_path}",
                )

            now = datetime.now()
            if action_name:
                safe_action = self._sanitize_action_name(action_name)
                file_name = f"portfolio_backup_{now.strftime('%Y-%m-%d_%H-%M-%S')}_vor_{safe_action}.db"
            else:
                file_name = f"portfolio_backup_{now.strftime('%Y-%m-%d')}.db"

            backup_path = self.backup_dir / file_name
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError(
                "Backup konnte nicht erstellt werden",
                str(exc),
            ) from exc

    def create_daily_backup_if_needed(self) -> Optional[Path]:
        """
        Erstellt tägliches Backup wenn noch keins für heute existiert

        Returns:
            Path zum Backup oder None wenn bereits existiert
        """
        today_name = f"portfolio_backup_{date.today().isoformat()}.db"
        existing = self.backup_dir / today_name
        if existing.exists():
            return None

        return self.create_backup()

    def cleanup_old_backups(self) -> int:
        """
        Löscht alte Backups (älter als 30 Tage, außer monatliche)

        Returns:
            Anzahl gelöschter Backups
        """
        backups = self.list_backups()
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted = 0

        for backup in backups:
            if backup.is_monthly:
                continue
            if backup.created_date < cutoff:
                try:
                    backup.file_path.unlink(missing_ok=True)
                    deleted += 1
                except Exception:
                    continue

        return deleted

    def list_backups(self) -> List[BackupInfo]:
        """
        Listet alle verfügbaren Backups

        Returns:
            Liste von BackupInfo Objekten (Dateiname, Größe, Datum)
        """
        backups: List[BackupInfo] = []

        if not self.backup_dir.exists():
            return backups

        for file_path in self.backup_dir.glob("portfolio_backup_*.db"):
            parsed = self._parse_backup_filename(file_path.name)
            if not parsed:
                continue

            created_date, action_name = parsed
            is_monthly = created_date.day == 1
            backups.append(
                BackupInfo(
                    file_path=file_path,
                    file_name=file_path.name,
                    size_bytes=file_path.stat().st_size,
                    created_date=created_date,
                    is_monthly=is_monthly,
                    action_name=action_name,
                )
            )

        backups.sort(key=lambda info: info.created_date, reverse=True)
        return backups

    def restore_backup(self, backup_path: Path) -> None:
        """
        Stellt Backup wieder her

        Args:
            backup_path: Pfad zum Backup

        Raises:
            BackupError: Wenn Restore fehlschlägt
        """
        backup_path = Path(backup_path)

        try:
            if not backup_path.exists():
                raise BackupError("Backup nicht gefunden", f"Datei existiert nicht: {backup_path}")

            if not self.db_path.parent.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

            temp_target = self.db_path.with_suffix(".db.restore_tmp")
            shutil.copy2(backup_path, temp_target)
            temp_target.replace(self.db_path)
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError("Backup konnte nicht wiederhergestellt werden", str(exc)) from exc

    @staticmethod
    def _sanitize_action_name(action_name: str) -> str:
        safe = action_name.strip().lower().replace(" ", "_")
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "", safe)
        return safe or "aktion"

    def _parse_backup_filename(self, file_name: str) -> Optional[tuple[datetime, Optional[str]]]:
        daily_match = self._DAILY_PATTERN.match(file_name)
        if daily_match:
            date_str = daily_match.group(1)
            return datetime.strptime(date_str, "%Y-%m-%d"), None

        action_match = self._ACTION_PATTERN.match(file_name)
        if action_match:
            date_str, time_str, action_name = action_match.groups()
            date_time_str = f"{date_str} {time_str}"
            created = datetime.strptime(date_time_str, "%Y-%m-%d %H-%M-%S")
            return created, action_name

        return None
