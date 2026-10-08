# Importing every model registers its table on Base.metadata,
# which scripts/setup_db.py uses to create the schema.
from app.models.customer import Customer
from app.models.department import Department
from app.models.employee import Employee
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product

__all__ = [
    "Customer",
    "Department",
    "Employee",
    "Order",
    "OrderItem",
    "Product",
]
