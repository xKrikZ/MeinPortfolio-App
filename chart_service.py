"""
Service for generating charts from price data
"""
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for embedding in Tkinter

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import date
from typing import List, Dict, Optional
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np

from models import PriceView, ChartType, ChartConfig
from exceptions import ChartError, DataNotFoundError


class ChartService:
    """Service for creating and managing charts"""
    
    def __init__(self):
        # Set default matplotlib style
        plt.style.use('seaborn-v0_8-whitegrid')
        # Set German locale for better formatting
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Segoe UI', 'Arial', 'DejaVu Sans']
    
    def validate_data(self, prices: List[PriceView]) -> None:
        """
        Validate price data for chart generation
        
        Args:
            prices: List of price views
            
        Raises:
            DataNotFoundError: If no data available
            ChartError: If data is invalid
        """
        if not prices:
            raise DataNotFoundError(
                "Keine Daten für Diagramm verfügbar",
                "Bitte wählen Sie einen Zeitraum mit vorhandenen Kursdaten."
            )
    
    def prepare_data(self, prices: List[PriceView]) -> Dict[str, Dict]:
        """
        Prepare price data for charting
        
        Args:
            prices: List of price views
            
        Returns:
            Dictionary with dates and values per symbol
            
        Raises:
            ChartError: If data preparation fails
        """
        try:
            # Group by symbol
            data_by_symbol: Dict[str, Dict] = {}
            
            for price in prices:
                if price.symbol not in data_by_symbol:
                    data_by_symbol[price.symbol] = {
                        'dates': [],
                        'values': [],
                        'name': price.name
                    }
                
                data_by_symbol[price.symbol]['dates'].append(price.price_date)
                data_by_symbol[price.symbol]['values'].append(price.close)
            
            # Sort by date for each symbol
            for symbol in data_by_symbol:
                dates = data_by_symbol[symbol]['dates']
                values = data_by_symbol[symbol]['values']
                
                # Combine, sort, and separate
                combined = sorted(zip(dates, values))
                data_by_symbol[symbol]['dates'] = [d for d, v in combined]
                data_by_symbol[symbol]['values'] = [v for d, v in combined]
            
            return data_by_symbol
            
        except Exception as e:
            raise ChartError(
                "Fehler bei der Datenaufbereitung",
                f"Technischer Fehler: {str(e)}"
            )
    
    def _get_unique_dates(self, data_by_symbol: Dict[str, Dict]) -> List[date]:
        """Get list of unique dates from all symbols"""
        all_dates = set()
        for symbol_data in data_by_symbol.values():
            all_dates.update(symbol_data['dates'])
        return sorted(list(all_dates))
    
    def create_chart(
        self,
        prices: List[PriceView],
        config: ChartConfig = None
    ) -> Figure:
        """
        Create a chart from price data
        Uses line chart for filtered time series data
        
        Args:
            prices: List of price views
            config: Chart configuration
            
        Returns:
            Matplotlib Figure object
            
        Raises:
            ChartError: If chart creation fails
        """
        if config is None:
            config = ChartConfig()
        
        try:
            # Validate data
            self.validate_data(prices)
            
            # Prepare data
            data_by_symbol = self.prepare_data(prices)
            unique_dates = self._get_unique_dates(data_by_symbol)
            
            # IMMER Zeitreihen-Diagramm für gefilterte Daten
            return self._create_time_series_chart(data_by_symbol, config)
            
        except (DataNotFoundError, ChartError):
            raise
        except Exception as e:
            raise ChartError(
                "Fehler beim Erstellen des Diagramms",
                f"Technischer Fehler: {str(e)}"
            )
    
    def _create_comparison_bar_chart(
        self,
        data_by_symbol: Dict[str, Dict],
        chart_date: date,
        config: ChartConfig
    ) -> Figure:
        """
        Create bar chart comparing asset prices on one date
        
        Args:
            data_by_symbol: Data grouped by symbol
            chart_date: The date to display
            config: Chart configuration
            
        Returns:
            Matplotlib Figure
        """
        # Create figure with better size for many assets
        fig = Figure(figsize=(14, 8), dpi=config.dpi)
        ax = fig.add_subplot(111)
        
        # Extract data for the chart
        symbols = []
        values = []
        colors = []
        
        # Color palette
        color_palette = plt.cm.tab20.colors  # 20 distinct colors
        
        for idx, (symbol, data) in enumerate(sorted(data_by_symbol.items())):
            # Get price for this date
            if chart_date in data['dates']:
                date_idx = data['dates'].index(chart_date)
                value = data['values'][date_idx]
                
                symbols.append(symbol)
                values.append(value)
                colors.append(color_palette[idx % len(color_palette)])
        
        # Create bar chart
        x_pos = np.arange(len(symbols))
        bars = ax.bar(x_pos, values, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
        
        # Customize chart
        ax.set_xlabel('Assets', fontsize=12, fontweight='bold')
        ax.set_ylabel('Kurs (EUR)', fontsize=12, fontweight='bold')
        ax.set_title(
            f'Asset-Vergleich am {chart_date.strftime("%d.%m.%Y")}',
            fontsize=14,
            fontweight='bold',
            pad=20
        )
        
        # Set x-axis
        ax.set_xticks(x_pos)
        ax.set_xticklabels(symbols, rotation=45, ha='right', fontsize=9)
        
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            if height >= 1000:
                label = f'{height:,.0f}'.replace(',', '.')
            elif height >= 10:
                label = f'{height:.1f}'.replace('.', ',')
            else:
                label = f'{height:.2f}'.replace('.', ',')
            
            ax.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                label,
                ha='center',
                va='bottom',
                fontsize=8,
                rotation=0
            )
        
        # Grid
        if config.show_grid:
            ax.grid(True, alpha=0.3, linestyle='--', axis='y')
            ax.set_axisbelow(True)
        
        # Format y-axis with German formatting
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'.replace(',', '.')))
        
        # Tight layout
        fig.tight_layout()
        
        return fig
    
    def _create_time_series_chart(
        self,
        data_by_symbol: Dict[str, Dict],
        config: ChartConfig
    ) -> Figure:
        """
        Create time series line/area chart
        
        Args:
            data_by_symbol: Data grouped by symbol
            config: Chart configuration
            
        Returns:
            Matplotlib Figure
        """
        # Create figure
        fig = Figure(figsize=config.figure_size, dpi=config.dpi)
        ax = fig.add_subplot(111)
        
        # Color palette
        color_palette = plt.cm.tab20.colors

        # Pick primary currency label from first dataset if available
        first_symbol = next(iter(data_by_symbol), None)
        y_currency = "EUR"
        if first_symbol:
            y_currency = data_by_symbol[first_symbol].get('currency', 'EUR')
        
        # Plot each symbol
        for idx, (symbol, data) in enumerate(sorted(data_by_symbol.items())):
            label = f"{symbol}"
            color = color_palette[idx % len(color_palette)]
            point_count = len(data['dates'])
            marker_style = 'o' if point_count <= 40 else None
            marker_size = 3 if point_count <= 40 else 0
            
            if config.chart_type == ChartType.LINE:
                ax.plot(
                    data['dates'],
                    data['values'],
                    marker=marker_style,
                    label=label,
                    linewidth=2.2,
                    color=color,
                    markersize=marker_size,
                    alpha=0.95
                )
            
            elif config.chart_type == ChartType.AREA:
                ax.fill_between(
                    data['dates'],
                    data['values'],
                    alpha=0.5,
                    label=label,
                    color=color
                )
                ax.plot(data['dates'], data['values'], linewidth=2, color=color)
        
        # Configure chart
        ax.set_xlabel('Datum', fontsize=11, fontweight='bold')
        ax.set_ylabel(f'Kurs ({y_currency})', fontsize=11, fontweight='bold')
        ax.set_title(config.title, fontsize=14, fontweight='bold', pad=20)
        
        if config.show_grid:
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
        
        # Legend - only if not too many items
        if config.show_legend and len(data_by_symbol) <= 15:
            ax.legend(
                loc='best',
                framealpha=0.9,
                fontsize=9,
                ncol=2 if len(data_by_symbol) > 8 else 1
            )
        
        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'.replace(',', '.')))

        # Better date axis formatting
        if len(data_by_symbol) > 0:
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        
        # Rotate date labels
        fig.autofmt_xdate(rotation=30, ha='right')
        
        # Tight layout
        fig.tight_layout()
        
        return fig
    
    def save_chart(
        self,
        fig: Figure,
        file_path: Path,
        dpi: int = 150
    ) -> None:
        """
        Save chart to file
        
        Args:
            fig: Matplotlib figure
            file_path: Path to save file
            dpi: Resolution in dots per inch
            
        Raises:
            ChartError: If saving fails
        """
        try:
            fig.savefig(file_path, dpi=dpi, bbox_inches='tight', facecolor='white')
        except Exception as e:
            raise ChartError(
                "Fehler beim Speichern des Diagramms",
                f"Datei: {file_path}\nFehler: {str(e)}"
            )


class ChartWindow(tk.Toplevel):
    """Window for displaying charts"""
    
    def __init__(
        self,
        parent: tk.Tk,
        fig: Figure,
        title: str = "Diagramm"
    ):
        super().__init__(parent)
        
        self.title(title)
        self.geometry("1400x800")
        
        # Configure window
        self.configure(bg='white')
        
        # Create toolbar frame
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # Save button
        ttk.Button(
            toolbar_frame,
            text="💾 Speichern",
            command=self._save_chart
        ).pack(side=tk.LEFT, padx=5)
        
        # Close button
        ttk.Button(
            toolbar_frame,
            text="❌ Schließen",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True,
            padx=15,
            pady=15
        )
        
        # Store figure for saving
        self.fig = fig
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (1400 // 2)
        y = (self.winfo_screenheight() // 2) - (800 // 2)
        self.geometry(f"1400x800+{x}+{y}")
    
    def _save_chart(self) -> None:
        """Save chart to file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Dateien", "*.png"),
                ("PDF Dateien", "*.pdf"),
                ("SVG Dateien", "*.svg"),
                ("Alle Dateien", "*.*")
            ],
            initialfile=f"chart_{date.today().isoformat()}.png"
        )
        
        if file_path:
            try:
                chart_service = ChartService()
                chart_service.save_chart(self.fig, Path(file_path))
                messagebox.showinfo(
                    "✅ Erfolg",
                    f"Diagramm gespeichert unter:\n{file_path}"
                )
            except ChartError as e:
                messagebox.showerror(
                    "❌ Fehler",
                    e.get_full_message()
                )