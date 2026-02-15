import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
from typing import List, Optional
from pathlib import Path
from decimal import Decimal, InvalidOperation
import sqlite3
from tkcalendar import DateEntry

from models import (
    Asset, PriceView, PriceFilter, ChartConfig, ChartType,
    TransactionType, PortfolioSummary, Transaction, DividendType, DividendSummary,
    AlertType, TriggeredAlert
)
from service import PriceService
from portfolio_service import PortfolioService
from dividend_service import DividendService
from alert_service import AlertService
from chart_service import ChartService, ChartWindow
from backup_service import BackupService
from dialogs import CountdownDialog, ConfirmationDialog
from validators import InputValidator
from theme_manager import ThemeManager, ThemeMode, ColorPalette
from exceptions import (
    ValidationError, ExportError, ChartError, 
    DataNotFoundError, DatabaseError, PortfolioError, BackupError
)
from config import AppConfig, Constants
from icon_manager import IconManager, EmojiIcons


class PriceGui(tk.Tk):
    """Main GUI for portfolio price management"""
    
    def __init__(self, config: AppConfig, price_service: PriceService, portfolio_service: PortfolioService):
        super().__init__()
        
        self._config = config
        self._price_service = price_service
        self._portfolio_service = portfolio_service
        self._chart_service = ChartService()
        self._icon_manager = IconManager(config)
        self._assets: List[Asset] = []
        self._currencies: List[str] = []
        self._current_prices: List[PriceView] = []
        self._current_portfolio: List[PortfolioSummary] = []
        self._current_dividend_summary: List[DividendSummary] = []
        self._backup_service: Optional[BackupService] = None
        self._dividend_service: Optional[DividendService] = None
        self._alert_service: Optional[AlertService] = None
        self._is_fullscreen = config.fullscreen
        if config.default_theme == "dark":
            default_mode = ThemeMode.DARK
        elif config.default_theme == "auto":
            default_mode = ThemeMode.AUTO
        else:
            default_mode = ThemeMode.LIGHT
        self._theme_manager = ThemeManager(config.theme_config_file, default_mode=default_mode)
        self._theme_manager.register_theme_change_callback(self._on_theme_changed)
        
        self._setup_window()
        self._setup_styles()
        self._load_data()
        self._build_ui()
        self._build_menu()
        self._setup_keybindings()
        self._refresh_prices()
        self._refresh_portfolio()
        self._apply_theme()

    def set_backup_service(self, backup_service: BackupService):
        """Set backup service for automatic backups before critical operations"""
        self._backup_service = backup_service

    def set_dividend_service(self, dividend_service: DividendService):
        """Set dividend service for dividends tab operations"""
        self._dividend_service = dividend_service
        self._refresh_dividends()

    def set_alert_service(self, alert_service: AlertService):
        """Set alert service for alert tab operations"""
        self._alert_service = alert_service
        self._alert_service.set_notification_callback(self._show_desktop_notification)
        self._refresh_alerts()

    def _backup_before_critical_action(self, action_name: str) -> bool:
        if not self._config.enable_auto_backup:
            return True

        if self._backup_service is None:
            return True

        try:
            backup_path = self._backup_service.create_backup(action_name)
            messagebox.showinfo(
                "🔒 Backup erstellt",
                f"Sicherheitsbackup wurde erstellt:\n{backup_path.name}"
            )
            return True
        except BackupError as e:
            result = messagebox.askyesno(
                "⚠️ Backup fehlgeschlagen",
                f"Backup konnte nicht erstellt werden!\n{e.message}\n\nTrotzdem fortfahren?"
            )
            return result
    
    def _setup_window(self) -> None:
        """Configure main window"""
        self.title("MeinPortfolio-App")
        self.configure(bg='#f0f0f0')
        self._icon_manager.set_window_icon(self)
        self.resizable(self._config.resizable, self._config.resizable)
        self.geometry(f"{self._config.window_width}x{self._config.window_height}")
        
        # Center window
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - self._config.window_width) // 2
        y = (screen_height - self._config.window_height) // 2
        self.geometry(f"{self._config.window_width}x{self._config.window_height}+{x}+{y}")
        
        if self._config.fullscreen:
            self.attributes('-fullscreen', True)
            self._is_fullscreen = True
        elif self._config.start_maximized:
            self.state('zoomed')

    def _setup_quantity_validation(self, entry_widget) -> None:
        """Add real-time validation to numeric entry fields."""

        def validate_input(new_value: str) -> bool:
            if new_value == "":
                return True

            if not all(c.isdigit() or c in ',.+ ' for c in new_value):
                return False

            try:
                clean = new_value.replace(',', '.').replace(' ', '')
                if clean and clean != '.':
                    float(clean)
            except ValueError:
                return False

            return True

        vcmd = (entry_widget.register(validate_input), '%P')
        entry_widget.config(validate='key', validatecommand=vcmd)
    
    # ==================== SORTABLE COLUMNS ====================
    
    def _make_sortable(self, tree, columns):
        """
        Setup sortable columns for a treeview
        
        Args:
            tree: The treeview widget
            columns: List of column identifiers
        """
        # Store sort direction for each column
        if not hasattr(self, '_sort_state'):
            self._sort_state = {}
        
        tree_id = str(id(tree))  # Unique ID for this tree
        self._sort_state[tree_id] = {col: False for col in columns}  # False = ascending
        
        # Bind click event to each column header
        for col in columns:
            tree.heading(col, command=lambda c=col, t=tree: self._sort_column(t, c))
    
    def _sort_column(self, tree, col):
        """
        Sort treeview by column
        
        Args:
            tree: The treeview widget
            col: Column to sort by
        """
        tree_id = str(id(tree))
        
        # Toggle sort direction
        ascending = self._sort_state[tree_id][col]
        self._sort_state[tree_id][col] = not ascending
        
        # Get all items
        items = [(tree.set(item, col), item) for item in tree.get_children('')]
        
        # Sort items
        try:
            # Try numeric sort first
            items_sorted = sorted(items, key=lambda x: self._parse_sort_value(x[0]), reverse=ascending)
        except:
            # Fall back to string sort
            items_sorted = sorted(items, key=lambda x: x[0].lower(), reverse=ascending)
        
        # Rearrange items in sorted positions
        for index, (val, item) in enumerate(items_sorted):
            tree.move(item, '', index)
        
        # Update column heading to show sort direction
        self._update_column_headers(tree, col, ascending)
    
    def _parse_sort_value(self, value):
        """
        Parse value for sorting (handle numbers, dates, percentages)
        
        Args:
            value: String value from cell
            
        Returns:
            Parsed value for comparison
        """
        if not value or value == '—' or value == '-':
            return float('-inf')  # Put empty/dash values at the end
        
        # Remove common formatting
        clean_value = value.replace('.', '').replace(',', '.').replace('€', '').replace('%', '').replace('+', '').strip()
        
        try:
            # Try to convert to float
            return float(clean_value)
        except:
            # Return as string for text sorting
            return value.lower()
    
    def _update_column_headers(self, tree, sorted_col, ascending):
        """
        Update column headers to show sort indicators
        
        Args:
            tree: The treeview widget
            sorted_col: Currently sorted column
            ascending: Sort direction
        """
        tree_id = str(id(tree))
        
        # Get column configuration based on tree type
        if tree == self.tree:
            # Price table columns
            column_names = {
                "symbol": "Symbol",
                "name": "Name",
                "close": "Kurs",
                "currency": "Währung",
                "change": "Änderung %",
                "date": "Datum",
            }
        elif tree == self.portfolio_tree:
            # Portfolio table columns
            column_names = {
                "symbol": "Symbol",
                "name": "Name",
                "quantity": "Menge",
                "avg_price": "Ø Kaufpreis",
                "current_price": "Aktueller Kurs",
                "value": "Wert",
                "profit_loss": "Gewinn/Verlust",
                "profit_percent": "G/V %",
            }
        elif hasattr(self, 'dividend_tree') and tree == self.dividend_tree:
            column_names = {
                "symbol": "Symbol",
                "name": "Name",
                "total_dividends": "Gesamt Netto",
                "dividend_count": "Anzahl",
                "average_dividend": "Ø Dividende",
                "current_holdings": "Bestand",
                "annual_yield": "Rendite %",
                "currency": "Währung",
            }
        elif hasattr(self, 'alerts_tree') and tree == self.alerts_tree:
            column_names = {
                "symbol": "Symbol",
                "name": "Name",
                "type": "Typ",
                "threshold": "Schwellwert",
                "status": "Status",
            }
        else:
            return
        
        # Update all column headings
        for col, base_name in column_names.items():
            if col == sorted_col:
                # Add arrow indicator
                arrow = "▼" if ascending else "▲"
                tree.heading(col, text=f"{base_name} {arrow}")
            else:
                # Remove arrow
                tree.heading(col, text=base_name)
    
    def _setup_styles(self) -> None:
        """Setup custom ttk styles"""
        style = ttk.Style()
        
        try:
            style.theme_use('clam')
        except:
            pass
        self._theme_manager.create_ttk_styles(style)
        
    def _setup_keybindings(self) -> None:
        """Setup keyboard shortcuts"""
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<F5>", lambda _: self._refresh_active_tab())
        self.bind("<Control-e>", lambda _: self._export_csv())
        self.bind("<Control-f>", lambda _: self._apply_filter())
        self.bind("<Control-r>", lambda _: self._reset_filter())
        self.bind("<Control-g>", lambda _: self._show_chart())
        self.bind("<Control-i>", lambda _: self._import_database())
        self.bind("<Control-t>", lambda _: self._toggle_theme())
        self.bind("<Delete>", lambda _: self._delete_selected_entry())
    
    def _toggle_fullscreen(self, event=None) -> None:
        """Toggle fullscreen mode"""
        self._is_fullscreen = not self._is_fullscreen
        self.attributes('-fullscreen', self._is_fullscreen)
    
    def _exit_fullscreen(self, event=None) -> None:
        """Exit fullscreen mode"""
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.attributes('-fullscreen', False)
    
    def _load_data(self) -> None:
        """Load initial data with error handling"""
        try:
            self._assets = self._price_service.get_active_assets()
            self._currencies = self._price_service.get_currencies()
        except DatabaseError as e:
            self._show_error("Datenbankfehler", e)
            self._assets = []
            self._currencies = []
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Unerwarteter Fehler beim Laden", str(e)))
            self._assets = []
            self._currencies = []
    
    def _build_ui(self) -> None:
        """Build user interface with tabs"""
        main_frame = ttk.Frame(self, style='Main.TFrame', padding=15)
        main_frame.pack(fill="both", expand=True)

        toolbar_frame = ttk.Frame(main_frame, style='Main.TFrame')
        toolbar_frame.pack(fill="x", pady=(0, 12), ipady=2)
        self._build_theme_toggle_button(toolbar_frame)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)
        
        # Tab 1: Kursverwaltung
        prices_tab = ttk.Frame(self.notebook, style='Main.TFrame')
        self.notebook.add(prices_tab, text="📊 Kursverwaltung")
        self._build_prices_tab(prices_tab)
        
        # Tab 2: Portfolio
        portfolio_tab = ttk.Frame(self.notebook, style='Main.TFrame')
        self.notebook.add(portfolio_tab, text="💼 Portfolio")
        self._build_portfolio_tab(portfolio_tab)

        # Tab 3: Dividenden
        dividends_tab = ttk.Frame(self.notebook, style='Main.TFrame')
        self.notebook.add(dividends_tab, text="💰 Dividenden")
        self._build_dividends_tab(dividends_tab)

        # Tab 4: Alarme
        alerts_tab = ttk.Frame(self.notebook, style='Main.TFrame')
        self.notebook.add(alerts_tab, text="🔔 Alarme")
        self._build_alerts_tab(alerts_tab)

    def _apply_theme(self):
        """Apply current theme to all widgets"""
        self._theme_manager.apply_to_root(self)
        self._setup_styles()

        for tree_attr in ["tree", "portfolio_tree", "dividend_tree", "alerts_tree"]:
            if hasattr(self, tree_attr):
                self._theme_manager.apply_to_treeview(getattr(self, tree_attr))

        palette = self._theme_manager.get_palette()
        for widget in self._get_all_text_widgets():
            widget.configure(bg=palette.bg_card, fg=palette.fg_main, insertbackground=palette.fg_main)

        if hasattr(self, 'btn_theme_toggle'):
            icon = "🌙" if self._theme_manager.get_effective_mode() == ThemeMode.LIGHT else "☀️"
            self.btn_theme_toggle.config(text=icon)

    def _get_all_text_widgets(self) -> list:
        """Get all Text widgets recursively"""
        text_widgets = []

        def find_text_widgets(parent):
            for child in parent.winfo_children():
                if isinstance(child, tk.Text):
                    text_widgets.append(child)
                find_text_widgets(child)

        find_text_widgets(self)
        return text_widgets

    def _on_theme_changed(self, palette: ColorPalette):
        """Callback when theme changes"""
        self._apply_theme()
        self.update_idletasks()

    def _toggle_theme(self):
        """Toggle between light and dark mode"""
        self._theme_manager.toggle_mode()

    def _build_menu(self):
        """Build menu bar with theme toggle"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="Aktualisieren", command=self._refresh_active_tab, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self._on_exit_app)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Bearbeiten", menu=edit_menu)
        edit_menu.add_command(label="Datenbank importieren…", command=self._import_database, accelerator="Ctrl+I")

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ansicht", menu=view_menu)

        view_menu.add_command(label="Dunkler Modus", command=lambda: self._theme_manager.set_mode(ThemeMode.DARK))
        view_menu.add_command(label="Heller Modus", command=lambda: self._theme_manager.set_mode(ThemeMode.LIGHT))
        view_menu.add_command(label="System (Auto)", command=lambda: self._theme_manager.set_mode(ThemeMode.AUTO))
        view_menu.add_separator()
        view_menu.add_command(label="Wechseln", command=self._toggle_theme, accelerator="Ctrl+T")

        menubar.add_command(label="Impressum", command=self._show_impressum)

    def _build_theme_toggle_button(self, parent: ttk.Frame):
        """Add theme toggle button to toolbar"""
        current_mode = self._theme_manager.get_effective_mode()
        icon = "🌙" if current_mode == ThemeMode.LIGHT else "☀️"

        self.btn_theme_toggle = ttk.Button(parent, text=icon, command=self._toggle_theme, width=3)
        self.btn_theme_toggle.pack(side="right", padx=5)

    def _refresh_active_tab(self) -> None:
        """Refresh data for currently selected tab."""
        try:
            if not hasattr(self, 'notebook'):
                self._refresh_prices()
                self._refresh_portfolio()
                self._refresh_dividends()
                self._refresh_alerts()
                return

            tab_index = self.notebook.index(self.notebook.select())
            if tab_index == 0:
                self._refresh_prices()
            elif tab_index == 1:
                self._refresh_portfolio()
            elif tab_index == 2:
                self._refresh_dividends()
            elif tab_index == 3:
                self._refresh_alerts()
            else:
                self._refresh_prices()
                self._refresh_portfolio()
                self._refresh_dividends()
                self._refresh_alerts()
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Aktualisieren fehlgeschlagen", str(e)))

    def _on_exit_app(self) -> None:
        """Confirm and close application."""
        should_exit = messagebox.askyesno("Beenden", "Anwendung wirklich beenden?")
        if should_exit:
            self.destroy()

    def _show_impressum(self) -> None:
        """Show imprint/about dialog with author and version."""
        messagebox.showinfo(
            "Impressum",
            "MeinPortfolio-App\n\n"
            "Autor: Jannik Baumgart\n"
            "Version: 0.001v"
        )

    def _import_database(self) -> None:
        """Import an existing SQLite database and switch to it live."""
        source_file = filedialog.askopenfilename(
            title="Alte Datenbank importieren",
            filetypes=[("SQLite Datenbank", "*.db *.sqlite *.sqlite3"), ("Alle Dateien", "*.*")]
        )
        if not source_file:
            return

        source_path = Path(source_file)
        target_path = self._config.db_path

        if source_path.resolve() == target_path.resolve():
            messagebox.showinfo("Hinweis", "Die ausgewählte Datei ist bereits die aktive Datenbank.")
            return

        should_import = messagebox.askyesno(
            "Datenbank importieren",
            "Die aktuelle Datenbank wird durch die ausgewählte Datei ersetzt.\n\n"
            "Vorher wird automatisch ein Backup erstellt.\n\n"
            "Fortfahren?"
        )
        if not should_import:
            return

        try:
            self._validate_import_database(source_path)

            backup_name = None
            if self._backup_service is not None:
                try:
                    backup_path = self._backup_service.create_backup("vor_db_import")
                    backup_name = backup_path.name
                except BackupError as e:
                    proceed = messagebox.askyesno(
                        "⚠️ Backup fehlgeschlagen",
                        f"Backup konnte nicht erstellt werden:\n{e.message}\n\nTrotzdem importieren?"
                    )
                    if not proceed:
                        return

            repository = getattr(self._price_service, "_repository", None)
            if repository is not None:
                repository.close()

            if self._backup_service is not None:
                self._backup_service.restore_backup(source_path)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                temp_target = target_path.with_suffix(".db.import_tmp")
                temp_target.write_bytes(source_path.read_bytes())
                temp_target.replace(target_path)

            if repository is not None:
                repository.connect()

            self._load_data()
            self._sync_asset_combobox_values()
            self._refresh_prices()
            self._refresh_portfolio()
            self._refresh_dividends()
            self._refresh_alerts()

            backup_msg = f"\n\nBackup: {backup_name}" if backup_name else ""
            messagebox.showinfo(
                "✅ Import erfolgreich",
                f"Datenbank wurde erfolgreich importiert und live aktiviert.{backup_msg}"
            )
        except PortfolioError as e:
            self._show_error("Import fehlgeschlagen", e)
        except Exception as e:
            self._show_error("Import fehlgeschlagen", PortfolioError("Unerwarteter Import-Fehler", str(e)))

    def _validate_import_database(self, db_path: Path) -> None:
        """Validate that selected file is a usable portfolio database."""
        if not db_path.exists():
            raise PortfolioError("Datei nicht gefunden", f"Die Datei existiert nicht:\n{db_path}")

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            integrity = cur.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise PortfolioError(
                    "Ungültige Datenbank",
                    "Integritätsprüfung fehlgeschlagen. Datei scheint beschädigt zu sein."
                )

            rows = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in rows}

            required_tables = {"asset", "price"}
            missing = sorted(required_tables - table_names)
            if missing:
                raise PortfolioError(
                    "Ungültige Datenbankstruktur",
                    f"Erforderliche Tabellen fehlen: {', '.join(missing)}"
                )
        except sqlite3.Error as e:
            raise PortfolioError("Ungültige SQLite-Datei", str(e))
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def _sync_asset_combobox_values(self) -> None:
        """Refresh combobox values after database import/switch."""
        asset_values = [asset.display_name() for asset in self._assets]

        if hasattr(self, 'cmb_asset'):
            self.cmb_asset["values"] = asset_values
            if asset_values:
                self.cmb_asset.current(0)

        if hasattr(self, 'cmb_dividend_asset'):
            self.cmb_dividend_asset["values"] = asset_values
            if asset_values:
                self.cmb_dividend_asset.current(0)

        if hasattr(self, 'cmb_filter_asset'):
            filter_values = ["Alle"] + asset_values
            self.cmb_filter_asset["values"] = filter_values
            self.cmb_filter_asset.current(0)
    
    # ==================== PRICES TAB ====================
    
    def _build_prices_tab(self, parent: ttk.Frame) -> None:
        """Build prices management tab"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)
        
        self._build_input_section(parent)
        self._build_filter_section(parent)
        self._build_table_section(parent)
        
        # Setup context menu
        self._setup_price_context_menu()

    #Preiseingabe, Filter, Tabelle und Kontextmenü für Kursverwaltung
    def _setup_price_context_menu(self) -> None:
        """Setup right-click context menu for price treeview"""
        self.price_context_menu = tk.Menu(self, tearoff=0)
        self.price_context_menu.add_command(
            label="Eintrag löschen",  # OHNE Emoji
            command=self._delete_selected_entry,
            font=('Segoe UI', 10)  # Größere Schrift
        )
    
    def _build_input_section(self, parent: ttk.Frame) -> None:
        """Build input form section"""
        input_frame = ttk.LabelFrame(
            parent,
            text="Neue Kurseingabe",
            style='Card.TLabelframe',
            padding=15
        )
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        inner_frame = ttk.Frame(input_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)
        inner_frame.grid_columnconfigure(1, weight=1)
        
        # Labels row
        ttk.Label(inner_frame, text=f"{EmojiIcons.CALENDAR} Datum:", style='Header.TLabel').grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text=f"{EmojiIcons.CHART} Asset:", style='Header.TLabel').grid(
            row=0, column=1, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text=f"{EmojiIcons.MONEY} Kurs:", style='Header.TLabel').grid(
            row=0, column=2, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Währung:", style='Header.TLabel').grid(
            row=0, column=3, sticky="w", padx=(0, 10), pady=(0, 5))
        
        # Input fields row
        self.date_entry = DateEntry(
            inner_frame, width=14, background='#1976D2',
            foreground='white', borderwidth=1,
            date_pattern='yyyy-mm-dd', locale='de_DE',
            font=('Segoe UI', 9))
        self.date_entry.set_date(date.today())
        self.date_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        self.var_asset = tk.StringVar()
        self.cmb_asset = ttk.Combobox(
            inner_frame, textvariable=self.var_asset,
            state="readonly", font=('Segoe UI', 9), height=10)
        self.cmb_asset["values"] = [asset.display_name() for asset in self._assets]
        if self._assets:
            self.cmb_asset.current(0)
        self.cmb_asset.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        
        self.var_close = tk.StringVar()
        self.ent_close = ttk.Entry(
            inner_frame, textvariable=self.var_close,
            width=18, font=('Segoe UI', 9))
        self.ent_close.grid(row=1, column=2, sticky="ew", padx=(0, 10))
        self._setup_quantity_validation(self.ent_close)
        self.ent_close.bind("<Return>", lambda _: self._on_save())
        
        self.var_cur = tk.StringVar(value=self._config.default_currency)
        self.ent_cur = ttk.Entry(
            inner_frame, textvariable=self.var_cur,
            width=10, font=('Segoe UI', 9))
        self.ent_cur.grid(row=1, column=3, sticky="ew", padx=(0, 10))
        
        # Save button
        save_icon = self._icon_manager.load_button_icon(Constants.ICON_SAVE)
        btn_text = f"{EmojiIcons.SAVE} Speichern" if not save_icon else "Speichern"
        self.btn_save = ttk.Button(
            inner_frame, text=btn_text,
            image=save_icon if save_icon else None,
            compound="left" if save_icon else "none",
            style='Primary.TButton', command=self._on_save)
        if save_icon:
            self.btn_save.image = save_icon
        self.btn_save.grid(row=1, column=4, sticky="w")
    
    def _build_filter_section(self, parent: ttk.Frame) -> None:
        """Build filter section"""
        filter_frame = ttk.LabelFrame(
            parent,
            text="Filteroptionen",
            style='Card.TLabelframe',
            padding=15
        )
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        inner_frame = ttk.Frame(filter_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)
        inner_frame.grid_columnconfigure(2, weight=1)
        
        # Labels row
        ttk.Label(inner_frame, text="Von Datum:", style='Header.TLabel').grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Bis Datum:", style='Header.TLabel').grid(
            row=0, column=1, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Asset:", style='Header.TLabel').grid(
            row=0, column=2, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Währung:", style='Header.TLabel').grid(
            row=0, column=3, sticky="w", padx=(0, 10), pady=(0, 5))
        
        # Input fields row
        self.filter_date_from = DateEntry(
            inner_frame, width=14, background='#1976D2',
            foreground='white', borderwidth=1,
            date_pattern='yyyy-mm-dd', locale='de_DE',
            font=('Segoe UI', 9))
        self.filter_date_from.set_date(date.today())
        self.filter_date_from.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        self.filter_date_to = DateEntry(
            inner_frame, width=14, background='#1976D2',
            foreground='white', borderwidth=1,
            date_pattern='yyyy-mm-dd', locale='de_DE',
            font=('Segoe UI', 9))
        self.filter_date_to.set_date(date.today())
        self.filter_date_to.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        
        self.var_filter_asset = tk.StringVar()
        asset_values = ["Alle"] + [asset.display_name() for asset in self._assets]
        self.cmb_filter_asset = ttk.Combobox(
            inner_frame, textvariable=self.var_filter_asset,
            state="readonly", font=('Segoe UI', 9), height=10)
        self.cmb_filter_asset["values"] = asset_values
        self.cmb_filter_asset.current(0)
        self.cmb_filter_asset.grid(row=1, column=2, sticky="ew", padx=(0, 10))
        
        self.var_filter_currency = tk.StringVar()
        currency_values = ["Alle"] + self._currencies
        self.cmb_filter_currency = ttk.Combobox(
            inner_frame, textvariable=self.var_filter_currency,
            width=12, state="readonly", font=('Segoe UI', 9), height=10)
        self.cmb_filter_currency["values"] = currency_values
        self.cmb_filter_currency.current(0)
        self.cmb_filter_currency.grid(row=1, column=3, sticky="ew", padx=(0, 10))
        
        # Buttons
        apply_icon = self._icon_manager.load_button_icon(Constants.ICON_APPLY)
        btn_filter_text = f"{EmojiIcons.CHECK} Anwenden" if not apply_icon else "Anwenden"
        self.btn_apply_filter = ttk.Button(
            inner_frame, text=btn_filter_text,
            image=apply_icon if apply_icon else None,
            compound="left" if apply_icon else "none",
            style='Action.TButton', command=self._apply_filter)
        if apply_icon:
            self.btn_apply_filter.image = apply_icon
        self.btn_apply_filter.grid(row=1, column=4, sticky="w", padx=(0, 5))
        
        reset_icon = self._icon_manager.load_button_icon(Constants.ICON_RESET)
        btn_reset_text = f"{EmojiIcons.RESET} Zurücksetzen" if not reset_icon else "Zurücksetzen"
        self.btn_reset_filter = ttk.Button(
            inner_frame, text=btn_reset_text,
            image=reset_icon if reset_icon else None,
            compound="left" if reset_icon else "none",
            style='Action.TButton', command=self._reset_filter)
        if reset_icon:
            self.btn_reset_filter.image = reset_icon
        self.btn_reset_filter.grid(row=1, column=5, sticky="w", padx=(0, 5))
        
        # Chart button
        self.btn_show_chart = ttk.Button(
            inner_frame,
            text="Diagramm",
            style='Chart.TButton',
            command=self._show_chart)
        self.btn_show_chart.grid(row=1, column=6, sticky="ew", padx=(5, 0))

    # ==================== TABLE SECTION ====================
    def _build_table_section(self, parent: ttk.Frame) -> None:
        """Build price table section"""
        table_frame = ttk.LabelFrame(
            parent,
            text="Kursübersicht",
            style='Card.TLabelframe',
            padding=15
        )
        table_frame.grid(row=2, column=0, sticky="nsew")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ttk.Frame(table_frame, style='Card.TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        self.lbl_count = ttk.Label(header_frame, text="(0 Einträge)", style='Count.TLabel')
        self.lbl_count.pack(side="left")
        
        # Right side buttons
        button_frame = ttk.Frame(header_frame, style='Card.TFrame')
        button_frame.pack(side="right")
        
        # Clear database button
        self.btn_clear_db = ttk.Button(
            button_frame,
            text="Datenbank leeren",
            style='Danger.TButton',
            command=self._clear_database)
        self.btn_clear_db.pack(side="right", padx=(5, 0))
        
        # Export button
        export_icon = self._icon_manager.load_button_icon(Constants.ICON_EXPORT)
        btn_export_text = f"{EmojiIcons.EXPORT} CSV Export" if not export_icon else "CSV Export"
        self.btn_export = ttk.Button(
            button_frame, text=btn_export_text,
            image=export_icon if export_icon else None,
            compound="left" if export_icon else "none",
            style='Action.TButton', command=self._export_csv)
        if export_icon:
            self.btn_export.image = export_icon
        self.btn_export.pack(side="right")
        
        # Table
        tree_container = ttk.Frame(table_frame, style='Card.TFrame')
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        columns = ("symbol", "name", "close", "currency", "change", "date")
        self.tree = ttk.Treeview(
            tree_container, columns=columns,
            show="headings", style='Custom.Treeview', selectmode='extended')
        
        column_config = {
            "symbol": ("Symbol", 120, "center"),
            "name": ("Name", 320, "w"),
            "close": ("Kurs", 140, "e"),
            "currency": ("Währung", 100, "center"),
            "change": ("Änderung %", 120, "e"),
            "date": ("Datum", 120, "center"),
        }
        
        for col, (heading, width, anchor) in column_config.items():
            self.tree.heading(col, text=heading, anchor='center')
            self.tree.column(col, width=width, anchor=anchor, minwidth=80, stretch=True)
        
        scrollbar_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        self.tree.tag_configure('oddrow', background='#f8f9fa')
        self.tree.tag_configure('evenrow', background='#ffffff')
        self.tree.tag_configure('positive', foreground='#4CAF50')
        self.tree.tag_configure('negative', foreground='#F44336')
        self.tree.bind('<Motion>', self._on_tree_hover)
        self.tree.bind('<Button-3>', self._show_price_context_menu)
        
        # Aktiviere sortierbare Spalten
        columns = ("symbol", "name", "close", "currency", "change", "date")
        self._make_sortable(self.tree, columns)
    
    def _show_price_context_menu(self, event):
        """Show context menu on right-click"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.price_context_menu.post(event.x_root, event.y_root)
    
    def _on_tree_hover(self, event):
        """Add hover effect to treeview rows"""
        tree = event.widget
        item = tree.identify_row(event.y)
        
        for i in tree.get_children():
            tags = list(tree.item(i, 'tags'))
            if 'hover' in tags:
                tags.remove('hover')
                tree.item(i, tags=tags)
        
        if item:
            tags = list(tree.item(item, 'tags'))
            if 'hover' not in tags:
                tags.append('hover')
                tree.item(item, tags=tags)
        
        tree.tag_configure('hover', background='#e3f2fd')
    
    # ==================== PORTFOLIO TAB ====================
    
    def _build_portfolio_tab(self, parent: ttk.Frame) -> None:
        """Build portfolio management tab"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)
        
        self._build_portfolio_summary(parent)
        self._build_transaction_input(parent)
        self._build_portfolio_table(parent)
        
        # Setup context menu
        self._setup_portfolio_context_menu()

    # ==================== DIVIDENDS TAB ====================

    def _build_dividends_tab(self, parent: ttk.Frame) -> None:
        """Build dividends tab"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        self._build_dividend_summary(parent)
        self._build_dividend_input(parent)
        self._build_dividend_table(parent)

    def _build_dividend_summary(self, parent: ttk.Frame) -> None:
        """Build dividend summary section"""
        summary_frame = ttk.LabelFrame(
            parent,
            text="Dividenden-Übersicht",
            style='Card.TLabelframe',
            padding=15
        )
        summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        inner_frame = ttk.Frame(summary_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)

        self.lbl_dividend_total = ttk.Label(
            inner_frame,
            text="Gesamtdividenden: 0,00 EUR",
            style='Summary.TLabel'
        )
        self.lbl_dividend_total.pack(side="left", padx=(0, 30))

        self.lbl_dividend_count = ttk.Label(
            inner_frame,
            text="0 Ausschüttungen",
            style='Summary.TLabel'
        )
        self.lbl_dividend_count.pack(side="left", padx=(0, 30))

        year_values = ["Alle"] + [str(date.today().year - i) for i in range(0, 11)]
        self.var_dividend_year = tk.StringVar(value="Alle")
        self.cmb_dividend_year = ttk.Combobox(
            inner_frame,
            textvariable=self.var_dividend_year,
            values=year_values,
            width=10,
            state="readonly",
            font=('Segoe UI', 9)
        )
        self.cmb_dividend_year.pack(side="right", padx=(5, 0))
        self.cmb_dividend_year.bind("<<ComboboxSelected>>", lambda _: self._refresh_dividends())

        ttk.Label(inner_frame, text="Jahr:", style='Header.TLabel').pack(side="right")

    def _build_dividend_input(self, parent: ttk.Frame) -> None:
        """Build dividend input section"""
        input_frame = ttk.LabelFrame(
            parent,
            text="Neue Dividende",
            style='Card.TLabelframe',
            padding=15
        )
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        inner_frame = ttk.Frame(input_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)
        inner_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(inner_frame, text="Asset:", style='Header.TLabel').grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 5))
        ttk.Label(inner_frame, text="Datum:", style='Header.TLabel').grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(0, 5))
        ttk.Label(inner_frame, text="Brutto:", style='Header.TLabel').grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 5))
        ttk.Label(inner_frame, text="Steuer:", style='Header.TLabel').grid(row=0, column=3, sticky="w", padx=(0, 8), pady=(0, 5))
        ttk.Label(inner_frame, text="Währung:", style='Header.TLabel').grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 5))
        ttk.Label(inner_frame, text="Typ:", style='Header.TLabel').grid(row=0, column=5, sticky="w", padx=(0, 8), pady=(0, 5))

        self.var_dividend_asset = tk.StringVar()
        self.cmb_dividend_asset = ttk.Combobox(
            inner_frame,
            textvariable=self.var_dividend_asset,
            state="readonly",
            font=('Segoe UI', 9),
            height=10
        )
        self.cmb_dividend_asset["values"] = [asset.display_name() for asset in self._assets]
        if self._assets:
            self.cmb_dividend_asset.current(0)
        self.cmb_dividend_asset.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self.dividend_date_entry = DateEntry(
            inner_frame,
            width=12,
            background='#1976D2',
            foreground='white',
            borderwidth=1,
            date_pattern='yyyy-mm-dd',
            locale='de_DE',
            font=('Segoe UI', 9)
        )
        self.dividend_date_entry.set_date(date.today())
        self.dividend_date_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        self.var_dividend_amount = tk.StringVar()
        self.ent_dividend_amount = ttk.Entry(
            inner_frame,
            textvariable=self.var_dividend_amount,
            width=12,
            font=('Segoe UI', 9)
        )
        self.ent_dividend_amount.grid(row=1, column=2, sticky="ew", padx=(0, 8))
        self._setup_quantity_validation(self.ent_dividend_amount)

        self.var_dividend_tax = tk.StringVar(value="0")
        self.ent_dividend_tax = ttk.Entry(
            inner_frame,
            textvariable=self.var_dividend_tax,
            width=12,
            font=('Segoe UI', 9)
        )
        self.ent_dividend_tax.grid(row=1, column=3, sticky="ew", padx=(0, 8))
        self._setup_quantity_validation(self.ent_dividend_tax)

        self.var_dividend_currency = tk.StringVar(value=self._config.default_currency)
        self.ent_dividend_currency = ttk.Entry(
            inner_frame,
            textvariable=self.var_dividend_currency,
            width=8,
            font=('Segoe UI', 9)
        )
        self.ent_dividend_currency.grid(row=1, column=4, sticky="ew", padx=(0, 8))

        self.var_dividend_type = tk.StringVar(value="Regular")
        self.cmb_dividend_type = ttk.Combobox(
            inner_frame,
            textvariable=self.var_dividend_type,
            values=["Regular", "Special", "Capital Return"],
            state="readonly",
            width=14,
            font=('Segoe UI', 9)
        )
        self.cmb_dividend_type.grid(row=1, column=5, sticky="ew", padx=(0, 8))

        add_icon = self._icon_manager.load_button_icon(Constants.ICON_ADD)
        btn_add_text = f"{EmojiIcons.ADD} Hinzufügen" if not add_icon else "Hinzufügen"
        self.btn_add_dividend = ttk.Button(
            inner_frame,
            text=btn_add_text,
            image=add_icon if add_icon else None,
            compound="left" if add_icon else "none",
            style='Primary.TButton',
            command=self._on_add_dividend
        )
        if add_icon:
            self.btn_add_dividend.image = add_icon
        self.btn_add_dividend.grid(row=1, column=6, sticky="w", padx=(8, 0))

        export_icon = self._icon_manager.load_button_icon(Constants.ICON_EXPORT)
        btn_export_dividends_text = f"{EmojiIcons.EXPORT} CSV Export" if not export_icon else "CSV Export"
        self.btn_export_dividends = ttk.Button(
            inner_frame,
            text=btn_export_dividends_text,
            image=export_icon if export_icon else None,
            compound="left",
            style='Action.TButton',
            command=self._export_dividends
        )
        if export_icon:
            self.btn_export_dividends.image = export_icon
        self.btn_export_dividends.grid(row=1, column=7, sticky="w", padx=(6, 0))

    def _build_dividend_table(self, parent: ttk.Frame) -> None:
        """Build dividend table section"""
        table_frame = ttk.LabelFrame(
            parent,
            text="Dividenden nach Asset",
            style='Card.TLabelframe',
            padding=15
        )
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        columns = ("symbol", "name", "total_dividends", "dividend_count", "average_dividend", "current_holdings", "annual_yield", "currency")
        self.dividend_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style='Custom.Treeview'
        )

        column_config = {
            "symbol": ("Symbol", 100, "center"),
            "name": ("Name", 220, "w"),
            "total_dividends": ("Gesamt Netto", 140, "e"),
            "dividend_count": ("Anzahl", 90, "e"),
            "average_dividend": ("Ø Dividende", 130, "e"),
            "current_holdings": ("Bestand", 110, "e"),
            "annual_yield": ("Rendite %", 110, "e"),
            "currency": ("Währung", 90, "center"),
        }

        for col, (heading, width, anchor) in column_config.items():
            self.dividend_tree.heading(col, text=heading, anchor='center')
            self.dividend_tree.column(col, width=width, anchor=anchor, minwidth=70, stretch=True)

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.dividend_tree.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.dividend_tree.xview)
        self.dividend_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.dividend_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        self.dividend_tree.tag_configure('oddrow', background='#f8f9fa')
        self.dividend_tree.tag_configure('evenrow', background='#ffffff')
        self._make_sortable(self.dividend_tree, columns)

    def _build_alerts_tab(self, parent: ttk.Frame) -> None:
        """Build alerts tab"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        input_frame = ttk.LabelFrame(parent, text="Neuer Alarm", style='Card.TLabelframe', padding=15)
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        inner = ttk.Frame(input_frame, style='Card.TFrame')
        inner.pack(fill="both", expand=True)

        ttk.Label(inner, text="Asset:", style='Header.TLabel').grid(row=0, column=0, sticky="w")
        self.var_alert_asset = tk.StringVar()
        self.cmb_alert_asset = ttk.Combobox(
            inner,
            textvariable=self.var_alert_asset,
            values=[a.display_name() for a in self._assets],
            state="readonly",
            width=30,
            font=('Segoe UI', 9)
        )
        if self._assets:
            self.cmb_alert_asset.current(0)
        self.cmb_alert_asset.grid(row=0, column=1, padx=5)

        ttk.Label(inner, text="Typ:", style='Header.TLabel').grid(row=0, column=2, sticky="w")
        self.var_alert_type = tk.StringVar(value="Über")
        self.cmb_alert_type = ttk.Combobox(
            inner,
            textvariable=self.var_alert_type,
            values=["Über", "Unter", "Änderung %"],
            state="readonly",
            width=12,
            font=('Segoe UI', 9)
        )
        self.cmb_alert_type.grid(row=0, column=3, padx=5)

        ttk.Label(inner, text="Schwellwert:", style='Header.TLabel').grid(row=0, column=4, sticky="w")
        self.var_alert_threshold = tk.StringVar()
        self.ent_alert_threshold = ttk.Entry(inner, textvariable=self.var_alert_threshold, width=15, font=('Segoe UI', 9))
        self.ent_alert_threshold.grid(row=0, column=5, padx=5)
        self._setup_quantity_validation(self.ent_alert_threshold)

        add_icon = self._icon_manager.load_button_icon(Constants.ICON_ADD)
        btn_add_text = f"{EmojiIcons.ADD} Hinzufügen" if not add_icon else "Hinzufügen"
        self.btn_add_alert = ttk.Button(
            inner,
            text=btn_add_text,
            image=add_icon if add_icon else None,
            compound="left" if add_icon else "none",
            style='Primary.TButton',
            command=self._on_add_alert
        )
        if add_icon:
            self.btn_add_alert.image = add_icon
        self.btn_add_alert.grid(row=0, column=6, padx=5)

        table_frame = ttk.LabelFrame(parent, text="Aktive Alarme", style='Card.TLabelframe', padding=15)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        columns = ("symbol", "name", "type", "threshold", "status")
        self.alerts_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style='Custom.Treeview'
        )

        self.alerts_tree.heading("symbol", text="Symbol")
        self.alerts_tree.heading("name", text="Name")
        self.alerts_tree.heading("type", text="Typ")
        self.alerts_tree.heading("threshold", text="Schwellwert")
        self.alerts_tree.heading("status", text="Status")

        self.alerts_tree.column("symbol", width=100, anchor='center')
        self.alerts_tree.column("name", width=250, anchor='w')
        self.alerts_tree.column("type", width=120, anchor='center')
        self.alerts_tree.column("threshold", width=120, anchor='e')
        self.alerts_tree.column("status", width=100, anchor='center')

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=scrollbar.set)

        self.alerts_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._make_sortable(self.alerts_tree, columns)
        self._theme_manager.apply_to_treeview(self.alerts_tree)

        self.alerts_context_menu = tk.Menu(self, tearoff=0)
        self.alerts_context_menu.add_command(label="Alarm deaktivieren", command=self._deactivate_selected_alert)
        self.alerts_context_menu.add_command(label="Alarm löschen", command=self._delete_selected_alert)
        self.alerts_tree.bind('<Button-3>', self._show_alert_context_menu)

        btn_frame = ttk.Frame(table_frame, style='Card.TFrame')
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        ttk.Button(btn_frame, text="🔍 Alarme prüfen", command=self._check_alerts).pack(side="left")
        ttk.Button(btn_frame, text="⏸️ Alarm deaktivieren", command=self._deactivate_selected_alert).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🗑️ Alarm löschen", command=self._delete_selected_alert).pack(side="left", padx=5)

        self._refresh_alerts()

    def _show_alert_context_menu(self, event):
        """Show alert context menu on right-click"""
        item = self.alerts_tree.identify_row(event.y)
        if item:
            self.alerts_tree.selection_set(item)
            self.alerts_context_menu.post(event.x_root, event.y_root)

    def _get_selected_alert_asset(self) -> Optional[Asset]:
        """Get selected asset for alert creation"""
        idx = self.cmb_alert_asset.current()
        if idx < 0 or idx >= len(self._assets):
            return None
        return self._assets[idx]

    def _on_add_alert(self):
        """Add new alert"""
        if self._alert_service is None:
            messagebox.showwarning("⚠️ Nicht verfügbar", "Alarm-Service ist noch nicht initialisiert.")
            return

        try:
            asset = self._get_selected_alert_asset()
            if not asset:
                raise ValidationError("Kein Asset", "Bitte Asset wählen")

            type_str = self.var_alert_type.get()
            if type_str == "Über":
                alert_type = AlertType.ABOVE
            elif type_str == "Unter":
                alert_type = AlertType.BELOW
            else:
                alert_type = AlertType.CHANGE_PERCENT

            raw_threshold = self.var_alert_threshold.get().strip().replace(',', '.')
            if not raw_threshold:
                raise ValidationError("Schwellwert fehlt", "Bitte einen Schwellwert eingeben.")

            threshold = Decimal(raw_threshold)

            self._alert_service.create_alert(
                asset_id=asset.id,
                alert_type=alert_type,
                threshold_value=threshold,
                currency=self._config.default_currency,
            )

            messagebox.showinfo("✅ Erfolg", "Alarm erstellt")
            self.var_alert_threshold.set("")
            self._refresh_alerts()

        except InvalidOperation:
            self._show_error("Fehler", ValidationError("Ungültiger Schwellwert", "Bitte gültige Zahl eingeben."))
        except (ValidationError, DatabaseError) as e:
            self._show_error("Fehler", e)

    def _refresh_alerts(self):
        """Refresh alerts table"""
        if not hasattr(self, 'alerts_tree'):
            return

        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)

        if self._alert_service is None:
            return

        alerts = self._alert_service.get_all_alerts(include_triggered=True)

        for idx, alert in enumerate(alerts):
            asset = next((a for a in self._assets if a.id == alert.asset_id), None)
            if not asset:
                continue

            type_str = {
                AlertType.ABOVE: "Über",
                AlertType.BELOW: "Unter",
                AlertType.CHANGE_PERCENT: "Änderung %"
            }[alert.alert_type]

            if alert.alert_type == AlertType.CHANGE_PERCENT:
                threshold_text = f"{alert.threshold_value}%"
            else:
                threshold_text = f"{alert.threshold_value} {alert.currency}"

            status = "✅ Ausgelöst" if alert.triggered else ("⏸️ Inaktiv" if not alert.active else "🔔 Aktiv")
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'

            self.alerts_tree.insert(
                "",
                "end",
                iid=str(alert.id),
                values=(asset.symbol, asset.name, type_str, threshold_text, status),
                tags=(tag,)
            )

        self._theme_manager.apply_to_treeview(self.alerts_tree)

    def _check_alerts(self):
        """Check all alerts and notify user"""
        if self._alert_service is None:
            messagebox.showwarning("⚠️ Nicht verfügbar", "Alarm-Service ist noch nicht initialisiert.")
            return

        try:
            triggered = self._alert_service.check_alerts()
            if not triggered:
                messagebox.showinfo("✅ Keine Alarme", "Keine Alarme wurden ausgelöst.")
            else:
                messages = "\n\n".join(t.message for t in triggered)
                messagebox.showwarning(f"🔔 {len(triggered)} Alarm(e) ausgelöst!", messages)
            self._refresh_alerts()
        except DatabaseError as e:
            self._show_error("Fehler", e)

    def _check_alerts_silent(self):
        """Silent alert check used after price refresh."""
        if self._alert_service is None:
            return
        try:
            triggered = self._alert_service.check_alerts()
            if triggered:
                self._refresh_alerts()
        except Exception:
            pass

    def _delete_selected_alert(self):
        """Delete selected alert"""
        if self._alert_service is None:
            return

        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning("⚠️ Keine Auswahl", "Bitte wählen Sie einen Alarm aus.")
            return

        alert_id = int(selection[0])
        if not messagebox.askyesno("🗑️ Alarm löschen", "Möchten Sie diesen Alarm wirklich löschen?"):
            return

        try:
            self._alert_service.delete_alert(alert_id)
            self._refresh_alerts()
        except DatabaseError as e:
            self._show_error("Fehler", e)

    def _deactivate_selected_alert(self):
        """Deactivate selected alert"""
        if self._alert_service is None:
            return

        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning("⚠️ Keine Auswahl", "Bitte wählen Sie einen Alarm aus.")
            return

        alert_id = int(selection[0])
        try:
            self._alert_service.deactivate_alert(alert_id)
            self._refresh_alerts()
        except DatabaseError as e:
            self._show_error("Fehler", e)

    def _show_desktop_notification(self, triggered_alerts: List[TriggeredAlert]):
        """Show Windows desktop notification (optional)"""
        try:
            import importlib
            toast_module = importlib.import_module("win10toast")
            toaster = toast_module.ToastNotifier()
            for alert in triggered_alerts:
                toaster.show_toast(
                    "🔔 Preisalarm",
                    alert.message,
                    duration=10,
                    threaded=True,
                )
        except Exception:
            pass

    def _get_selected_dividend_asset(self) -> Optional[Asset]:
        """Get selected asset for dividend entry"""
        idx = self.cmb_dividend_asset.current()
        if idx < 0 or idx >= len(self._assets):
            return None
        return self._assets[idx]

    def _on_add_dividend(self) -> None:
        """Handle add dividend button"""
        if self._dividend_service is None:
            messagebox.showwarning("⚠️ Nicht verfügbar", "Dividenden-Service ist noch nicht initialisiert.")
            return

        try:
            asset = self._get_selected_dividend_asset()
            if not asset:
                raise ValidationError("Kein Asset ausgewählt", "Bitte wählen Sie ein Asset aus der Liste aus.")

            type_map = {
                "Regular": DividendType.REGULAR,
                "Special": DividendType.SPECIAL,
                "Capital Return": DividendType.CAPITAL_RETURN,
            }
            dividend_type = type_map.get(self.var_dividend_type.get(), DividendType.REGULAR)

            self._dividend_service.add_dividend(
                asset_id=asset.id,
                payment_date=self.dividend_date_entry.get_date(),
                amount_str=self.var_dividend_amount.get(),
                currency=self.var_dividend_currency.get(),
                tax_withheld_str=self.var_dividend_tax.get(),
                dividend_type=dividend_type,
                notes=None,
            )

            messagebox.showinfo(f"{EmojiIcons.CHECK} Erfolg", "Dividende hinzugefügt")
            self.var_dividend_amount.set("")
            self.var_dividend_tax.set("0")
            self._refresh_dividends()
        except (ValidationError, DatabaseError) as e:
            self._show_error("Fehler", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Hinzufügen der Dividende", str(e)))

    def _refresh_dividends(self) -> None:
        """Refresh dividend summary and table"""
        if not hasattr(self, 'dividend_tree'):
            return

        if self._dividend_service is None:
            self._current_dividend_summary = []
            self._update_dividend_table()
            self._update_dividend_summary_labels()
            return

        try:
            year_value = self.var_dividend_year.get() if hasattr(self, 'var_dividend_year') else "Alle"
            year = None if year_value == "Alle" else int(year_value)
            self._current_dividend_summary = self._dividend_service.get_dividend_summary(year)
            self._update_dividend_table()
            self._update_dividend_summary_labels()
        except (ValidationError, DatabaseError) as e:
            self._show_error("Fehler beim Laden der Dividenden", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Aktualisieren der Dividenden", str(e)))

    def _update_dividend_table(self) -> None:
        """Update dividend summary table"""
        for item in self.dividend_tree.get_children():
            self.dividend_tree.delete(item)

        for idx, summary in enumerate(self._current_dividend_summary):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'

            total_str = self._format_large_number(float(summary.total_dividends))
            avg_str = self._format_large_number(float(summary.average_dividend))
            holdings_str = self._format_large_number(float(summary.current_holdings))
            yield_str = "—"
            if summary.annual_yield is not None:
                yield_str = f"{float(summary.annual_yield):.2f}".replace('.', ',') + "%"

            self.dividend_tree.insert("", "end", values=(
                summary.symbol,
                summary.name,
                total_str,
                summary.dividend_count,
                avg_str,
                holdings_str,
                yield_str,
                summary.currency,
            ), tags=tag)

    def _update_dividend_summary_labels(self) -> None:
        """Update dividend overview labels"""
        if not hasattr(self, 'lbl_dividend_total'):
            return

        total = 0.0
        for summary in self._current_dividend_summary:
            total += float(summary.total_dividends)

        count = sum(item.dividend_count for item in self._current_dividend_summary)
        self.lbl_dividend_total.config(
            text=f"Gesamtdividenden: {self._format_large_number(total)} {self._config.default_currency}"
        )
        self.lbl_dividend_count.config(text=f"{count} Ausschüttungen")

    def _export_dividends(self) -> None:
        """Export dividends as CSV"""
        if self._dividend_service is None:
            messagebox.showwarning("⚠️ Nicht verfügbar", "Dividenden-Service ist noch nicht initialisiert.")
            return

        try:
            year_value = self.var_dividend_year.get() if hasattr(self, 'var_dividend_year') else "Alle"
            year = None if year_value == "Alle" else int(year_value)

            suffix = year_value if year else date.today().isoformat()
            default_filename = f"dividenden_export_{suffix}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
                initialfile=default_filename
            )
            if not file_path:
                return

            self._dividend_service.export_dividends_csv(Path(file_path), year)
            messagebox.showinfo(f"{EmojiIcons.CHECK} Erfolg", f"Dividenden erfolgreich exportiert:\n\n{file_path}")
        except (ValidationError, DatabaseError) as e:
            self._show_error("Export-Fehler", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Dividenden-Export", str(e)))
        
    # Portfolioübersicht, Transaktionseingabe, Portfoliotabelle und Kontextmenü für Portfolioverwaltung
    def _setup_portfolio_context_menu(self) -> None:
        """Setup right-click context menu for portfolio treeview"""
        self.portfolio_context_menu = tk.Menu(self, tearoff=0)
        self.portfolio_context_menu.add_command(
            label="Details anzeigen",  # OHNE Emoji
            command=self._show_portfolio_details,
            font=('Segoe UI', 10)  # Größere Schrift
        )

    def _build_portfolio_summary(self, parent: ttk.Frame) -> None:
        """Build portfolio summary section"""
        summary_frame = ttk.LabelFrame(
            parent,
            text="Portfolio-Übersicht",
            style='Card.TLabelframe',
            padding=15
        )
        summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        inner_frame = ttk.Frame(summary_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)
        
        # Summary labels
        self.lbl_portfolio_value = ttk.Label(
            inner_frame,
            text="Gesamtwert: 0,00 EUR",
            style='Summary.TLabel'
        )
        self.lbl_portfolio_value.pack(side="left", padx=(0, 30))
        
        self.lbl_portfolio_profit = ttk.Label(
            inner_frame,
            text="Gewinn/Verlust: +0,00 EUR (0,00%)",
            style='Summary.TLabel'
        )
        self.lbl_portfolio_profit.pack(side="left")
    
    def _build_transaction_input(self, parent: ttk.Frame) -> None:
        """Build transaction input section"""
        input_frame = ttk.LabelFrame(
            parent,
            text="Neue Transaktion",
            style='Card.TLabelframe',
            padding=15
        )
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        inner_frame = ttk.Frame(input_frame, style='Card.TFrame')
        inner_frame.pack(fill="both", expand=True)
        inner_frame.grid_columnconfigure(1, weight=1)
        
        # Labels row
        ttk.Label(inner_frame, text="Typ:", style='Header.TLabel').grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text=f"{EmojiIcons.CHART} Asset:", style='Header.TLabel').grid(
            row=0, column=1, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Menge:", style='Header.TLabel').grid(
            row=0, column=2, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Preis:", style='Header.TLabel').grid(
            row=0, column=3, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text="Währung:", style='Header.TLabel').grid(
            row=0, column=4, sticky="w", padx=(0, 10), pady=(0, 5))
        ttk.Label(inner_frame, text=f"{EmojiIcons.CALENDAR} Datum:", style='Header.TLabel').grid(
            row=0, column=5, sticky="w", padx=(0, 10), pady=(0, 5))
        
        # Input fields row
        self.var_transaction_type = tk.StringVar(value="Kauf")
        self.cmb_transaction_type = ttk.Combobox(
            inner_frame,
            textvariable=self.var_transaction_type,
            values=["Kauf", "Verkauf"],
            state="readonly",
            width=10,
            font=('Segoe UI', 9)
        )
        self.cmb_transaction_type.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        self.var_portfolio_asset = tk.StringVar()
        self.cmb_portfolio_asset = ttk.Combobox(
            inner_frame,
            textvariable=self.var_portfolio_asset,
            state="readonly",
            font=('Segoe UI', 9),
            height=10
        )
        self.cmb_portfolio_asset["values"] = [asset.display_name() for asset in self._assets]
        if self._assets:
            self.cmb_portfolio_asset.current(0)
        self.cmb_portfolio_asset.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        
        self.var_quantity = tk.StringVar()
        self.ent_quantity = ttk.Entry(
            inner_frame,
            textvariable=self.var_quantity,
            width=12,
            font=('Segoe UI', 9)
        )
        self.ent_quantity.grid(row=1, column=2, sticky="ew", padx=(0, 10))
        self._setup_quantity_validation(self.ent_quantity)
        
        self.var_price = tk.StringVar()
        self.ent_price = ttk.Entry(
            inner_frame,
            textvariable=self.var_price,
            width=12,
            font=('Segoe UI', 9)
        )
        self.ent_price.grid(row=1, column=3, sticky="ew", padx=(0, 10))
        self._setup_quantity_validation(self.ent_price)
        
        self.var_portfolio_currency = tk.StringVar(value=self._config.default_currency)
        self.ent_portfolio_currency = ttk.Entry(
            inner_frame,
            textvariable=self.var_portfolio_currency,
            width=8,
            font=('Segoe UI', 9)
        )
        self.ent_portfolio_currency.grid(row=1, column=4, sticky="ew", padx=(0, 10))
        
        self.transaction_date_entry = DateEntry(
            inner_frame,
            width=12,
            background='#1976D2',
            foreground='white',
            borderwidth=1,
            date_pattern='yyyy-mm-dd',
            locale='de_DE',
            font=('Segoe UI', 9)
        )
        self.transaction_date_entry.set_date(date.today())
        self.transaction_date_entry.grid(row=1, column=5, sticky="ew", padx=(0, 10))
        
        # Add button
        add_icon = self._icon_manager.load_button_icon(Constants.ICON_ADD)
        btn_add_text = f"{EmojiIcons.ADD} Hinzufügen" if not add_icon else "Hinzufügen"
        self.btn_add_transaction = ttk.Button(
            inner_frame,
            text=btn_add_text,
            image=add_icon if add_icon else None,
            compound="left" if add_icon else "none",
            style='Primary.TButton',
            command=self._on_add_transaction
        )
        if add_icon:
            self.btn_add_transaction.image = add_icon
        self.btn_add_transaction.grid(row=1, column=6, sticky="w")
    
    def _build_portfolio_table(self, parent: ttk.Frame) -> None:
        """Build portfolio table section"""
        table_frame = ttk.LabelFrame(
            parent,
            text="Meine Positionen",
            style='Card.TLabelframe',
            padding=15
        )
        table_frame.grid(row=2, column=0, sticky="nsew")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ttk.Frame(table_frame, style='Card.TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        self.lbl_portfolio_count = ttk.Label(
            header_frame,
            text="(0 Positionen)",
            style='Count.TLabel'
        )
        self.lbl_portfolio_count.pack(side="left")
        
        # Right side buttons
        button_frame = ttk.Frame(header_frame, style='Card.TFrame')
        button_frame.pack(side="right")
        
        # Clear portfolio buttonn
        self.btn_clear_portfolio = ttk.Button(
            button_frame,
            text="Portfolio leeren",
            style='Danger.TButton',
            command=self._clear_portfolio)
        self.btn_clear_portfolio.pack(side="right", padx=(5, 0))

        # Export portfolio button
        export_icon = self._icon_manager.load_button_icon(Constants.ICON_EXPORT)
        btn_export_portfolio_text = f"{EmojiIcons.EXPORT} Portfolio exportieren" if not export_icon else "Portfolio exportieren"
        self.btn_export_portfolio = ttk.Button(
            button_frame,
            text=btn_export_portfolio_text,
            image=export_icon if export_icon else None,
            compound="left",
            style='Action.TButton',
            command=self._export_portfolio
        )
        if export_icon:
            self.btn_export_portfolio.image = export_icon
        self.btn_export_portfolio.pack(side="right")
        
        # Table
        tree_container = ttk.Frame(table_frame, style='Card.TFrame')
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        columns = ("symbol", "name", "quantity", "avg_price", "current_price", 
                   "value", "profit_loss", "profit_percent")
        self.portfolio_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style='Custom.Treeview'
        )
        
        column_config = {
            "symbol": ("Symbol", 100, "center"),
            "name": ("Name", 250, "w"),
            "quantity": ("Menge", 100, "e"),
            "avg_price": ("Ø Kaufpreis", 120, "e"),
            "current_price": ("Aktueller Kurs", 120, "e"),
            "value": ("Wert", 120, "e"),
            "profit_loss": ("Gewinn/Verlust", 130, "e"),
            "profit_percent": ("G/V %", 100, "e"),
        }
        
        for col, (heading, width, anchor) in column_config.items():
            self.portfolio_tree.heading(col, text=heading, anchor='center')
            self.portfolio_tree.column(col, width=width, anchor=anchor, minwidth=80, stretch=True)
        
        scrollbar_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.portfolio_tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.portfolio_tree.xview)
        
        self.portfolio_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.portfolio_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        self.portfolio_tree.tag_configure('oddrow', background='#f8f9fa')
        self.portfolio_tree.tag_configure('evenrow', background='#ffffff')
        self.portfolio_tree.tag_configure('profit', foreground='#4CAF50')
        self.portfolio_tree.tag_configure('loss', foreground='#F44336')
        self.portfolio_tree.bind('<Button-3>', self._show_portfolio_context_menu_event)
        
        # Aktiviere sortierbare Spalten
        columns = ("symbol", "name", "quantity", "avg_price", "current_price", "value", "profit_loss", "profit_percent")
        self._make_sortable(self.portfolio_tree, columns)
    
    def _show_portfolio_context_menu_event(self, event):
        """Show portfolio context menu on right-click"""
        item = self.portfolio_tree.identify_row(event.y)
        if item:
            self.portfolio_tree.selection_set(item)
            self.portfolio_context_menu.post(event.x_root, event.y_root)
    
    # ==================== HELPER METHODS ====================
    
    def _get_selected_asset(self) -> Optional[Asset]:
        """Get currently selected asset from price input"""
        idx = self.cmb_asset.current()
        if idx < 0 or idx >= len(self._assets):
            return None
        return self._assets[idx]
    
    def _get_selected_portfolio_asset(self) -> Optional[Asset]:
        """Get currently selected asset from portfolio input"""
        idx = self.cmb_portfolio_asset.current()
        if idx < 0 or idx >= len(self._assets):
            return None
        return self._assets[idx]
    
    def _get_filter_asset_id(self) -> Optional[int]:
        """Get selected asset ID from filter"""
        idx = self.cmb_filter_asset.current()
        if idx <= 0:
            return None
        return self._assets[idx - 1].id
    
    def _get_filter_currency(self) -> Optional[str]:
        """Get selected currency from filter"""
        value = self.var_filter_currency.get()
        if value == "Alle":
            return None
        return value
    
    def _build_price_filter(self) -> PriceFilter:
        """Build PriceFilter from UI inputs"""
        price_filter = PriceFilter()
        price_filter.date_from = self.filter_date_from.get_date()
        price_filter.date_to = self.filter_date_to.get_date()
        price_filter.asset_id = self._get_filter_asset_id()
        price_filter.currency = self._get_filter_currency()
        return price_filter
    
    def _show_error(self, title: str, error: PortfolioError) -> None:
        """Display error message with details"""
        messagebox.showerror(f"❌ {title}", error.get_full_message())
    
    def _format_price(self, price: float) -> str:
        """Format price with German number formatting (1.234,56)"""
        if abs(price) >= 1000:
            # German format: 1.234,56
            return f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif price < 10 and price > 0:
            # More decimals for small numbers
            return f"{price:.4f}".replace(".", ",")
        else:
            return f"{price:.2f}".replace(".", ",")
    
    def _format_large_number(self, number: float) -> str:
        """Format large number with German thousand separators (1.234,56)"""
        if abs(number) >= 1000:
            return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return f"{number:.2f}".replace(".", ",")
    
    def _format_currency(self, amount: float, currency: str = "EUR") -> str:
        """Format amount as currency with German formatting"""
        formatted = self._format_large_number(amount)
        return f"{formatted} {currency}"
    
    # ==================== PRICE MANAGEMENT ACTIONS ====================
    
    def _on_save(self) -> None:
        """Handle save button click"""
        try:
            price_date = self.date_entry.get_date()
            asset = self._get_selected_asset()
            
            if not asset:
                raise ValidationError(
                    "Kein Asset ausgewählt",
                    "Bitte wählen Sie ein Asset aus der Liste aus."
                )
            
            self._price_service.save_price(
                asset_id=asset.id,
                price_date=price_date,
                close_str=self.var_close.get(),
                currency=self.var_cur.get(),
            )
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Erfolg",
                f"Kurs gespeichert:\n\nAsset: {asset.symbol}\nDatum: {price_date.isoformat()}\nKurs: {self.var_close.get()} {self.var_cur.get()}"
            )
            self._apply_filter()
            self._check_alerts_silent()
            self._refresh_portfolio()
            
            self.var_close.set("")
            self.ent_close.focus_set()
            
        except (ValidationError, DatabaseError) as e:
            self._show_error("Fehler beim Speichern", e)
        except Exception as e:
            self._show_error("Unerwarteter Fehler", PortfolioError("Fehler beim Speichern", str(e)))
    
    def _delete_selected_entry(self) -> None:
        """Delete selected price entry from table"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "⚠️ Keine Auswahl",
                "Bitte wählen Sie einen Eintrag zum Löschen aus."
            )
            return
        
        item = selection[0]
        values = self.tree.item(item, 'values')
        symbol = values[0]
        date_str = values[5]
        
        result = messagebox.askyesno(
            "🗑️ Eintrag löschen",
            f"Möchten Sie diesen Eintrag wirklich löschen?\n\n"
            f"Symbol: {symbol}\n"
            f"Datum: {date_str}\n\n"
            f"ℹ️ Ein Backup wird automatisch erstellt.",
            icon='warning'
        )
        
        if not result:
            return

        try:
            if self._backup_service is not None and self._config.enable_auto_backup:
                try:
                    self._backup_service.create_backup("eintrag_loeschen")
                except BackupError as e:
                    if not messagebox.askyesno(
                        "⚠️ Backup fehlgeschlagen",
                        f"{e.message}\n\nTrotzdem löschen?"
                    ):
                        return

            price_date = date.fromisoformat(date_str)
            self._price_service.delete_price(symbol, price_date)
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Erfolg",
                f"Eintrag gelöscht:\n{symbol} vom {date_str}"
            )
            self._apply_filter()
            
        except DatabaseError as e:
            self._show_error("Fehler beim Löschen", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Löschen", str(e)))
    
    def _clear_database(self) -> None:
        """Clear all price entries from database with triple confirmation"""
        result1 = messagebox.askokcancel(
            "⚠️ ACHTUNG - Datenbank leeren",
            "Sie sind dabei ALLE Kurseinträge zu löschen!\n\n"
            "⚠️ Dies betrifft:\n"
            f"   • {len(self._current_prices)} Kurseinträge\n"
            "   • Alle historischen Daten\n\n"
            "ℹ️ Ein Backup wird automatisch erstellt.\n\n"
            "Möchten Sie fortfahren?",
            icon='warning'
        )
        
        if not result1:
            return

        countdown_dialog = CountdownDialog(
            self,
            title="⏳ Letzte Warnung",
            message=(
                "Sie löschen gleich ALLE Kursdaten!\n\n"
                "⚠️ Diese Aktion ist UNWIDERRUFLICH!\n\n"
                "Bitte warten Sie 5 Sekunden und überlegen Sie nochmal..."
            ),
            countdown_seconds=5,
            icon="error"
        )

        if not countdown_dialog.show():
            return

        confirm_dialog = ConfirmationDialog(
            self,
            title="🔒 Finale Bestätigung",
            message=(
                "Um die Datenbank zu leeren, tippen Sie bitte:\n\n"
                "LÖSCHEN\n\n"
                "(in Großbuchstaben)"
            ),
            required_text="LÖSCHEN"
        )

        if not confirm_dialog.show():
            messagebox.showinfo("✅ Abgebrochen", "Aktion wurde abgebrochen. Keine Daten gelöscht.")
            return
        
        try:
            backup_name = None
            if self._backup_service is not None and self._config.enable_auto_backup:
                try:
                    backup_path = self._backup_service.create_backup("datenbank_leeren")
                    backup_name = backup_path.name
                except BackupError as e:
                    if not messagebox.askyesno(
                        "⚠️ Backup fehlgeschlagen",
                        f"{e.message}\n\nTrotzdem fortfahren?"
                    ):
                        return

            deleted_count = self._price_service.clear_all_prices()
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Datenbank geleert",
                (
                    f"Erfolgreich {deleted_count} Einträge gelöscht.\n\n"
                    f"Backup gespeichert unter:\n{backup_name}"
                ) if backup_name else (
                    f"Erfolgreich {deleted_count} Einträge gelöscht.\n\n"
                    "Die Datenbank wurde vollständig geleert."
                )
            )
            self._apply_filter()
            self._refresh_portfolio()
            
        except DatabaseError as e:
            self._show_error("Fehler beim Leeren", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Leeren der Datenbank", str(e)))
    
    def _apply_filter(self) -> None:
        """Apply filter and refresh table"""
        try:
            price_filter = self._build_price_filter()
            self._current_prices = self._price_service.get_prices_filtered(price_filter)
            self._update_table()
        except DatabaseError as e:
            self._show_error("Datenbankfehler", e)
        except Exception as e:
            self._show_error("Fehler beim Filtern", PortfolioError("Fehler beim Filtern", str(e)))
    
    def _reset_filter(self) -> None:
        """Reset filter to today's date"""
        today = date.today()
        self.filter_date_from.set_date(today)
        self.filter_date_to.set_date(today)
        self.cmb_filter_asset.current(0)
        self.cmb_filter_currency.current(0)
        self._apply_filter()
    
    def _refresh_prices(self) -> None:
        """Refresh price table"""
        self._apply_filter()
        self._check_alerts_silent()
    
    def _update_table(self) -> None:
        """Update price table with current prices"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for idx, price in enumerate(self._current_prices):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            formatted_close = self._format_price(price.close)
            change_str = price.format_change_percent()
            
            # Add color tag for positive/negative changes
            if price.change_percent is not None:
                if price.change_percent >= 0:
                    tag = (tag, 'positive')
                else:
                    tag = (tag, 'negative')
            
            self.tree.insert("", "end", values=(
                price.symbol,
                price.name,
                formatted_close,
                price.currency,
                change_str,
                price.price_date.isoformat(),
            ), tags=tag)
        
        count_text = f"Insgesamt {len(self._current_prices)} Einträge"
        if len(self._current_prices) == 0:
            count_text = "Keine Einträge gefunden"
        elif len(self._current_prices) == 1:
            count_text = "1 Eintrag"
        
        self.lbl_count.config(text=count_text)
    
    def _show_chart(self) -> None:
        """Show chart for filtered data"""
        try:
            if not self._current_prices:
                raise DataNotFoundError(
                    "Keine Daten für Diagramm",
                    "Bitte filtern Sie zuerst Kursdaten, um ein Diagramm anzuzeigen."
                )

            # Use marked symbols from table if selected, otherwise use all filtered symbols
            selected_items = self.tree.selection()
            selected_symbols = set()
            for item in selected_items:
                values = self.tree.item(item, 'values')
                if values:
                    selected_symbols.add(values[0])

            chart_prices = self._current_prices
            if selected_symbols:
                chart_prices = [price for price in self._current_prices if price.symbol in selected_symbols]

            if not chart_prices:
                raise DataNotFoundError(
                    "Keine Daten für Diagramm",
                    "Für die markierten Assets sind im gewählten Zeitraum keine Daten vorhanden."
                )

            symbol_suffix = "alle Assets"
            if selected_symbols:
                sorted_symbols = sorted(selected_symbols)
                symbol_suffix = ", ".join(sorted_symbols[:4])
                if len(sorted_symbols) > 4:
                    symbol_suffix += f" (+{len(sorted_symbols) - 4})"
            
            config = ChartConfig(
                chart_type=ChartType.LINE,
                title=(
                    f"Kursverlauf {symbol_suffix} "
                    f"({self.filter_date_from.get_date()} bis {self.filter_date_to.get_date()})"
                ),
                show_grid=True,
                show_legend=True,
                figure_size=(12, 6),
                dpi=100
            )
            
            fig = self._chart_service.create_chart(chart_prices, config)
            ChartWindow(self, fig, title="📊 Kursdiagramm")
            
        except (ChartError, DataNotFoundError) as e:
            self._show_error("Diagrammfehler", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Erstellen des Diagramms", str(e)))
    
    def _export_csv(self) -> None:
        """Export current price table data to CSV"""
        try:
            if not self._current_prices:
                raise ValidationError(
                    "Keine Daten zum Exportieren",
                    "Bitte filtern Sie zuerst Kursdaten."
                )
            
            default_filename = f"kurse_export_{date.today().isoformat()}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
                initialfile=default_filename
            )
            
            if not file_path:
                return
            
            self._price_service.export_to_csv(self._current_prices, Path(file_path))
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Erfolg",
                f"Daten erfolgreich exportiert:\n\n{file_path}\n\n{len(self._current_prices)} Einträge gespeichert."
            )
            
        except (ValidationError, ExportError) as e:
            self._show_error("Export-Fehler", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim CSV-Export", str(e)))

    # ==================== PORTFOLIO MANAGEMENT ACTIONS ====================
    
    def _on_add_transaction(self) -> None:
        """Handle add transaction button click"""
        try:
            asset = self._get_selected_portfolio_asset()
            if not asset:
                raise ValidationError(
                    "Kein Asset ausgewählt",
                    "Bitte wählen Sie ein Asset aus der Liste aus."
                )
            
            # Determine transaction type
            transaction_type_str = self.var_transaction_type.get()
            if transaction_type_str == "Kauf":
                transaction_type = TransactionType.BUY
            elif transaction_type_str == "Verkauf":
                transaction_type = TransactionType.SELL
            else:
                raise ValidationError(
                    "Ungültiger Transaktionstyp",
                    f"'{transaction_type_str}' ist kein gültiger Typ."
                )
            
            # Get values
            quantity_str = self.var_quantity.get()
            price_str = self.var_price.get()
            currency = self.var_portfolio_currency.get()
            transaction_date = self.transaction_date_entry.get_date()
            
            # Validate transaction (especially for sells)
            quantity = InputValidator.validate_quantity(quantity_str)
            self._portfolio_service.validate_transaction(asset.id, transaction_type, quantity)
            
            # Add transaction
            transaction_id = self._portfolio_service.add_transaction(
                asset_id=asset.id,
                transaction_type=transaction_type,
                quantity_str=quantity_str,
                price_str=price_str,
                currency=currency,
                transaction_date=transaction_date,
                notes=None
            )
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Erfolg",
                f"Transaktion hinzugefügt:\n\n"
                f"Typ: {transaction_type_str}\n"
                f"Asset: {asset.symbol}\n"
                f"Menge: {quantity_str}\n"
                f"Preis: {price_str} {currency}\n"
                f"Datum: {transaction_date.isoformat()}"
            )
            
            # Refresh portfolio
            self._refresh_portfolio()
            
            # Clear inputs
            self.var_quantity.set("")
            self.var_price.set("")
            self.ent_quantity.focus_set()
            
        except (ValidationError, DatabaseError) as e:
            self._show_error("Fehler beim Hinzufügen", e)
        except Exception as e:
            self._show_error("Unerwarteter Fehler", PortfolioError("Fehler beim Hinzufügen der Transaktion", str(e)))
    
    def _show_portfolio_details(self) -> None:
        """Show details for selected portfolio position"""
        selection = self.portfolio_tree.selection()
        if not selection:
            messagebox.showwarning(
                "⚠️ Keine Auswahl",
                "Bitte wählen Sie eine Position aus."
            )
            return
        
        item = selection[0]
        values = self.portfolio_tree.item(item, 'values')
        symbol = values[0]
        
        # Find asset
        asset = None
        for a in self._assets:
            if a.symbol == symbol:
                asset = a
                break
        
        if not asset:
            messagebox.showerror("Fehler", f"Asset {symbol} nicht gefunden")
            return
        
        try:
            # Get transactions for this asset
            transactions = self._portfolio_service.get_transactions_for_asset(asset.id)
            
            if not transactions:
                messagebox.showinfo(
                    f"📋 Details: {symbol}",
                    "Keine Transaktionen gefunden."
                )
                return
            
            # Build details message
            details = f"Transaktionshistorie für {symbol}:\n\n"
            
            for trans in transactions:
                typ = "Kauf" if trans.transaction_type == TransactionType.BUY else "Verkauf"
                details += (
                    f"• {trans.transaction_date.isoformat()} | "
                    f"{typ} | {trans.quantity} Stk. | "
                    f"{trans.price:.2f} {trans.currency}\n"
                )
            
            # Show in message box
            messagebox.showinfo(f"📋 Details: {symbol}", details)
            
        except DatabaseError as e:
            self._show_error("Fehler beim Laden der Details", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Anzeigen der Details", str(e)))
    
    def _clear_portfolio(self) -> None:
        """Clear all portfolio transactions with triple confirmation"""
        try:
            total_value, currency = self._portfolio_service.get_total_portfolio_value()
            position_count = len(self._current_portfolio)
        except DatabaseError as e:
            self._show_error("Fehler beim Laden der Portfolio-Daten", e)
            return
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler bei der Vorbereitung des Löschens", str(e)))
            return

        result1 = messagebox.askokcancel(
            "⚠️ ACHTUNG - Portfolio leeren",
            "Sie löschen Ihr gesamtes Portfolio!\n\n"
            "⚠️ Dies betrifft:\n"
            f"   • Positionen: {position_count}\n"
            f"   • Wert: {self._format_large_number(total_value)} {currency}\n\n"
            "ℹ️ Ein Backup wird automatisch erstellt.\n\n"
            "Möchten Sie fortfahren?",
            icon='warning'
        )
        
        if not result1:
            return

        countdown_dialog = CountdownDialog(
            self,
            title="⏳ Letzte Warnung",
            message=(
                "Sie löschen gleich Ihr gesamtes Portfolio!\n\n"
                "⚠️ Diese Aktion ist UNWIDERRUFLICH!\n\n"
                "Bitte warten Sie 5 Sekunden und überlegen Sie nochmal..."
            ),
            countdown_seconds=5,
            icon="error"
        )

        if not countdown_dialog.show():
            return

        confirm_dialog = ConfirmationDialog(
            self,
            title="🔒 Finale Bestätigung",
            message=(
                "Um das Portfolio zu leeren, tippen Sie bitte:\n\n"
                "LÖSCHEN\n\n"
                "(in Großbuchstaben)"
            ),
            required_text="LÖSCHEN"
        )

        if not confirm_dialog.show():
            messagebox.showinfo("✅ Abgebrochen", "Aktion wurde abgebrochen. Keine Daten gelöscht.")
            return
        
        try:
            backup_name = None
            if self._backup_service is not None and self._config.enable_auto_backup:
                try:
                    backup_path = self._backup_service.create_backup("portfolio_leeren")
                    backup_name = backup_path.name
                except BackupError as e:
                    if not messagebox.askyesno(
                        "⚠️ Backup fehlgeschlagen",
                        f"{e.message}\n\nTrotzdem fortfahren?"
                    ):
                        return

            deleted_count = self._portfolio_service.clear_portfolio()
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Portfolio geleert",
                (
                    f"Erfolgreich {deleted_count} Transaktionen gelöscht.\n\n"
                    f"Backup gespeichert unter:\n{backup_name}"
                ) if backup_name else (
                    f"Erfolgreich {deleted_count} Transaktionen gelöscht.\n\n"
                    "Das Portfolio wurde vollständig geleert."
                )
            )
            self._refresh_portfolio()
            
        except DatabaseError as e:
            self._show_error("Fehler beim Leeren", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Leeren des Portfolios", str(e)))
    
    def _export_portfolio(self) -> None:
        """Export portfolio to CSV"""
        try:
            default_filename = f"portfolio_export_{date.today().isoformat()}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
                initialfile=default_filename
            )
            
            if not file_path:
                return
            
            self._portfolio_service.export_portfolio_to_csv(Path(file_path))
            
            messagebox.showinfo(
                f"{EmojiIcons.CHECK} Erfolg",
                f"Portfolio erfolgreich exportiert:\n\n{file_path}"
            )
            
        except (ValidationError, DatabaseError) as e:
            self._show_error("Export-Fehler", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Portfolio-Export", str(e)))
    
    def _refresh_portfolio(self) -> None:
        """Refresh portfolio data"""
        try:
            self._current_portfolio = self._portfolio_service.get_portfolio_summary()
            self._update_portfolio_table()
            self._update_portfolio_summary()
        except DatabaseError as e:
            self._show_error("Fehler beim Laden des Portfolios", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler beim Aktualisieren des Portfolios", str(e)))
    
    def _update_portfolio_table(self) -> None:
        """Update portfolio table with current positions"""
        # Clear existing items
        for item in self.portfolio_tree.get_children():
            self.portfolio_tree.delete(item)
        
        # Populate table
        for idx, summary in enumerate(self._current_portfolio):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            
            # Add profit/loss color tag
            if summary.profit_loss >= 0:
                tag = (tag, 'profit')
            else:
                tag = (tag, 'loss')
            
            # Format with German number formatting
            quantity_str = f"{summary.quantity:.4f}".rstrip("0").rstrip(".")
            avg_price_str = self._format_price(summary.avg_buy_price)
            current_price_str = self._format_price(summary.current_price)
            value_str = self._format_large_number(summary.current_value)
            
            # Format profit/loss
            profit_loss_str = self._format_large_number(abs(summary.profit_loss))
            if summary.profit_loss < 0:
                profit_loss_str = "-" + profit_loss_str
            else:
                profit_loss_str = "+" + profit_loss_str
            
            # Format percentage
            percent_str = f"{abs(summary.profit_loss_percent):.2f}".replace(".", ",")
            if summary.profit_loss_percent >= 0:
                percent_str = "+" + percent_str + "%"
            else:
                percent_str = "-" + percent_str + "%"
            
            self.portfolio_tree.insert("", "end", values=(
                summary.symbol,
                summary.name,
                quantity_str,
                avg_price_str,
                current_price_str,
                value_str,
                profit_loss_str,
                percent_str,
            ), tags=tag)
        
        # Update count
        count_text = f"{len(self._current_portfolio)} Positionen"
        if len(self._current_portfolio) == 0:
            count_text = "Keine Positionen"
        elif len(self._current_portfolio) == 1:
            count_text = "1 Position"
        
        self.lbl_portfolio_count.config(text=count_text)
    
    def _update_portfolio_summary(self) -> None:
        """Update portfolio summary labels with proper German formatting"""
        try:
            # Get total value
            total_value, currency = self._portfolio_service.get_total_portfolio_value()
            
            # Get total profit/loss
            profit_loss, profit_loss_percent, _ = self._portfolio_service.get_total_profit_loss()
            
            # Format with German number formatting
            total_value_str = self._format_currency(total_value, currency)
            
            # Update total value label
            self.lbl_portfolio_value.config(
                text=f"Gesamtwert: {total_value_str}"
            )
            
            # Format profit/loss
            profit_loss_str = self._format_large_number(abs(profit_loss))
            if profit_loss < 0:
                profit_loss_str = "-" + profit_loss_str
            else:
                profit_loss_str = "+" + profit_loss_str
            
            # Format percentage
            percent_str = f"{abs(profit_loss_percent):.2f}".replace(".", ",")
            if profit_loss_percent >= 0:
                percent_str = "+" + percent_str
            else:
                percent_str = "-" + percent_str
            
            # Update profit/loss label
            self.lbl_portfolio_profit.config(
                text=f"Gewinn/Verlust: {profit_loss_str} {currency} ({percent_str}%)",
                foreground='#4CAF50' if profit_loss >= 0 else '#F44336'
            )
            
        except DatabaseError as e:
            self._show_error("Fehler beim Berechnen der Übersicht", e)
        except Exception as e:
            self._show_error("Fehler", PortfolioError("Fehler bei der Zusammenfassung", str(e)))


# ==================== MAIN ENTRY POINT ====================

def main():
    """Application entry point"""
    from main import main as app_main
    app_main()


if __name__ == "__main__":
    main()