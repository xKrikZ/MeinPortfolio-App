"""Service for managing dividends"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pathlib import Path

from database import PriceRepository
from models import Dividend, DividendSummary, DividendCalendar, DividendType
from exceptions import ValidationError, DatabaseError
from validators import InputValidator


class DividendService:
    """Service for dividend operations"""

    def __init__(self, db: PriceRepository):
        self._db = db

    def add_dividend(
        self,
        asset_id: int,
        payment_date: date,
        amount_str: str,
        currency: str,
        tax_withheld_str: str = "0",
        dividend_type: DividendType = DividendType.REGULAR,
        notes: Optional[str] = None
    ) -> int:
        """Add a dividend payment."""
        try:
            validated_date = InputValidator.validate_date(payment_date)
            validated_amount = InputValidator.validate_price(amount_str)
            validated_tax = self._parse_non_negative_amount(tax_withheld_str)
            validated_currency = InputValidator.validate_currency(currency)

            if asset_id <= 0:
                raise ValidationError("Ungültiges Asset", f"Asset ID {asset_id} ist ungültig.")

            if validated_amount <= 0:
                raise ValidationError(
                    "Ungültiger Dividendenbetrag",
                    "Dividende muss größer als 0 sein."
                )

            if validated_tax > validated_amount:
                raise ValidationError(
                    "Steuer zu hoch",
                    f"Quellensteuer ({validated_tax}) kann nicht höher als Dividende ({validated_amount}) sein."
                )

            with self._db.transaction():
                cursor = self._db.execute(
                    """
                    INSERT INTO dividend
                    (asset_id, payment_date, amount, currency, tax_withheld, dividend_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(asset_id, payment_date) DO UPDATE SET
                        amount = excluded.amount,
                        currency = excluded.currency,
                        tax_withheld = excluded.tax_withheld,
                        dividend_type = excluded.dividend_type,
                        notes = excluded.notes
                    """,
                    (
                        asset_id,
                        validated_date.isoformat(),
                        float(validated_amount),
                        validated_currency,
                        float(validated_tax),
                        dividend_type.value,
                        notes,
                    ),
                )
                return cursor.lastrowid

        except ValidationError:
            raise
        except Exception as e:
            raise DatabaseError("Fehler beim Speichern der Dividende", str(e))

    def get_dividends_for_asset(self, asset_id: int, year: Optional[int] = None) -> List[Dividend]:
        """Get all dividends for an asset."""
        try:
            if year:
                rows = self._db.execute(
                    """
                    SELECT id, asset_id, payment_date, amount, currency,
                           tax_withheld, dividend_type, notes, created_at
                    FROM dividend
                    WHERE asset_id = ? AND strftime('%Y', payment_date) = ?
                    ORDER BY payment_date DESC
                    """,
                    (asset_id, str(year)),
                ).fetchall()
            else:
                rows = self._db.execute(
                    """
                    SELECT id, asset_id, payment_date, amount, currency,
                           tax_withheld, dividend_type, notes, created_at
                    FROM dividend
                    WHERE asset_id = ?
                    ORDER BY payment_date DESC
                    """,
                    (asset_id,),
                ).fetchall()

            return [self._row_to_dividend(row) for row in rows]
        except Exception as e:
            raise DatabaseError("Fehler beim Laden der Dividenden", str(e))

    def get_dividend_summary(self, year: Optional[int] = None) -> List[DividendSummary]:
        """Get dividend summary for all assets."""
        try:
            year_filter = ""
            params: List[str] = []

            if year:
                year_filter = "AND strftime('%Y', d.payment_date) = ?"
                params.append(str(year))

            rows = self._db.execute(
                f"""
                SELECT
                    a.symbol,
                    a.name,
                    SUM(d.amount - COALESCE(d.tax_withheld, 0)) as net_dividends,
                    COUNT(d.id) as dividend_count,
                    AVG(d.amount) as avg_dividend,
                    d.currency,
                    COALESCE(
                        (SELECT SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE -quantity END)
                         FROM portfolio_transaction
                         WHERE asset_id = a.id), 0
                    ) as current_holdings,
                    a.id as asset_id
                FROM dividend d
                JOIN asset a ON a.id = d.asset_id
                WHERE 1=1 {year_filter}
                GROUP BY a.id, a.symbol, a.name, d.currency
                ORDER BY net_dividends DESC
                """,
                tuple(params),
            ).fetchall()

            summaries: List[DividendSummary] = []
            for row in rows:
                annual_yield = None
                try:
                    price_row = self._db.execute(
                        """
                        SELECT close FROM price
                        WHERE asset_id = ?
                        ORDER BY price_date DESC LIMIT 1
                        """,
                        (row[7],),
                    ).fetchone()

                    if price_row and row[6] > 0:
                        current_price = Decimal(str(price_row[0]))
                        total_value = current_price * Decimal(str(row[6]))
                        if total_value > 0:
                            annual_yield = (Decimal(str(row[2])) / total_value) * Decimal("100")
                except Exception:
                    annual_yield = None

                summaries.append(
                    DividendSummary(
                        symbol=row[0],
                        name=row[1],
                        total_dividends=Decimal(str(row[2] or 0)),
                        dividend_count=int(row[3] or 0),
                        average_dividend=Decimal(str(row[4] or 0)),
                        currency=row[5],
                        current_holdings=Decimal(str(row[6] or 0)),
                        annual_yield=annual_yield,
                    )
                )

            return summaries
        except Exception as e:
            raise DatabaseError("Fehler beim Berechnen der Dividenden-Zusammenfassung", str(e))

    def get_total_dividends(self, year: Optional[int] = None, currency: str = "EUR") -> Decimal:
        """Get total dividends received."""
        try:
            validated_currency = InputValidator.validate_currency(currency)
            year_filter = ""
            params: List[str] = [validated_currency]

            if year:
                year_filter = "AND strftime('%Y', payment_date) = ?"
                params.append(str(year))

            result = self._db.execute(
                f"""
                SELECT COALESCE(SUM(amount - COALESCE(tax_withheld, 0)), 0)
                FROM dividend
                WHERE currency = ? {year_filter}
                """,
                tuple(params),
            ).fetchone()

            return Decimal(str(result[0] if result else 0))
        except ValidationError:
            raise
        except Exception as e:
            raise DatabaseError("Fehler beim Berechnen der Gesamt-Dividenden", str(e))

    def get_dividend_calendar(self, days_ahead: int = 90) -> List[DividendCalendar]:
        """Get upcoming dividends (projection based on past payments)."""
        return []

    def delete_dividend(self, dividend_id: int) -> None:
        """Delete a dividend payment."""
        try:
            with self._db.transaction():
                self._db.execute("DELETE FROM dividend WHERE id = ?", (dividend_id,))
        except Exception as e:
            raise DatabaseError("Fehler beim Löschen der Dividende", str(e))

    def export_dividends_csv(self, file_path: Path, year: Optional[int] = None) -> None:
        """Export dividends to CSV."""
        import csv

        try:
            year_filter = ""
            params: List[str] = []
            if year:
                year_filter = "WHERE strftime('%Y', d.payment_date) = ?"
                params.append(str(year))

            rows = self._db.execute(
                f"""
                SELECT
                    a.symbol,
                    a.name,
                    d.payment_date,
                    d.amount,
                    COALESCE(d.tax_withheld, 0),
                    d.amount - COALESCE(d.tax_withheld, 0) as net_amount,
                    d.currency,
                    d.dividend_type,
                    COALESCE(d.notes, '')
                FROM dividend d
                JOIN asset a ON a.id = d.asset_id
                {year_filter}
                ORDER BY d.payment_date DESC
                """,
                tuple(params),
            ).fetchall()

            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow([
                    "Symbol", "Name", "Datum", "Brutto", "Steuer", "Netto", "Währung", "Typ", "Notizen"
                ])
                writer.writerows(rows)
        except Exception as e:
            raise DatabaseError("Fehler beim CSV-Export", str(e))

    def _row_to_dividend(self, row) -> Dividend:
        return Dividend(
            id=row[0],
            asset_id=row[1],
            payment_date=date.fromisoformat(row[2]),
            amount=Decimal(str(row[3])),
            currency=row[4],
            tax_withheld=Decimal(str(row[5] or 0)),
            dividend_type=DividendType(row[6]),
            notes=row[7],
            created_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    @staticmethod
    def _parse_non_negative_amount(value: str) -> Decimal:
        clean = (value or "").strip()
        if clean == "":
            return Decimal("0")

        normalized = clean.replace(",", ".").replace(" ", "")
        try:
            parsed = Decimal(normalized)
        except Exception as exc:
            raise ValidationError("Ungültige Steuer", f"'{value}' ist keine gültige Zahl.") from exc

        if parsed < 0:
            raise ValidationError("Ungültige Steuer", "Steuer darf nicht negativ sein.")

        return parsed
