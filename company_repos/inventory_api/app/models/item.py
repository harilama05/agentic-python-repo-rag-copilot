"""Inventory item model."""


class InventoryItem:
    """Simple inventory item with restock logic."""

    def __init__(self, sku: str, name: str, quantity: int, reorder_threshold: int = 10) -> None:
        """Create an inventory item."""
        self.sku = sku
        self.name = name
        self.quantity = quantity
        self.reorder_threshold = reorder_threshold

    def needs_restock(self) -> bool:
        """Return True when quantity is less than or equal to the reorder threshold."""
        return self.quantity <= self.reorder_threshold

    def to_dict(self) -> dict:
        """Serialize the item to a dictionary."""
        return {
            "sku": self.sku,
            "name": self.name,
            "quantity": self.quantity,
            "reorder_threshold": self.reorder_threshold,
        }
