"""Input validation utilities"""

from decimal import Decimal, InvalidOperation
from datetime import date
from exceptions import ValidationError


class InputValidator:
    """Validates user input before database operations"""

    MAX_QUANTITY = Decimal("1000000000")
    MIN_QUANTITY = Decimal("0.00000001")
    MAX_PRICE = Decimal("1000000000")
    MIN_PRICE = Decimal("0.00000001")
    MAX_STRING_LENGTH = 255

    @staticmethod
    def validate_quantity(quantity_str: str) -> Decimal:
        """Validate and parse quantity"""
        if not quantity_str or not quantity_str.strip():
            raise ValidationError(
                "Menge fehlt",
                "Bitte geben Sie eine Menge ein."
            )

        clean = quantity_str.strip().replace(',', '.').replace(' ', '')

        try:
            quantity = Decimal(clean)
        except InvalidOperation:
            raise ValidationError(
                "Ungültige Menge",
                f"'{quantity_str}' ist keine gültige Zahl."
            )

        if quantity <= 0:
            raise ValidationError(
                "Menge muss positiv sein",
                f"Menge {quantity} ist nicht erlaubt. Muss > 0 sein."
            )

        if quantity < InputValidator.MIN_QUANTITY:
            raise ValidationError(
                "Menge zu klein",
                f"Minimum: {InputValidator.MIN_QUANTITY}"
            )

        if quantity > InputValidator.MAX_QUANTITY:
            raise ValidationError(
                "Menge zu groß",
                f"Maximum: {InputValidator.MAX_QUANTITY}"
            )

        return quantity

    @staticmethod
    def validate_price(price_str: str) -> Decimal:
        """Validate and parse price"""
        if not price_str or not price_str.strip():
            raise ValidationError(
                "Preis fehlt",
                "Bitte geben Sie einen Preis ein."
            )

        clean = price_str.strip().replace(',', '.').replace(' ', '')

        try:
            price = Decimal(clean)
        except InvalidOperation:
            raise ValidationError(
                "Ungültiger Preis",
                f"'{price_str}' ist keine gültige Zahl."
            )

        if price <= 0:
            raise ValidationError(
                "Preis muss positiv sein",
                f"Preis {price} ist nicht erlaubt. Muss > 0 sein."
            )

        if price < InputValidator.MIN_PRICE:
            raise ValidationError(
                "Preis zu klein",
                f"Minimum: {InputValidator.MIN_PRICE}"
            )

        if price > InputValidator.MAX_PRICE:
            raise ValidationError(
                "Preis zu groß",
                f"Maximum: {InputValidator.MAX_PRICE}"
            )

        return price

    @staticmethod
    def validate_currency(currency: str) -> str:
        """Validate currency code"""
        if not currency or not currency.strip():
            raise ValidationError(
                "Währung fehlt",
                "Bitte geben Sie eine Währung ein."
            )

        clean = currency.strip().upper()

        if len(clean) != 3:
            raise ValidationError(
                "Ungültige Währung",
                f"'{currency}' ist kein gültiger Währungscode (z.B. EUR, USD)"
            )

        if not clean.isalpha():
            raise ValidationError(
                "Ungültige Währung",
                "Währung darf nur Buchstaben enthalten."
            )

        return clean

    @staticmethod
    def validate_date(date_input: date) -> date:
        """Validate date"""
        if not date_input:
            raise ValidationError(
                "Datum fehlt",
                "Bitte wählen Sie ein Datum."
            )

        if date_input > date.today():
            raise ValidationError(
                "Datum in der Zukunft",
                f"{date_input.isoformat()} liegt in der Zukunft. "
                "Kurse/Transaktionen können nur für vergangene Daten eingetragen werden."
            )

        if date_input.year < 1970:
            raise ValidationError(
                "Datum zu weit in der Vergangenheit",
                f"{date_input.isoformat()} ist vor 1970."
            )

        return date_input

    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate asset symbol"""
        if not symbol or not symbol.strip():
            raise ValidationError(
                "Symbol fehlt",
                "Bitte geben Sie ein Symbol ein."
            )

        clean = symbol.strip().upper()

        if len(clean) > InputValidator.MAX_STRING_LENGTH:
            raise ValidationError(
                "Symbol zu lang",
                f"Maximum {InputValidator.MAX_STRING_LENGTH} Zeichen."
            )

        dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "DROP", "DELETE", "INSERT"]
        for char in dangerous_chars:
            if char in clean.upper():
                raise ValidationError(
                    "Ungültiges Symbol",
                    f"Symbol darf '{char}' nicht enthalten."
                )

        return clean
