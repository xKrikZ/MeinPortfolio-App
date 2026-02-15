import csv
from datetime import date
from pathlib import Path
from typing import List

from models import Asset, Price, PriceView, PriceFilter
from database import PriceRepository
from config import AppConfig, Constants
from exceptions import ValidationError, ExportError, DatabaseError
from validators import InputValidator


class PriceService:
    """Business logic for price management"""
    
    def __init__(self, repository: PriceRepository, config: AppConfig):
        self._repository = repository
        self._config = config
    
    def get_active_assets(self) -> List[Asset]:
        """Get all active assets"""
        try:
            return self._repository.get_active_assets()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Unerwarteter Fehler beim Laden der Assets",
                str(e)
            )
    
    def get_currencies(self) -> List[str]:
        """Get all distinct currencies"""
        try:
            return self._repository.get_distinct_currencies()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Unerwarteter Fehler beim Laden der Währungen",
                str(e)
            )
    
    def save_price(
        self,
        asset_id: int,
        price_date: date,
        close_str: str,
        currency: str,
    ) -> None:
        """Validate and save a price entry"""
        try:
            validated_date = InputValidator.validate_date(price_date)
            validated_price = InputValidator.validate_price(close_str)
            validated_currency = InputValidator.validate_currency(
                currency.strip() or self._config.default_currency
            )

            if asset_id <= 0:
                raise ValidationError(
                    "Ungültiges Asset",
                    f"Asset ID {asset_id} ist ungültig."
                )
            
            price = Price(
                asset_id=asset_id,
                price_date=validated_date,
                close=float(validated_price),
                currency=validated_currency,
                source=Constants.SOURCE_MANUAL_GUI,
            )
            
            self._repository.save_price(price)
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            raise ValidationError(
                "Fehler beim Validieren der Kursdaten",
                str(e)
            )
    
    def delete_price(self, symbol: str, price_date: date) -> None:
        """
        Delete a specific price entry
        
        Args:
            symbol: Asset symbol
            price_date: Price date
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            validated_symbol = InputValidator.validate_symbol(symbol)
            validated_date = InputValidator.validate_date(price_date)
            self._repository.delete_price(validated_symbol, validated_date)
        except DatabaseError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Löschen des Eintrags",
                f"Symbol: {symbol}, Datum: {price_date}\nFehler: {str(e)}"
            )
    
    def clear_all_prices(self) -> int:
        """
        Delete all price entries
        
        Returns:
            Number of deleted entries
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            return self._repository.clear_all_prices()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Leeren der Datenbank",
                str(e)
            )
    
    def get_prices_for_date(self, price_date: date) -> List[PriceView]:
        """Get all prices for a specific date"""
        try:
            return self._repository.get_prices_by_date(price_date)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Laden der Kurse für Datum",
                f"Datum: {price_date}\nFehler: {str(e)}"
            )
    
    def get_prices_filtered(self, price_filter: PriceFilter) -> List[PriceView]:
        """Get prices with filter criteria"""
        try:
            return self._repository.get_prices_filtered(price_filter)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Fehler beim Filtern der Kurse",
                str(e)
            )
    
    def export_to_csv(self, prices: List[PriceView], file_path: Path) -> None:
        """Export prices to CSV file"""
        if not prices:
            raise ValidationError(
                "Keine Daten zum Exportieren",
                "Bitte wählen Sie einen Zeitraum mit Kursdaten aus."
            )
        
        try:
            with open(file_path, 'w', newline='', encoding=Constants.CSV_ENCODING) as f:
                writer = csv.writer(f, delimiter=Constants.CSV_DELIMITER)
                
                # Write header
                writer.writerow(['Symbol', 'Name', 'Close', 'Currency', 'Source', 'Datum'])
                
                # Write data (new order!)
                for price in prices:
                    writer.writerow([
                        price.symbol,
                        price.name,
                        price.format_close(),
                        price.currency,
                        price.source,
                        price.price_date.isoformat(),
                    ])
                    
        except PermissionError:
            raise ExportError(
                "Zugriff verweigert",
                f"Die Datei '{file_path}' ist möglicherweise geöffnet oder schreibgeschützt."
            )
        except IOError as e:
            raise ExportError(
                "Fehler beim Schreiben der CSV-Datei",
                f"Datei: {file_path}\nFehler: {str(e)}"
            )
        except Exception as e:
            raise ExportError(
                "Unerwarteter Fehler beim CSV-Export",
                str(e)
            )
    
    @staticmethod
    def _parse_close(close_str: str) -> float:
        """Parse close price from string"""
        value = close_str.strip().replace(",", ".")
        
        if not value:
            raise ValidationError(
                "Schlusskurs ist leer",
                "Bitte geben Sie einen gültigen Schlusskurs ein."
            )
        
        try:
            parsed_value = float(value)
            
            if parsed_value <= 0:
                raise ValidationError(
                    "Ungültiger Schlusskurs",
                    f"Der Schlusskurs muss größer als 0 sein (eingegeben: {parsed_value})."
                )
            
            if parsed_value > 1000000000:
                raise ValidationError(
                    "Schlusskurs zu hoch",
                    f"Der Schlusskurs scheint unrealistisch hoch: {parsed_value}"
                )
            
            return parsed_value
            
        except ValueError:
            raise ValidationError(
                "Ungültiges Zahlenformat",
                f"'{close_str}' ist kein gültiger Schlusskurs. Bitte verwenden Sie das Format: 123.45"
            )
    
    @staticmethod
    def validate_date(date_str: str) -> date:
        """Validate and parse date string"""
        date_str = date_str.strip()
        
        if len(date_str) != Constants.DATE_LENGTH or date_str[4] != "-" or date_str[7] != "-":
            raise ValidationError(
                "Ungültiges Datumsformat",
                f"Datum muss im Format YYYY-MM-DD sein (z.B. 2026-02-14).\nEingegeben: '{date_str}'"
            )
        
        try:
            parsed_date = date.fromisoformat(date_str)
            
            if parsed_date > date.today().replace(year=date.today().year + 10):
                raise ValidationError(
                    "Datum liegt zu weit in der Zukunft",
                    f"Das eingegebene Datum ({parsed_date}) liegt mehr als 10 Jahre in der Zukunft."
                )
            
            if parsed_date < date(1900, 1, 1):
                raise ValidationError(
                    "Datum liegt zu weit in der Vergangenheit",
                    f"Das eingegebene Datum ({parsed_date}) liegt vor 1900."
                )
            
            return parsed_date
            
        except ValueError as e:
            raise ValidationError(
                "Ungültiges Datum",
                f"'{date_str}' ist kein gültiges Datum.\nFehler: {str(e)}"
            )