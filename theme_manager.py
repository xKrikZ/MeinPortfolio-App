"""Theme manager for light/dark mode"""

import tkinter as tk
from tkinter import ttk
from typing import Callable
from enum import Enum
from pathlib import Path
import json


class ThemeMode(Enum):
    """Theme modes"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ColorPalette:
    """Color palette for a theme"""

    def __init__(
        self,
        bg_main: str,
        bg_secondary: str,
        bg_card: str,
        fg_main: str,
        fg_secondary: str,
        accent: str,
        success: str,
        error: str,
        warning: str,
        border: str,
        hover: str,
    ):
        self.bg_main = bg_main
        self.bg_secondary = bg_secondary
        self.bg_card = bg_card
        self.fg_main = fg_main
        self.fg_secondary = fg_secondary
        self.accent = accent
        self.success = success
        self.error = error
        self.warning = warning
        self.border = border
        self.hover = hover


LIGHT_PALETTE = ColorPalette(
    bg_main="#f0f0f0",
    bg_secondary="#e0e0e0",
    bg_card="#ffffff",
    fg_main="#2c3e50",
    fg_secondary="#7f8c8d",
    accent="#1976D2",
    success="#4CAF50",
    error="#F44336",
    warning="#FF9800",
    border="#cccccc",
    hover="#e3f2fd",
)

DARK_PALETTE = ColorPalette(
    bg_main="#1e1e1e",
    bg_secondary="#2d2d2d",
    bg_card="#252525",
    fg_main="#e0e0e0",
    fg_secondary="#b0b0b0",
    accent="#42A5F5",
    success="#66BB6A",
    error="#EF5350",
    warning="#FFA726",
    border="#404040",
    hover="#2d3e50",
)


class ThemeManager:
    """Manages application theme (light/dark mode)"""

    def __init__(self, config_file: Path, default_mode: ThemeMode = ThemeMode.LIGHT):
        self._config_file = config_file
        self._current_mode = default_mode
        self._palette = LIGHT_PALETTE
        self._theme_change_callbacks: list[Callable] = []
        self._load_preference()
        self._update_palette()

    def _load_preference(self):
        """Load theme preference from config file"""
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    mode_str = config.get("theme", self._current_mode.value)
                    self._current_mode = ThemeMode(mode_str)
        except Exception:
            pass

    def _save_preference(self):
        """Save theme preference to config file"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {}
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)

            config["theme"] = self._current_mode.value

            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Could not save theme preference: {e}")

    def _update_palette(self):
        """Update color palette based on current mode"""
        effective_mode = self.get_effective_mode()
        if effective_mode == ThemeMode.DARK:
            self._palette = DARK_PALETTE
        else:
            self._palette = LIGHT_PALETTE

    def get_current_mode(self) -> ThemeMode:
        return self._current_mode

    def get_effective_mode(self) -> ThemeMode:
        """Get effective mode (resolves AUTO to LIGHT/DARK)."""
        if self._current_mode != ThemeMode.AUTO:
            return self._current_mode
        return self._detect_system_theme()

    def get_palette(self) -> ColorPalette:
        return self._palette

    def set_mode(self, mode: ThemeMode):
        if mode != self._current_mode:
            self._current_mode = mode
            self._update_palette()
            self._save_preference()
            self._notify_theme_change()

    def toggle_mode(self):
        current_effective = self.get_effective_mode()
        if current_effective == ThemeMode.LIGHT:
            self.set_mode(ThemeMode.DARK)
        else:
            self.set_mode(ThemeMode.LIGHT)

    def register_theme_change_callback(self, callback: Callable):
        self._theme_change_callbacks.append(callback)

    def _notify_theme_change(self):
        for callback in self._theme_change_callbacks:
            try:
                callback(self._palette)
            except Exception as e:
                print(f"Error in theme change callback: {e}")

    def apply_to_root(self, root: tk.Tk):
        root.configure(bg=self._palette.bg_main)

    def create_ttk_styles(self, style: ttk.Style) -> None:
        p = self._palette

        style.configure("Main.TFrame", background=p.bg_main)
        style.configure("Card.TFrame", background=p.bg_card, relief="raised", borderwidth=1)

        style.configure("Card.TLabelframe", background=p.bg_card, relief="solid", borderwidth=1)
        style.configure(
            "Card.TLabelframe.Label",
            background=p.bg_card,
            foreground=p.accent,
            font=("Segoe UI", 10, "bold"),
        )

        style.configure("Header.TLabel", background=p.bg_card, foreground=p.fg_main, font=("Segoe UI", 9), anchor="w")
        style.configure("Count.TLabel", background=p.bg_card, foreground=p.fg_secondary, font=("Segoe UI", 10))
        style.configure("Summary.TLabel", background=p.bg_card, foreground=p.accent, font=("Segoe UI", 11, "bold"))

        style.configure("Action.TButton", font=("Segoe UI", 9), padding=(15, 8), anchor="w")
        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(15, 8), anchor="w")
        style.configure("Chart.TButton", font=("Segoe UI", 9), padding=(15, 8), anchor="w")
        style.configure("Danger.TButton", font=("Segoe UI", 9), padding=(15, 8), anchor="w")

        style.configure("TEntry", fieldbackground=p.bg_card, foreground=p.fg_main, borderwidth=1)
        style.configure("TCombobox", fieldbackground=p.bg_card, foreground=p.fg_main, borderwidth=1)

        style.configure("TNotebook", background=p.bg_main, borderwidth=0, tabmargins=[2, 5, 2, 0])
        style.configure(
            "TNotebook.Tab",
            background=p.bg_secondary,
            foreground=p.fg_secondary,
            padding=[35, 15],
            font=("Segoe UI", 11, "bold"),
            borderwidth=1,
            relief="raised",
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", p.bg_card), ("active", p.hover)],
            foreground=[("selected", p.accent), ("active", p.accent)],
            padding=[("selected", [40, 18, 40, 18])],
            expand=[("selected", [2, 2, 2, 0])],
        )

        style.configure(
            "Custom.Treeview",
            background=p.bg_card,
            foreground=p.fg_main,
            fieldbackground=p.bg_card,
            rowheight=35,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=p.accent,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            borderwidth=1,
            padding=(10, 8),
        )
        style.map("Custom.Treeview", background=[("selected", p.accent)], foreground=[("selected", "white")])
        style.map("Custom.Treeview.Heading", background=[("active", p.accent)], foreground=[("active", "white")])

    def apply_to_treeview(self, tree: ttk.Treeview):
        p = self._palette
        if self.get_effective_mode() == ThemeMode.DARK:
            tree.tag_configure("oddrow", background="#2a2a2a")
            tree.tag_configure("evenrow", background="#252525")
        else:
            tree.tag_configure("oddrow", background="#f8f9fa")
            tree.tag_configure("evenrow", background="#ffffff")

        tree.tag_configure("positive", foreground=p.success)
        tree.tag_configure("negative", foreground=p.error)
        tree.tag_configure("profit", foreground=p.success)
        tree.tag_configure("loss", foreground=p.error)
        tree.tag_configure("hover", background=p.hover)

    @staticmethod
    def _detect_system_theme() -> ThemeMode:
        """Detect Windows app theme preference (best effort)."""
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return ThemeMode.LIGHT if int(value) == 1 else ThemeMode.DARK
        except Exception:
            return ThemeMode.LIGHT
