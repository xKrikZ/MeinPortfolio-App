import sys
import traceback
import ctypes
from tkinter import messagebox

from config import AppConfig
from database import PriceRepository
from service import PriceService
from portfolio_service import PortfolioService
from dividend_service import DividendService
from alert_service import AlertService
from gui import PriceGui
from backup_service import BackupService
from exceptions import PortfolioError, DatabaseError, ConfigurationError, BackupError


def main() -> None:
    """Application entry point with comprehensive error handling"""
    try:
        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "Jannik.Aktienportfolio.Preisverwaltung"
                )
            except Exception:
                pass

        # Load configuration
        config = AppConfig.from_env()
        
        # Initialize repository
        repository = PriceRepository(config.db_path)
        
        try:
            repository.connect()
        except DatabaseError as e:
            messagebox.showerror(
                "❌ Datenbankfehler",
                e.get_full_message() + "\n\nDie Anwendung wird beendet."
            )
            sys.exit(1)

        try:
            print("🔍 Prüfe Datenbank-Integrität...")
            repository.check_integrity()
            print("✅ Datenbank-Integrität OK")

            violations = repository.check_foreign_keys()
            if violations:
                print("⚠️ Foreign Key Violations gefunden:")
                for violation in violations:
                    print(f"   - {violation}")

                messagebox.showwarning(
                    "⚠️ Datenbank-Inkonsistenzen",
                    f"Es wurden {len(violations)} Inkonsistenzen gefunden.\n\n"
                    "Details wurden in die Konsole ausgegeben.\n\n"
                    "Empfehlung: Backup wiederherstellen."
                )
        except DatabaseError as e:
            messagebox.showerror(
                "❌ Datenbank-Fehler",
                e.get_full_message()
            )
            sys.exit(1)
        
        try:
            # Initialize services
            price_service = PriceService(repository, config)
            portfolio_service = PortfolioService(repository, config)
            dividend_service = DividendService(repository)
            alert_service = AlertService(repository)
            backup_service = BackupService(
                db_path=config.db_path,
                backup_dir=config.backup_dir
            )
            backup_service.retention_days = config.backup_retention_days

            if config.enable_auto_backup:
                try:
                    backup_path = backup_service.create_daily_backup_if_needed()
                    if backup_path:
                        print(f"✅ Tägliches Backup erstellt: {backup_path.name}")

                    deleted = backup_service.cleanup_old_backups()
                    if deleted > 0:
                        print(f"🗑️ {deleted} alte Backups gelöscht")
                except BackupError as e:
                    print(f"⚠️ Backup-Warnung: {e.get_full_message()}")
            
            # Start GUI with both services
            app = PriceGui(config, price_service, portfolio_service)
            app.set_backup_service(backup_service)
            app.set_dividend_service(dividend_service)
            app.set_alert_service(alert_service)
            app.mainloop()
            
        except Exception as e:
            # Log the full error
            traceback.print_exc()
            
            # Show user-friendly error
            error = PortfolioError(
                "Unerwarteter Fehler beim Starten der Anwendung",
                str(e)
            )
            messagebox.showerror("❌ Fehler", error.get_full_message())
            
        finally:
            # Cleanup
            try:
                repository.close()
            except Exception:
                pass
    
    except ConfigurationError as e:
        messagebox.showerror(
            "❌ Konfigurationsfehler",
            e.get_full_message() + "\n\nDie Anwendung wird beendet."
        )
        sys.exit(1)
    
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror(
            "❌ Kritischer Fehler",
            f"Ein unerwarteter Fehler ist aufgetreten:\n\n{str(e)}\n\nDie Anwendung wird beendet."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()