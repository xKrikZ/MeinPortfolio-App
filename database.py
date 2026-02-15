import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from datetime import date, timedelta
from contextlib import contextmanager

from models import (
    Asset, Price, PriceView, PriceFilter,
    PortfolioPosition, Transaction, TransactionType, PortfolioSummary
)
from exceptions import DatabaseError, DataNotFoundError


class PriceRepository:
    """Repository for price and asset data access"""
    
    def __init__(self, db_path: Path):
        if not db_path.exists():
            raise DatabaseError(
                "Datenbank nicht gefunden",
                f"Pfad: {db_path}"
            )
        
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
    
    def connect(self) -> None:
        """Establish database connection"""
        try:
            self._connection = sqlite3.connect(self._db_path)
            self._enable_foreign_keys()
            self._create_portfolio_tables()
        except sqlite3.Error as e:
            raise DatabaseError(
                "Verbindung zur Datenbank fehlgeschlagen",
                f"Datenbankpfad: {self._db_path}\nFehler: {str(e)}"
            )

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL query on the active connection."""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")

        try:
            return self._connection.execute(query, params)
        except sqlite3.Error as e:
            raise DatabaseError("SQL-Ausführung fehlgeschlagen", str(e))

    def _enable_foreign_keys(self) -> None:
        """Enable foreign key constraints"""
        self.execute("PRAGMA foreign_keys = ON")

        result = self.execute("PRAGMA foreign_keys").fetchone()
        if not result or result[0] != 1:
            raise DatabaseError(
                "Foreign Keys konnten nicht aktiviert werden",
                "Kritischer Datenbank-Fehler beim Initialisieren"
            )
    
    def _create_portfolio_tables(self) -> None:
        """Create portfolio tables if they don't exist"""
        try:
            # Portfolio transactions table
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_transaction (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    price REAL NOT NULL CHECK(price > 0),
                    currency TEXT NOT NULL CHECK(length(currency) = 3),
                    transaction_date TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES asset(id)
                )
            """)
            
            # Index for faster queries
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_asset_date 
                ON portfolio_transaction(asset_id, transaction_date)
            """)

            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS dividend (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    payment_date TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    currency TEXT NOT NULL DEFAULT 'EUR' CHECK(length(currency) = 3),
                    tax_withheld REAL DEFAULT 0 CHECK(tax_withheld >= 0),
                    dividend_type TEXT DEFAULT 'regular' CHECK(dividend_type IN ('regular', 'special', 'capital_return')),
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE,
                    UNIQUE(asset_id, payment_date)
                )
            """)

            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_dividend_asset
                ON dividend(asset_id)
            """)

            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_dividend_date
                ON dividend(payment_date)
            """)

            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS price_alert (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL CHECK(alert_type IN ('above', 'below', 'change_percent')),
                    threshold_value REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'EUR' CHECK(length(currency) = 3),
                    active INTEGER DEFAULT 1,
                    triggered INTEGER DEFAULT 0,
                    triggered_at TEXT,
                    notification_sent INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE
                )
            """)

            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_alert_asset
                ON price_alert(asset_id)
            """)

            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_alert_active
                ON price_alert(active, triggered)
            """)
            
            self._connection.commit()
        except sqlite3.Error as e:
            raise DatabaseError(
                "Fehler beim Erstellen der Portfolio-Tabellen",
                str(e)
            )
    
    def close(self) -> None:
        """Close database connection"""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
            except sqlite3.Error as e:
                raise DatabaseError(
                    "Fehler beim Schließen der Datenbankverbindung",
                    str(e)
                )
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        if not self._connection:
            raise DatabaseError(
                "Keine aktive Datenbankverbindung",
                "Bitte rufen Sie connect() auf."
            )
        
        try:
            self.begin_transaction()
            yield
            self.commit_transaction()
        except Exception as e:
            self.rollback_transaction()
            raise DatabaseError(
                "Transaktion fehlgeschlagen",
                f"Änderungen wurden rückgängig gemacht. Fehler: {str(e)}"
            )

    def begin_transaction(self) -> None:
        """Start a new transaction"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        self._connection.execute("BEGIN")

    def commit_transaction(self) -> None:
        """Commit current transaction"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        self._connection.commit()

    def rollback_transaction(self) -> None:
        """Rollback current transaction"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        self._connection.rollback()

    def check_integrity(self) -> bool:
        """Check database integrity"""
        try:
            result = self.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise DatabaseError(
                    "Datenbank-Korruption erkannt!",
                    f"Integrity Check Ergebnis: {result[0] if result else 'unbekannt'}\n\n"
                    "Bitte Backup wiederherstellen!"
                )

            return True
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Integritäts-Check fehlgeschlagen",
                str(e)
            )

    def check_foreign_keys(self) -> List[str]:
        """Check for foreign key violations"""
        violations: List[str] = []

        result = self.execute("""
            SELECT pt.id, pt.asset_id
            FROM portfolio_transaction pt
            LEFT JOIN asset a ON pt.asset_id = a.id
            WHERE a.id IS NULL
        """).fetchall()

        for row in result:
            violations.append(
                f"portfolio_transaction.id={row[0]} verweist auf "
                f"nicht existierendes asset.id={row[1]}"
            )

        result = self.execute("""
            SELECT p.asset_id, p.price_date
            FROM price p
            LEFT JOIN asset a ON p.asset_id = a.id
            WHERE a.id IS NULL
        """).fetchall()

        for row in result:
            violations.append(
                f"price für asset.id={row[0]} am {row[1]} verweist auf "
                f"nicht existierendes Asset"
            )

        result = self.execute("""
            SELECT d.id, d.asset_id, d.payment_date
            FROM dividend d
            LEFT JOIN asset a ON d.asset_id = a.id
            WHERE a.id IS NULL
        """).fetchall()

        for row in result:
            violations.append(
                f"dividend.id={row[0]} (asset.id={row[1]}, {row[2]}) verweist auf "
                f"nicht existierendes Asset"
            )

        result = self.execute("""
            SELECT pa.id, pa.asset_id
            FROM price_alert pa
            LEFT JOIN asset a ON pa.asset_id = a.id
            WHERE a.id IS NULL
        """).fetchall()

        for row in result:
            violations.append(
                f"price_alert.id={row[0]} verweist auf nicht existierendes asset.id={row[1]}"
            )

        return violations

    def cleanup_orphaned_data(self) -> Dict[str, int]:
        """Remove orphaned data (foreign key violations)."""
        deleted: Dict[str, int] = {}

        with self.transaction():
            result = self.execute("""
                DELETE FROM portfolio_transaction
                WHERE asset_id NOT IN (SELECT id FROM asset)
            """)
            deleted['portfolio_transaction'] = result.rowcount

            result = self.execute("""
                DELETE FROM price
                WHERE asset_id NOT IN (SELECT id FROM asset)
            """)
            deleted['price'] = result.rowcount

            result = self.execute("""
                DELETE FROM dividend
                WHERE asset_id NOT IN (SELECT id FROM asset)
            """)
            deleted['dividend'] = result.rowcount

            result = self.execute("""
                DELETE FROM price_alert
                WHERE asset_id NOT IN (SELECT id FROM asset)
            """)
            deleted['price_alert'] = result.rowcount

        return deleted
    
    # ==================== PRICE MANAGEMENT ====================
    
    def get_active_assets(self) -> List[Asset]:
        """Retrieve all active assets"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = """
                SELECT id, symbol, name, active
                FROM asset
                WHERE active = 1
                ORDER BY symbol
            """
            rows = self._connection.execute(query).fetchall()
            
            return [
                Asset(id=row[0], symbol=row[1], name=row[2], active=bool(row[3]))
                for row in rows
            ]
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden der Assets", f"SQL-Fehler: {str(e)}")
    
    def save_price(self, price: Price) -> None:
        """Insert or update a price entry"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")

        if price.asset_id <= 0:
            raise DatabaseError("Ungültiges Asset", f"Asset ID {price.asset_id} ist ungültig.")
        if price.close <= 0:
            raise DatabaseError("Ungültiger Kurs", "Kurs muss größer als 0 sein.")
        if not price.currency or len(price.currency.strip()) != 3:
            raise DatabaseError("Ungültige Währung", "Währung muss genau 3 Buchstaben haben.")
        
        query = """
            INSERT INTO price (asset_id, price_date, close, currency, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id, price_date) DO UPDATE SET
                close = excluded.close,
                currency = excluded.currency,
                source = excluded.source
        """
        
        try:
            with self.transaction():
                self._connection.execute(
                    query,
                    (price.asset_id, price.price_date.isoformat(), 
                     price.close, price.currency, price.source)
                )
        except DatabaseError:
            raise
    
    def delete_price(self, symbol: str, price_date: date) -> None:
        """Delete a specific price entry"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            with self.transaction():
                asset_query = "SELECT id FROM asset WHERE symbol = ?"
                result = self._connection.execute(asset_query, (symbol,)).fetchone()
                
                if not result:
                    raise DatabaseError("Asset nicht gefunden", f"Symbol: {symbol}")
                
                asset_id = result[0]
                delete_query = "DELETE FROM price WHERE asset_id = ? AND price_date = ?"
                cursor = self._connection.execute(delete_query, (asset_id, price_date.isoformat()))
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        "Eintrag nicht gefunden",
                        f"Kein Eintrag für {symbol} am {price_date.isoformat()}"
                    )
        except DatabaseError:
            raise
    
    def clear_all_prices(self) -> int:
        """Delete all price entries"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            with self.transaction():
                cursor = self._connection.execute("DELETE FROM price")
                return cursor.rowcount
        except Exception as e:
            raise DatabaseError("Fehler beim Leeren der Datenbank", str(e))
    
    def _calculate_price_changes(self, prices: List[PriceView]) -> List[PriceView]:
        """Calculate percentage changes for price list"""
        if not prices:
            return prices
        
        # Group by symbol
        by_symbol: Dict[str, List[PriceView]] = {}
        for price in prices:
            if price.symbol not in by_symbol:
                by_symbol[price.symbol] = []
            by_symbol[price.symbol].append(price)
        
        # Sort by date and calculate changes
        for symbol in by_symbol:
            symbol_prices = sorted(by_symbol[symbol], key=lambda p: p.price_date)
            
            for i, price in enumerate(symbol_prices):
                if i == 0:
                    price.change_percent = None
                else:
                    prev_price = symbol_prices[i - 1]
                    if prev_price.close > 0:
                        change = ((price.close - prev_price.close) / prev_price.close) * 100
                        price.change_percent = change
                    else:
                        price.change_percent = None
        
        return prices
    
    def get_prices_filtered(self, price_filter: PriceFilter) -> List[PriceView]:
        """Retrieve prices with filter criteria and calculate changes"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query_parts = ["""
                SELECT a.symbol, a.name, p.close, p.currency, COALESCE(p.source, ''), p.price_date
                FROM price p
                JOIN asset a ON a.id = p.asset_id
                WHERE 1=1
            """]
            
            params: List = []
            
            if price_filter.date_from:
                query_parts.append("AND p.price_date >= ?")
                params.append(price_filter.date_from.isoformat())
            
            if price_filter.date_to:
                query_parts.append("AND p.price_date <= ?")
                params.append(price_filter.date_to.isoformat())
            
            if price_filter.asset_id:
                query_parts.append("AND a.id = ?")
                params.append(price_filter.asset_id)
            
            if price_filter.symbol:
                query_parts.append("AND a.symbol LIKE ?")
                params.append(f"%{price_filter.symbol}%")
            
            if price_filter.currency:
                query_parts.append("AND p.currency = ?")
                params.append(price_filter.currency)
            
            query_parts.append("ORDER BY a.symbol, p.price_date")
            
            query = "\n".join(query_parts)
            rows = self._connection.execute(query, params).fetchall()
            
            prices = [
                PriceView(
                    symbol=row[0], name=row[1], close=float(row[2]),
                    currency=row[3], source=row[4],
                    price_date=date.fromisoformat(row[5])
                )
                for row in rows
            ]
            
            # Calculate percentage changes
            return self._calculate_price_changes(prices)
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Filtern der Kurse", f"SQL-Fehler: {str(e)}")
    
    def get_distinct_currencies(self) -> List[str]:
        """Get list of all currencies"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = "SELECT DISTINCT currency FROM price ORDER BY currency"
            rows = self._connection.execute(query).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden der Währungen", f"SQL-Fehler: {str(e)}")
    
    # ==================== PORTFOLIO MANAGEMENT ====================
    
    def save_transaction(self, transaction: Transaction) -> int:
        """Save a portfolio transaction"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")

        if transaction.asset_id <= 0:
            raise DatabaseError("Ungültiges Asset", f"Asset ID {transaction.asset_id} ist ungültig.")
        if transaction.quantity <= 0:
            raise DatabaseError("Ungültige Menge", "Menge muss größer als 0 sein.")
        if transaction.price <= 0:
            raise DatabaseError("Ungültiger Preis", "Preis muss größer als 0 sein.")
        if not transaction.currency or len(transaction.currency.strip()) != 3:
            raise DatabaseError("Ungültige Währung", "Währung muss genau 3 Buchstaben haben.")
        
        try:
            with self.transaction():
                query = """
                    INSERT INTO portfolio_transaction 
                    (asset_id, transaction_type, quantity, price, currency, transaction_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                cursor = self._connection.execute(
                    query,
                    (
                        transaction.asset_id,
                        transaction.transaction_type.value,
                        transaction.quantity,
                        transaction.price,
                        transaction.currency,
                        transaction.transaction_date.isoformat(),
                        transaction.notes
                    )
                )
                return cursor.lastrowid
        except Exception as e:
            raise DatabaseError("Fehler beim Speichern der Transaktion", str(e))
    
    def get_portfolio_positions(self) -> List[PortfolioPosition]:
        """Get all current portfolio positions"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = """
                SELECT 
                    a.id,
                    a.symbol,
                    a.name,
                    SUM(CASE 
                        WHEN pt.transaction_type = 'buy' THEN pt.quantity 
                        WHEN pt.transaction_type = 'sell' THEN -pt.quantity 
                    END) as total_quantity,
                    SUM(CASE 
                        WHEN pt.transaction_type = 'buy' THEN pt.quantity * pt.price 
                        WHEN pt.transaction_type = 'sell' THEN -pt.quantity * pt.price 
                    END) / NULLIF(SUM(CASE 
                        WHEN pt.transaction_type = 'buy' THEN pt.quantity 
                        WHEN pt.transaction_type = 'sell' THEN -pt.quantity 
                    END), 0) as avg_price,
                    pt.currency,
                    MIN(pt.transaction_date) as first_buy_date,
                    MAX(pt.transaction_date) as last_transaction_date
                FROM portfolio_transaction pt
                JOIN asset a ON a.id = pt.asset_id
                GROUP BY a.id, a.symbol, a.name, pt.currency
                HAVING total_quantity > 0
                ORDER BY a.symbol
            """
            
            rows = self._connection.execute(query).fetchall()
            
            positions = []
            for row in rows:
                positions.append(PortfolioPosition(
                    id=row[0],
                    asset_id=row[0],
                    symbol=row[1],
                    name=row[2],
                    quantity=float(row[3]),
                    average_buy_price=float(row[4]) if row[4] else 0.0,
                    currency=row[5],
                    first_buy_date=date.fromisoformat(row[6]),
                    last_transaction_date=date.fromisoformat(row[7])
                ))
            
            return positions
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden der Portfolio-Positionen", f"SQL-Fehler: {str(e)}")
    
    def get_portfolio_summary(self) -> List[PortfolioSummary]:
        """Get portfolio summary with current prices and profit/loss"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            positions = self.get_portfolio_positions()
            summaries = []
            
            for pos in positions:
                # Get latest price for this asset
                price_query = """
                    SELECT close, price_date
                    FROM price
                    WHERE asset_id = ?
                    ORDER BY price_date DESC
                    LIMIT 1
                """
                price_row = self._connection.execute(price_query, (pos.asset_id,)).fetchone()
                
                if price_row:
                    current_price = float(price_row[0])
                    last_update = date.fromisoformat(price_row[1])
                else:
                    current_price = 0.0
                    last_update = date.today()
                
                current_value = pos.calculate_current_value(current_price)
                total_cost = pos.calculate_total_cost()
                profit_loss = pos.calculate_profit_loss(current_price)
                profit_loss_percent = pos.calculate_profit_loss_percent(current_price)
                
                summaries.append(PortfolioSummary(
                    symbol=pos.symbol,
                    name=pos.name,
                    quantity=pos.quantity,
                    avg_buy_price=pos.average_buy_price,
                    current_price=current_price,
                    currency=pos.currency,
                    current_value=current_value,
                    total_cost=total_cost,
                    profit_loss=profit_loss,
                    profit_loss_percent=profit_loss_percent,
                    last_update=last_update
                ))
            
            return summaries
            
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError("Fehler beim Erstellen der Portfolio-Übersicht", str(e))
    
    def get_transactions_for_asset(self, asset_id: int) -> List[Transaction]:
        """Get all transactions for a specific asset"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = """
                SELECT id, asset_id, transaction_type, quantity, price, 
                       currency, transaction_date, notes
                FROM portfolio_transaction
                WHERE asset_id = ?
                ORDER BY transaction_date DESC
            """
            
            rows = self._connection.execute(query, (asset_id,)).fetchall()
            
            transactions = []
            for row in rows:
                transactions.append(Transaction(
                    id=row[0],
                    asset_id=row[1],
                    transaction_type=TransactionType(row[2]),
                    quantity=float(row[3]),
                    price=float(row[4]),
                    currency=row[5],
                    transaction_date=date.fromisoformat(row[6]),
                    notes=row[7]
                ))
            
            return transactions
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden der Transaktionen", f"SQL-Fehler: {str(e)}")
    
    def get_all_transactions(self) -> List[Transaction]:
        """Get all portfolio transactions"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = """
                SELECT id, asset_id, transaction_type, quantity, price, 
                       currency, transaction_date, notes
                FROM portfolio_transaction
                ORDER BY transaction_date DESC
            """
            
            rows = self._connection.execute(query).fetchall()
            
            transactions = []
            for row in rows:
                transactions.append(Transaction(
                    id=row[0],
                    asset_id=row[1],
                    transaction_type=TransactionType(row[2]),
                    quantity=float(row[3]),
                    price=float(row[4]),
                    currency=row[5],
                    transaction_date=date.fromisoformat(row[6]),
                    notes=row[7]
                ))
            
            return transactions
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden aller Transaktionen", f"SQL-Fehler: {str(e)}")
    
    def delete_transaction(self, transaction_id: int) -> None:
        """Delete a portfolio transaction"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            with self.transaction():
                query = "DELETE FROM portfolio_transaction WHERE id = ?"
                cursor = self._connection.execute(query, (transaction_id,))
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        "Transaktion nicht gefunden",
                        f"Keine Transaktion mit ID {transaction_id}"
                    )
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError("Fehler beim Löschen der Transaktion", str(e))
    
    def clear_portfolio(self) -> int:
        """Delete all portfolio transactions"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            with self.transaction():
                cursor = self._connection.execute("DELETE FROM portfolio_transaction")
                return cursor.rowcount
        except Exception as e:
            raise DatabaseError("Fehler beim Leeren des Portfolios", str(e))
    
    def get_portfolio_value_history(
        self, 
        start_date: date, 
        end_date: date
    ) -> List[Tuple[date, float]]:
        """Get portfolio value history over time"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            positions = self.get_portfolio_positions()
            if not positions:
                return []
            
            date_query = """
                SELECT DISTINCT price_date
                FROM price
                WHERE price_date BETWEEN ? AND ?
                ORDER BY price_date
            """
            
            date_rows = self._connection.execute(
                date_query,
                (start_date.isoformat(), end_date.isoformat())
            ).fetchall()
            
            value_history = []
            
            for date_row in date_rows:
                current_date = date.fromisoformat(date_row[0])
                total_value = 0.0
                
                for pos in positions:
                    price_query = """
                        SELECT close
                        FROM price
                        WHERE asset_id = ? AND price_date <= ?
                        ORDER BY price_date DESC
                        LIMIT 1
                    """
                    price_row = self._connection.execute(
                        price_query,
                        (pos.asset_id, current_date.isoformat())
                    ).fetchone()
                    
                    if price_row:
                        price = float(price_row[0])
                        total_value += pos.quantity * price
                
                value_history.append((current_date, total_value))
            
            return value_history
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden der Portfolio-Wertentwicklung", f"SQL-Fehler: {str(e)}")
    
    def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """Get asset by symbol"""
        if not self._connection:
            raise DatabaseError("Keine aktive Datenbankverbindung")
        
        try:
            query = """
                SELECT id, symbol, name, active
                FROM asset
                WHERE symbol = ?
            """
            row = self._connection.execute(query, (symbol,)).fetchone()
            
            if row:
                return Asset(
                    id=row[0],
                    symbol=row[1],
                    name=row[2],
                    active=bool(row[3])
                )
            return None
            
        except sqlite3.Error as e:
            raise DatabaseError("Fehler beim Laden des Assets", f"SQL-Fehler: {str(e)}")