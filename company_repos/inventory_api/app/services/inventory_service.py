"""Business logic for inventory operations."""

from app.models.item import InventoryItem


class InventoryService:
    """Service object that manages in-memory inventory records."""

    def __init__(self) -> None:
        """Initialize the service with an empty item store."""
        self.items: dict[str, InventoryItem] = {}

    def create_item(self, sku: str, name: str, quantity: int) -> dict:
        """Create and store a new inventory item."""
        item = InventoryItem(sku=sku, name=name, quantity=quantity)
        self.items[sku] = item

        return item.to_dict()

    def update_stock(self, sku: str, quantity_delta: int) -> dict:
        """Update item quantity by applying a positive or negative delta."""
        item = self.items.get(sku)

        if item is None:
            raise ValueError(f"Unknown SKU: {sku}")

        item.quantity += quantity_delta
        return item.to_dict()

    def get_stock_status(self, sku: str) -> dict:
        """Return current stock information and whether restocking is needed."""
        item = self.items.get(sku)

        if item is None:
            raise ValueError(f"Unknown SKU: {sku}")

        return {
            "sku": item.sku,
            "name": item.name,
            "quantity": item.quantity,
            "needs_restock": item.needs_restock(),
        }
