"""API layer for inventory operations."""

from app.services.inventory_service import InventoryService


def create_item(sku: str, name: str, quantity: int) -> dict:
    """Create an inventory item through the service layer."""
    service = InventoryService()
    return service.create_item(sku=sku, name=name, quantity=quantity)


def update_stock(sku: str, quantity_delta: int) -> dict:
    """Update stock quantity for an existing inventory item."""
    service = InventoryService()
    return service.update_stock(sku=sku, quantity_delta=quantity_delta)


def get_stock_status(sku: str) -> dict:
    """Return stock status and restock recommendation for an item."""
    service = InventoryService()
    return service.get_stock_status(sku=sku)
