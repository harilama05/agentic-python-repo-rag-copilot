import hashlib
import re
from typing import List


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_email(email: str) -> bool:
    """Validate an email address format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def paginate(items: List, page: int = 1, per_page: int = 10) -> List:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end]