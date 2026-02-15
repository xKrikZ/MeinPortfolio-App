"""Service for managing price alerts"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Callable

from database import PriceRepository
from models import PriceAlert, TriggeredAlert, AlertType
from exceptions import DatabaseError, ValidationError
from validators import InputValidator


class AlertService:
    """Service for price alert operations"""

    def __init__(self, db: PriceRepository):
        self._db = db
        self._notification_callback: Optional[Callable[[List[TriggeredAlert]], None]] = None

    def set_notification_callback(self, callback: Callable[[List[TriggeredAlert]], None]):
        """Set callback function for notifications."""
        self._notification_callback = callback

    def create_alert(
        self,
        asset_id: int,
        alert_type: AlertType,
        threshold_value: Decimal,
        currency: str = "EUR",
        notes: Optional[str] = None
    ) -> int:
        """Create a new price alert."""
        try:
            if asset_id <= 0:
                raise ValidationError("Ungültiges Asset", f"Asset ID {asset_id} ist ungültig")

            validated_currency = InputValidator.validate_currency(currency)

            if alert_type in [AlertType.ABOVE, AlertType.BELOW] and threshold_value <= 0:
                raise ValidationError("Ungültiger Schwellwert", "Schwellwert muss > 0 sein")

            if alert_type == AlertType.CHANGE_PERCENT and threshold_value <= 0:
                raise ValidationError("Ungültiger Prozentwert", "Prozentwert muss > 0 sein")

            with self._db.transaction():
                cursor = self._db.execute(
                    """
                    INSERT INTO price_alert
                    (asset_id, alert_type, threshold_value, currency, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (asset_id, alert_type.value, float(threshold_value), validated_currency, notes)
                )
                return cursor.lastrowid
        except ValidationError:
            raise
        except Exception as e:
            raise DatabaseError("Fehler beim Erstellen des Alarms", str(e))

    def get_active_alerts(self, asset_id: Optional[int] = None) -> List[PriceAlert]:
        """Get all active (non-triggered) alerts."""
        try:
            query = """
                SELECT id, asset_id, alert_type, threshold_value, currency,
                       active, triggered, triggered_at, notification_sent, notes, created_at
                FROM price_alert
                WHERE active = 1 AND triggered = 0
            """
            params: List = []

            if asset_id:
                query += " AND asset_id = ?"
                params.append(asset_id)

            query += " ORDER BY created_at DESC"
            rows = self._db.execute(query, tuple(params)).fetchall()
            return [self._row_to_alert(row) for row in rows]
        except Exception as e:
            raise DatabaseError("Fehler beim Laden der Alarme", str(e))

    def get_all_alerts(self, include_triggered: bool = False) -> List[PriceAlert]:
        """Get all alerts."""
        try:
            query = """
                SELECT id, asset_id, alert_type, threshold_value, currency,
                       active, triggered, triggered_at, notification_sent, notes, created_at
                FROM price_alert
                WHERE 1=1
            """

            if not include_triggered:
                query += " AND triggered = 0"

            query += " ORDER BY triggered, created_at DESC"
            rows = self._db.execute(query).fetchall()
            return [self._row_to_alert(row) for row in rows]
        except Exception as e:
            raise DatabaseError("Fehler beim Laden der Alarme", str(e))

    def delete_alert(self, alert_id: int) -> None:
        """Delete an alert."""
        try:
            with self._db.transaction():
                self._db.execute("DELETE FROM price_alert WHERE id = ?", (alert_id,))
        except Exception as e:
            raise DatabaseError("Fehler beim Löschen des Alarms", str(e))

    def deactivate_alert(self, alert_id: int) -> None:
        """Deactivate an alert without deleting."""
        try:
            with self._db.transaction():
                self._db.execute("UPDATE price_alert SET active = 0 WHERE id = ?", (alert_id,))
        except Exception as e:
            raise DatabaseError("Fehler beim Deaktivieren des Alarms", str(e))

    def check_alerts(self) -> List[TriggeredAlert]:
        """Check all active alerts against current prices."""
        try:
            triggered: List[TriggeredAlert] = []
            alerts = self.get_active_alerts()

            for alert in alerts:
                price_row = self._db.execute(
                    """
                    SELECT a.symbol, a.name, p.close
                    FROM asset a
                    LEFT JOIN (
                        SELECT p1.asset_id, p1.close
                        FROM price p1
                        INNER JOIN (
                            SELECT asset_id, MAX(price_date) AS max_date
                            FROM price
                            GROUP BY asset_id
                        ) latest ON latest.asset_id = p1.asset_id AND latest.max_date = p1.price_date
                    ) p ON a.id = p.asset_id
                    WHERE a.id = ?
                    """,
                    (alert.asset_id,)
                ).fetchone()

                if not price_row or price_row[2] is None:
                    continue

                symbol, name, current_price_raw = price_row
                current_price = Decimal(str(current_price_raw))

                is_triggered = False
                message = ""

                if alert.alert_type == AlertType.ABOVE and current_price >= alert.threshold_value:
                    is_triggered = True
                    message = (
                        f"{symbol} hat {alert.threshold_value} {alert.currency} überschritten!\n"
                        f"Aktueller Kurs: {current_price} {alert.currency}"
                    )
                elif alert.alert_type == AlertType.BELOW and current_price <= alert.threshold_value:
                    is_triggered = True
                    message = (
                        f"{symbol} ist unter {alert.threshold_value} {alert.currency} gefallen!\n"
                        f"Aktueller Kurs: {current_price} {alert.currency}"
                    )
                elif alert.alert_type == AlertType.CHANGE_PERCENT:
                    yesterday_row = self._db.execute(
                        """
                        SELECT close FROM price
                        WHERE asset_id = ? AND price_date < (
                            SELECT MAX(price_date) FROM price WHERE asset_id = ?
                        )
                        ORDER BY price_date DESC
                        LIMIT 1
                        """,
                        (alert.asset_id, alert.asset_id)
                    ).fetchone()

                    if yesterday_row:
                        yesterday_price = Decimal(str(yesterday_row[0]))
                        if yesterday_price > 0:
                            change_percent = abs(((current_price / yesterday_price) - Decimal("1")) * Decimal("100"))
                            if change_percent >= alert.threshold_value:
                                is_triggered = True
                                direction = "gestiegen" if current_price > yesterday_price else "gefallen"
                                message = (
                                    f"{symbol} ist um {change_percent:.2f}% {direction}!\n"
                                    f"Schwellwert: {alert.threshold_value}%"
                                )

                if is_triggered:
                    now_value = datetime.now().isoformat(sep=" ", timespec="seconds")
                    with self._db.transaction():
                        self._db.execute(
                            """
                            UPDATE price_alert
                            SET triggered = 1, triggered_at = ?, notification_sent = 1
                            WHERE id = ?
                            """,
                            (now_value, alert.id)
                        )

                    alert.triggered = True
                    alert.triggered_at = datetime.fromisoformat(now_value)
                    alert.notification_sent = True

                    triggered.append(
                        TriggeredAlert(
                            alert=alert,
                            symbol=symbol,
                            name=name,
                            current_price=current_price,
                            message=message,
                        )
                    )

            if triggered and self._notification_callback:
                self._notification_callback(triggered)

            return triggered
        except Exception as e:
            raise DatabaseError("Fehler beim Prüfen der Alarme", str(e))

    def _row_to_alert(self, row) -> PriceAlert:
        """Convert database row to PriceAlert."""
        return PriceAlert(
            id=row[0],
            asset_id=row[1],
            alert_type=AlertType(row[2]),
            threshold_value=Decimal(str(row[3])),
            currency=row[4],
            active=bool(row[5]),
            triggered=bool(row[6]),
            triggered_at=datetime.fromisoformat(row[7]) if row[7] else None,
            notification_sent=bool(row[8]),
            notes=row[9],
            created_at=datetime.fromisoformat(row[10]) if row[10] else None,
        )
