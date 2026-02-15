"""
Service layer for portfolio management
"""
from datetime import date
from typing import List, Optional, Tuple
from pathlib import Path
from decimal import Decimal

from models import (
    Asset, Transaction, TransactionType,
    PortfolioPosition, PortfolioSummary
)
from database import PriceRepository
from config import AppConfig
from exceptions import ValidationError, DatabaseError
from validators import InputValidator


class PortfolioService:
    """Business logic for portfolio management"""
    
    def __init__(self, repository: PriceRepository, config: AppConfig):
        self._repository = repository
        self._config = config
    
    def add_transaction(
        self,
        asset_id: int,
        transaction_type: TransactionType,
        quantity_str: str,
        price_str: str,
        currency: str,
        transaction_date: date,
        notes: Optional[str] = None
    ) -> int:
        """
        Add a new portfolio transaction
        
        Args:
            asset_id: Asset ID
            transaction_type: Buy or Sell
            quantity_str: Quantity as string
            price_str: Price as string
            currency: Currency code
            transaction_date: Transaction date
            notes: Optional notes
            
        Returns:
            Transaction ID
            
        Raises:
            ValidationError: If validation fails
            DatabaseError: If save fails
        """
        try:
            if asset_id <= 0:
                raise ValidationError(
                    "Ungültiges Asset",
                    f"Asset ID {asset_id} ist ungültig."
                )

            validated_quantity = InputValidator.validate_quantity(quantity_str)
            validated_price = InputValidator.validate_price(price_str)
            validated_currency = InputValidator.validate_currency(
                currency.strip() or self._config.default_currency
            )
            validated_date = InputValidator.validate_date(transaction_date)

            # Validate business logic before database operation
            self.validate_transaction(asset_id, transaction_type, validated_quantity)
            
            # Create transaction
            transaction = Transaction(
                id=None,
                asset_id=asset_id,
                transaction_type=transaction_type,
                quantity=float(validated_quantity),
                price=float(validated_price),
                currency=validated_currency,
                transaction_date=validated_date,
                notes=notes
            )
            
            # Save to database
            return self._repository.save_transaction(transaction)
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            raise ValidationError(
                "Fehler beim Erstellen der Transaktion",
                str(e)
            )
    
    def get_portfolio_positions(self) -> List[PortfolioPosition]:
        """
        Get all current portfolio positions
        
        Returns:
            List of portfolio positions
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            return self._repository.get_portfolio_positions()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Laden der Positionen",
                str(e)
            )
    
    def get_portfolio_summary(self) -> List[PortfolioSummary]:
        """
        Get portfolio summary with current values and profit/loss
        
        Returns:
            List of portfolio summaries
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            return self._repository.get_portfolio_summary()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Erstellen der Portfolio-Übersicht",
                str(e)
            )
    
    def get_total_portfolio_value(self) -> Tuple[float, str]:
        """
        Calculate total portfolio value
        
        Returns:
            Tuple of (total_value, currency)
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            summaries = self.get_portfolio_summary()
            
            if not summaries:
                return (0.0, self._config.default_currency)
            
            # Group by currency
            totals_by_currency = {}
            for summary in summaries:
                if summary.currency not in totals_by_currency:
                    totals_by_currency[summary.currency] = 0.0
                totals_by_currency[summary.currency] += summary.current_value
            
            # For simplicity, return the first currency total
            # In production, you might want currency conversion
            if totals_by_currency:
                first_currency = list(totals_by_currency.keys())[0]
                return (totals_by_currency[first_currency], first_currency)
            
            return (0.0, self._config.default_currency)
            
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Berechnen des Portfoliowertes",
                str(e)
            )
    
    def get_total_profit_loss(self) -> Tuple[float, float, str]:
        """
        Calculate total profit/loss for portfolio
        
        Returns:
            Tuple of (profit_loss_amount, profit_loss_percent, currency)
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            summaries = self.get_portfolio_summary()
            
            if not summaries:
                return (0.0, 0.0, self._config.default_currency)
            
            # Group by currency
            by_currency = {}
            for summary in summaries:
                if summary.currency not in by_currency:
                    by_currency[summary.currency] = {
                        'profit_loss': 0.0,
                        'total_cost': 0.0,
                        'current_value': 0.0
                    }
                
                by_currency[summary.currency]['profit_loss'] += summary.profit_loss
                by_currency[summary.currency]['total_cost'] += summary.total_cost
                by_currency[summary.currency]['current_value'] += summary.current_value
            
            # Return first currency
            if by_currency:
                first_currency = list(by_currency.keys())[0]
                data = by_currency[first_currency]
                
                profit_loss = data['profit_loss']
                total_cost = data['total_cost']
                
                if total_cost > 0:
                    profit_loss_percent = (profit_loss / total_cost) * 100
                else:
                    profit_loss_percent = 0.0
                
                return (profit_loss, profit_loss_percent, first_currency)
            
            return (0.0, 0.0, self._config.default_currency)
            
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Berechnen des Gewinns/Verlusts",
                str(e)
            )
    
    def get_transactions_for_asset(self, asset_id: int) -> List[Transaction]:
        """
        Get all transactions for a specific asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            List of transactions
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            return self._repository.get_transactions_for_asset(asset_id)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Laden der Transaktionen",
                str(e)
            )
    
    def get_all_transactions(self) -> List[Transaction]:
        """
        Get all portfolio transactions
        
        Returns:
            List of all transactions
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            return self._repository.get_all_transactions()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Laden aller Transaktionen",
                str(e)
            )
    
    def delete_transaction(self, transaction_id: int) -> None:
        """
        Delete a portfolio transaction
        
        Args:
            transaction_id: Transaction ID
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            self._repository.delete_transaction(transaction_id)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Löschen der Transaktion",
                str(e)
            )
    
    def clear_portfolio(self) -> int:
        """
        Delete all portfolio transactions
        
        Returns:
            Number of deleted transactions
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            return self._repository.clear_portfolio()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Leeren des Portfolios",
                str(e)
            )
    
    def get_portfolio_value_history(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, float]]:
        """
        Get portfolio value development over time
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of (date, value) tuples
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            return self._repository.get_portfolio_value_history(start_date, end_date)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Laden der Wertentwicklung",
                str(e)
            )
    
    def validate_transaction(
        self,
        asset_id: int,
        transaction_type: TransactionType,
        quantity: Decimal
    ) -> None:
        """
        Validate if a transaction is possible
        
        Args:
            asset_id: Asset ID
            transaction_type: Buy or Sell
            quantity: Quantity to trade
            
        Raises:
            ValidationError: If transaction is not valid
        """
        if transaction_type == TransactionType.SELL:
            # Check if we have enough quantity to sell
            current_quantity = self.get_asset_quantity(asset_id)

            if current_quantity == Decimal("0"):
                raise ValidationError(
                    "Keine Position vorhanden",
                    "Sie besitzen dieses Asset nicht und können es daher nicht verkaufen."
                )

            if quantity > current_quantity:
                raise ValidationError(
                    "Verkaufsmenge zu groß",
                    f"Sie besitzen nur {current_quantity} Stück, "
                    f"können aber nicht {quantity} verkaufen.\n\n"
                    f"Maximal verkaufbar: {current_quantity}"
                )

    def get_asset_quantity(self, asset_id: int) -> Decimal:
        """Get current quantity for a specific asset in portfolio."""
        positions = self.get_portfolio_positions()
        for pos in positions:
            if pos.asset_id == asset_id:
                return Decimal(str(pos.quantity))
        return Decimal("0")
    
    def export_portfolio_to_csv(self, file_path: Path) -> None:
        """
        Export portfolio summary to CSV
        
        Args:
            file_path: Path to CSV file
            
        Raises:
            ValidationError: If no data to export
            DatabaseError: If export fails
        """
        import csv
        from config import Constants
        
        try:
            summaries = self.get_portfolio_summary()
            
            if not summaries:
                raise ValidationError(
                    "Kein Portfolio vorhanden",
                    "Es gibt keine Portfolio-Positionen zum Exportieren."
                )
            
            with open(file_path, 'w', newline='', encoding=Constants.CSV_ENCODING) as f:
                writer = csv.writer(f, delimiter=Constants.CSV_DELIMITER)
                
                # Write header
                writer.writerow([
                    'Symbol',
                    'Name',
                    'Menge',
                    'Ø Kaufpreis',
                    'Aktueller Kurs',
                    'Währung',
                    'Aktueller Wert',
                    'Gesamtkosten',
                    'Gewinn/Verlust',
                    'Gewinn/Verlust %',
                    'Letztes Update'
                ])
                
                # Write data
                for summary in summaries:
                    writer.writerow([
                        summary.symbol,
                        summary.name,
                        f"{summary.quantity:.6f}".rstrip("0").rstrip("."),
                        f"{summary.avg_buy_price:.2f}",
                        f"{summary.current_price:.2f}",
                        summary.currency,
                        f"{summary.current_value:.2f}",
                        f"{summary.total_cost:.2f}",
                        summary.format_profit_loss(),
                        summary.format_profit_loss_percent(),
                        summary.last_update.isoformat()
                    ])
                    
        except ValidationError:
            raise
        except PermissionError:
            raise DatabaseError(
                "Zugriff verweigert",
                f"Die Datei '{file_path}' ist möglicherweise geöffnet oder schreibgeschützt."
            )
        except IOError as e:
            raise DatabaseError(
                "Fehler beim Schreiben der CSV-Datei",
                f"Datei: {file_path}\nFehler: {str(e)}"
            )
        except Exception as e:
            raise DatabaseError(
                "Unerwarteter Fehler beim Portfolio-Export",
                str(e)
            )