"""
Standard API response wrapper for consistent JSON shape.
"""

from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """Uniform API response envelope."""
    success: bool = True
    message: str = "OK"
    data: Any = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "OK") -> "ApiResponse":
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str, data: Any = None) -> "ApiResponse":
        return cls(success=False, message=message, data=data)
