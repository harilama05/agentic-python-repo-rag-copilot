from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Represents a user in the system."""
    id: int
    name: str
    email: str
    is_active: bool = True


@dataclass
class Product:
    """Represents a product in the catalog."""
    id: int
    name: str
    price: float
    description: Optional[str] = None