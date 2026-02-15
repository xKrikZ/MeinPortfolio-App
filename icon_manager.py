import tkinter as tk
from pathlib import Path
from typing import Optional, Dict, Tuple
from PIL import Image, ImageTk

from config import AppConfig, Constants


class IconManager:
    """Manages application icons and images"""
    
    # Standard sizes for different use cases - VERGRÖSSERT
    SIZE_BUTTON = (20, 20)      # For toolbar/action buttons
    SIZE_SMALL = (16, 16)       # For small buttons/indicators
    SIZE_MEDIUM = (28, 28)      # For larger buttons
    SIZE_LARGE = (48, 48)       # For headers/special buttons
    ICON_VERTICAL_OFFSET = 1    # Move icon slightly down for visual centering
    
    def __init__(self, config: AppConfig):
        self._config = config
        self._cache: Dict[str, ImageTk.PhotoImage] = {}
        self._ensure_icons_dir()
    
    def _ensure_icons_dir(self) -> None:
        """Create icons directory if it doesn't exist"""
        self._config.icons_dir.mkdir(parents=True, exist_ok=True)
    
    def load_icon(
        self, 
        icon_name: str, 
        size: Tuple[int, int] = None
    ) -> Optional[ImageTk.PhotoImage]:
        """
        Load and cache an icon with high-quality scaling
        
        Args:
            icon_name: Name of the icon file
            size: Tuple of (width, height) for resizing. 
                  Default: SIZE_BUTTON (20x20)
            
        Returns:
            PhotoImage or None if file not found
        """
        if size is None:
            size = self.SIZE_BUTTON
        
        cache_key = f"{icon_name}_{size[0]}x{size[1]}"
        
        # Return cached version if available
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        icon_path = self._config.get_icon_path(icon_name)
        
        if not icon_path.exists():
            print(f"⚠️  Icon nicht gefunden: {icon_path}")
            return None
        
        try:
            # Load and resize image with high quality
            img = Image.open(icon_path)
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Remove transparent outer padding for better alignment (without distorting aspect ratio)
            alpha = img.split()[3]
            bbox = alpha.getbbox()
            if bbox:
                img = img.crop(bbox)

            # Fit proportionally into target box and center it (never stretch)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            calibrated = Image.new('RGBA', size, (0, 0, 0, 0))
            x_raw = (size[0] - img.width) // 2
            y_raw = (size[1] - img.height) // 2 + self.ICON_VERTICAL_OFFSET

            # Clamp to canvas bounds to prevent clipping/cropping artifacts
            x = min(max(0, x_raw), max(0, size[0] - img.width))
            y = min(max(0, y_raw), max(0, size[1] - img.height))
            calibrated.paste(img, (x, y), img)

            img = calibrated
            photo = ImageTk.PhotoImage(img)
            
            # Cache it
            self._cache[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"❌ Error loading icon {icon_name}: {e}")
            return None
    
    def load_button_icon(self, icon_name: str) -> Optional[ImageTk.PhotoImage]:
        """Load icon at standard button size (20x20)"""
        return self.load_icon(icon_name, self.SIZE_BUTTON)
    
    def load_small_icon(self, icon_name: str) -> Optional[ImageTk.PhotoImage]:
        """Load icon at small size (16x16)"""
        return self.load_icon(icon_name, self.SIZE_SMALL)
    
    def load_medium_icon(self, icon_name: str) -> Optional[ImageTk.PhotoImage]:
        """Load icon at medium size (28x28)"""
        return self.load_icon(icon_name, self.SIZE_MEDIUM)
    
    def load_large_icon(self, icon_name: str) -> Optional[ImageTk.PhotoImage]:
        """Load icon at large size (48x48)"""
        return self.load_icon(icon_name, self.SIZE_LARGE)
    
    def set_window_icon(self, window: tk.Tk) -> None:
        """Set the window icon"""
        icon_path = self._config.get_icon_path(Constants.ICON_APP)
        if icon_path.exists():
            try:
                window.iconbitmap(icon_path)
                try:
                    icon_img = Image.open(icon_path)
                    icon_photo = ImageTk.PhotoImage(icon_img)
                    window.iconphoto(True, icon_photo)
                    window._taskbar_icon_photo = icon_photo
                except Exception:
                    pass
                print(f"✅ Window icon loaded: {icon_path.name}")
            except Exception as e:
                print(f"⚠️  Could not set window icon: {e}")
        else:
            print(f"⚠️  Window icon not found: {icon_path}")
    
    @staticmethod
    def get_emoji_icon(emoji: str) -> str:
        """
        Return emoji as fallback icon
        
        Args:
            emoji: Emoji character
            
        Returns:
            Formatted string with emoji
        """
        return f"{emoji} "


class EmojiIcons:
    """Unicode emoji icons as fallback"""
    # General
    SAVE = "💾"
    EXPORT = "📊"
    FILTER = "🔍"
    REFRESH = "🔄"
    RESET = "↺"
    CHART = "📈"
    
    # Date & Time
    CALENDAR = "📅"
    
    # Money & Finance
    MONEY = "💰"
    DATABASE = "🗄️"
    
    # Portfolio
    PORTFOLIO = "💼"
    BUY = "🛒"
    SELL = "💸"
    PROFIT = "📈"
    LOSS = "📉"
    TRANSACTION = "💳"
    
    # Status
    CHECK = "✅"
    CROSS = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # Actions
    SETTINGS = "⚙️"
    DELETE = "🗑️"
    DETAILS = "📋"
    ADD = "➕"
    REMOVE = "➖"