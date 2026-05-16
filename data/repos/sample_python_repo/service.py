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