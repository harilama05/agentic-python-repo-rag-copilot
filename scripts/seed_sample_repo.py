"""Seed a sample Python repo for testing."""

from pathlib import Path

SAMPLE_REPO_DIR = Path("data/repos/sample_python_repo")


def create_sample_repo():
    SAMPLE_REPO_DIR.mkdir(parents=True, exist_ok=True)

    # models.py
    (SAMPLE_REPO_DIR / "models.py").write_text('''
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
'''.strip(), encoding="utf-8")

    # service.py
    (SAMPLE_REPO_DIR / "service.py").write_text('''
from typing import List, Optional
from models import User, Product


class UserService:
    """Service for managing users."""

    def __init__(self):
        self._users: List[User] = []

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user_id = len(self._users) + 1
        user = User(id=user_id, name=name, email=email)
        self._users.append(user)
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        for user in self._users:
            if user.id == user_id:
                return user
        return None

    def list_users(self) -> List[User]:
        """List all active users."""
        return [u for u in self._users if u.is_active]

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user."""
        user = self.get_user(user_id)
        if user:
            user.is_active = False
            return True
        return False


class ProductService:
    """Service for managing products."""

    def __init__(self):
        self._products: List[Product] = []

    def add_product(self, name: str, price: float, description: str = None) -> Product:
        """Add a new product."""
        product_id = len(self._products) + 1
        product = Product(id=product_id, name=name, price=price, description=description)
        self._products.append(product)
        return product

    def search_products(self, query: str) -> List[Product]:
        """Search products by name."""
        query_lower = query.lower()
        return [p for p in self._products if query_lower in p.name.lower()]
'''.strip(), encoding="utf-8")

    # utils.py
    (SAMPLE_REPO_DIR / "utils.py").write_text('''
import hashlib
import re
from typing import List


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_email(email: str) -> bool:
    """Validate an email address format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def paginate(items: List, page: int = 1, per_page: int = 10) -> List:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end]
'''.strip(), encoding="utf-8")

    print(f"[OK] Sample repo created at: {SAMPLE_REPO_DIR}")


if __name__ == "__main__":
    create_sample_repo()
