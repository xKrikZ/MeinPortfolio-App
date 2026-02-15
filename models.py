from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List
from enum import Enum
from pathlib import Path
from decimal import Decimal

@dataclass
class Asset:
    """Domain model for an asset"""
    id: int
    symbol: str
    name: str
    active: bool = True
    
    def display_name(self) -> str:
        """Returns formatted display name"""
        return f"{self.symbol}  {self.name}"


@dataclass
class Price:
    """Domain model for a price entry"""
    asset_id: int
    price_date: date
    close: float
    currency: str
    source: str
    
    def format_close(self) -> str:
        """Format close price for display"""
        return f"{self.close:.6f}".rstrip("0").rstrip(".")


@dataclass
class PriceView:
    """View model for displaying price with asset info"""
    symbol: str
    name: str
    close: float
    currency: str
    source: str
    price_date: date
    change_percent: Optional[float] = None  # NEU: Prozentuale Änderung
    
    def format_close(self) -> str:
        """Format close price for display"""
        return f"{self.close:.6f}".rstrip("0").rstrip(".")
    
    def format_change_percent(self) -> str:
        """Format percentage change"""
        if self.change_percent is None:
            return "—"
        
        sign = "+" if self.change_percent >= 0 else ""
        return f"{sign}{self.change_percent:.2f}%"
    
    def to_csv_row(self) -> list:
        """Convert to CSV row"""
        return [
            self.symbol,
            self.name,
            self.format_close(),
            self.currency,
            self.format_change_percent(),
            self.price_date.isoformat(),
        ]


@dataclass
class PriceFilter:
    """Filter criteria for price queries"""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    asset_id: Optional[int] = None
    symbol: Optional[str] = None
    currency: Optional[str] = None
    
    def has_filters(self) -> bool:
        """Check if any filter is set"""
        return any([
            self.date_from is not None,
            self.date_to is not None,
            self.asset_id is not None,
            self.symbol is not None,
            self.currency is not None,
        ])


class ChartType(Enum):
    """Chart types available for visualization"""
    LINE = "line"
    BAR = "bar"
    AREA = "area"


@dataclass
class ChartConfig:
    """Configuration for chart generation"""
    chart_type: ChartType = ChartType.LINE
    title: str = "Kursverlauf"
    show_grid: bool = True
    show_legend: bool = True
    figure_size: tuple = (12, 6)
    dpi: int = 100
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.dpi < 50 or self.dpi > 300:
            raise ValueError("DPI must be between 50 and 300")
        
        if self.figure_size[0] < 4 or self.figure_size[1] < 3:
            raise ValueError("Figure size must be at least 4x3")


# NEU: Portfolio-Management Models

class TransactionType(Enum):
    """Transaction types"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class PortfolioPosition:
    """Portfolio position (holdings)"""
    id: Optional[int]
    asset_id: int
    symbol: str
    name: str
    quantity: float
    average_buy_price: float
    currency: str
    first_buy_date: date
    last_transaction_date: date
    
    def calculate_current_value(self, current_price: float) -> float:
        """Calculate current market value"""
        return self.quantity * current_price
    
    def calculate_total_cost(self) -> float:
        """Calculate total investment cost"""
        return self.quantity * self.average_buy_price
    
    def calculate_profit_loss(self, current_price: float) -> float:
        """Calculate profit/loss"""
        return self.calculate_current_value(current_price) - self.calculate_total_cost()
    
    def calculate_profit_loss_percent(self, current_price: float) -> float:
        """Calculate profit/loss percentage"""
        total_cost = self.calculate_total_cost()
        if total_cost == 0:
            return 0.0
        return ((current_price - self.average_buy_price) / self.average_buy_price) * 100


@dataclass
class Transaction:
    """Single portfolio transaction"""
    id: Optional[int]
    asset_id: int
    transaction_type: TransactionType
    quantity: float
    price: float
    currency: str
    transaction_date: date
    notes: Optional[str] = None


@dataclass
class PortfolioSummary:
    """Portfolio summary view"""
    symbol: str
    name: str
    quantity: float
    avg_buy_price: float
    current_price: float
    currency: str
    current_value: float
    total_cost: float
    profit_loss: float
    profit_loss_percent: float
    last_update: date
    
    def format_profit_loss(self) -> str:
        """Format profit/loss with sign"""
        sign = "+" if self.profit_loss >= 0 else ""
        return f"{sign}{self.profit_loss:,.2f}"
    
    def format_profit_loss_percent(self) -> str:
        """Format profit/loss percentage"""
        sign = "+" if self.profit_loss_percent >= 0 else ""
        return f"{sign}{self.profit_loss_percent:.2f}%"


@dataclass
class BackupInfo:
    """Information about a backup file"""
    file_path: Path
    file_name: str
    size_bytes: int
    created_date: datetime
    is_monthly: bool
    action_name: Optional[str] = None


class DividendType(Enum):
    """Types of dividend payments"""
    REGULAR = "regular"
    SPECIAL = "special"
    CAPITAL_RETURN = "capital_return"


@dataclass
class Dividend:
    """Represents a dividend payment"""
    id: Optional[int]
    asset_id: int
    payment_date: date
    amount: Decimal
    currency: str
    tax_withheld: Decimal = Decimal("0")
    dividend_type: DividendType = DividendType.REGULAR
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class DividendSummary:
    """Summary of dividends for an asset"""
    symbol: str
    name: str
    total_dividends: Decimal
    dividend_count: int
    average_dividend: Decimal
    currency: str
    current_holdings: Decimal
    annual_yield: Optional[Decimal] = None


@dataclass
class DividendCalendar:
    """Dividend calendar entry"""
    symbol: str
    name: str
    payment_date: date
    amount: Decimal
    currency: str
    dividend_type: DividendType


class AlertType(Enum):
    """Types of price alerts"""
    ABOVE = "above"
    BELOW = "below"
    CHANGE_PERCENT = "change_percent"


@dataclass
class PriceAlert:
    """Price alert configuration"""
    id: Optional[int]
    asset_id: int
    alert_type: AlertType
    threshold_value: Decimal
    currency: str = "EUR"
    active: bool = True
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    notification_sent: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class TriggeredAlert:
    """Triggered alert with asset information"""
    alert: PriceAlert
    symbol: str
    name: str
    current_price: Decimal
    message: str