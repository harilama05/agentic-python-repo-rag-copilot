"""Application entrypoint for the Inventory API sample repo."""

from app.api.inventory import create_item, get_stock_status


def create_app() -> dict:
    """Create a minimal application descriptor for the inventory service."""
    return {
        "name": "Inventory API",
        "routes": [
            "create_item",
            "get_stock_status",
        ],
    }


def health_check() -> dict:
    """Return a simple health check response."""
    return {
        "status": "ok",
        "service": "inventory_api",
    }
