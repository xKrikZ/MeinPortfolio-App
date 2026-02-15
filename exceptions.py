"""
Custom exceptions for the portfolio application
"""


class PortfolioError(Exception):
    """Base exception for all portfolio application errors"""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def get_full_message(self) -> str:
        """Get full error message including details"""
        if self.details:
            return f"{self.message}\n\nDetails: {self.details}"
        return self.message


class ValidationError(PortfolioError):
    """Exception raised for validation errors"""
    pass


class DatabaseError(PortfolioError):
    """Exception raised for database operations"""
    pass


class ExportError(PortfolioError):
    """Exception raised for export operations"""
    pass


class ChartError(PortfolioError):
    """Exception raised for chart generation errors"""
    pass


class ConfigurationError(PortfolioError):
    """Exception raised for configuration errors"""
    pass


class DataNotFoundError(PortfolioError):
    """Exception raised when required data is not found"""
    pass


class BackupError(PortfolioError):
    """Exception for backup operations"""
    pass