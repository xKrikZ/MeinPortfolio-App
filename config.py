from pathlib import Path
from dataclasses import dataclass

@dataclass
class AppConfig:
    """Application configuration"""
    db_path: Path
    window_title: str = "Janniks Aktienportfolio - Preisverwaltung"
    window_width: int = 1280
    window_height: int = 720
    default_currency: str = "EUR"
    date_format: str = "%Y-%m-%d"
    backup_dir: Path = Path(__file__).parent / "backups"
    backup_retention_days: int = 30
    enable_auto_backup: bool = True
    theme_config_file: Path = Path(__file__).parent / "config" / "theme.json"
    default_theme: str = "light"
    
    # Window settings
    start_maximized: bool = True
    fullscreen: bool = False
    resizable: bool = True
    
    # Icon paths
    assets_dir: Path = Path(__file__).parent / "assets"
    icons_dir: Path = assets_dir / "icons"
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment or defaults"""
        db_path = Path(__file__).parent / "portfolio.db"
        backup_dir = Path(__file__).parent / "backups"
        theme_config_file = Path(__file__).parent / "config" / "theme.json"
        return cls(db_path=db_path, backup_dir=backup_dir, theme_config_file=theme_config_file)
    
    def get_icon_path(self, icon_name: str) -> Path:
        """Get full path to icon file"""
        return self.icons_dir / icon_name


class Constants:
    """Application constants"""
    SOURCE_MANUAL_GUI = "manual_gui"
    PADDING = 10
    DATE_LENGTH = 10
    FLOAT_PRECISION = 6
    CSV_DELIMITER = ";"
    CSV_ENCODING = "utf-8-sig"
    
    # Icon names - Price Management
    ICON_APP = "app_icon.ico"
    ICON_SAVE = "save.png"
    ICON_ADD = "add.png"
    ICON_APPLY = "apply.png"
    ICON_EXPORT = "export.png"
    ICON_FILTER = "filter.png"
    ICON_REFRESH = "refresh.png"
    ICON_RESET = "reset.png"
    ICON_CHART = "chart.png"
    
    # Icon names - Portfolio Management (NEW)
    ICON_PORTFOLIO = "portfolio.png"
    ICON_BUY = "buy.png"
    ICON_SELL = "sell.png"
    ICON_TRANSACTION = "transaction.png"
    ICON_PROFIT = "profit.png"
    ICON_LOSS = "loss.png"
    ICON_DETAILS = "details.png"