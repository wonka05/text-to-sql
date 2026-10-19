"""Create the database, its tables, sample data and the app's read-only user.

Uses the admin account from backend/.env (DB_ADMIN_USER / DB_ADMIN_PASSWORD).
Run from the backend/ folder:

    python -m scripts.setup_db            # create what's missing, fill empty tables
    python -m scripts.setup_db --reset    # drop all tables and rebuild with fresh data
"""
import argparse
import random
import re
import sys
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import create_engine, func, select, text

from app.core.config import get_settings
from app.database.base import Base
from app.database.connection import database_url
from app.models import Customer, Department, Employee, Order, OrderItem, Product

# A fixed seed makes every run produce identical data, so answers to
# benchmark questions stay the same across machines and resets.
SEED = 42

EMPLOYEE_COUNT = 100
CUSTOMER_COUNT = 200
ORDER_COUNT = 600
DATA_END = date(2026, 9, 30)

# (name, min salary, max salary, hiring weight)
DEPARTMENTS = [
    ("Engineering", 70000, 180000, 25),
    ("Human Resources", 40000, 90000, 6),
    ("Finance", 55000, 130000, 10),
    ("Marketing", 45000, 110000, 12),
    ("Sales", 40000, 120000, 18),
    ("Operations", 40000, 95000, 12),
    ("IT Support", 35000, 80000, 9),
    ("Research", 65000, 160000, 8),
]

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
]

# (name, category, price)
PRODUCTS = [
    ("Wireless Mouse", "Electronics", "799.00"),
    ("Mechanical Keyboard", "Electronics", "3499.00"),
    ("27-inch Monitor", "Electronics", "15999.00"),
    ("USB-C Hub", "Electronics", "1899.00"),
    ("Noise Cancelling Headphones", "Electronics", "8999.00"),
    ("Bluetooth Speaker", "Electronics", "2499.00"),
    ("HD Webcam", "Electronics", "2199.00"),
    ("1TB External SSD", "Electronics", "6499.00"),
    ("Ergonomic Office Chair", "Furniture", "12499.00"),
    ("Standing Desk", "Furniture", "21999.00"),
    ("Bookshelf", "Furniture", "5999.00"),
    ("Filing Cabinet", "Furniture", "7499.00"),
    ("LED Desk Lamp", "Furniture", "1299.00"),
    ("A5 Notebook (Pack of 5)", "Stationery", "349.00"),
    ("Gel Pens (Pack of 10)", "Stationery", "199.00"),
    ("Sticky Notes", "Stationery", "149.00"),
    ("Whiteboard Markers", "Stationery", "249.00"),
    ("Stapler", "Stationery", "299.00"),
    ("Cotton T-Shirt", "Clothing", "599.00"),
    ("Denim Jacket", "Clothing", "2499.00"),
    ("Running Shoes", "Clothing", "3999.00"),
    ("Formal Shirt", "Clothing", "1499.00"),
    ("Hoodie", "Clothing", "1799.00"),
    ("Yoga Mat", "Sports", "899.00"),
    ("Dumbbell Set", "Sports", "3299.00"),
    ("Cricket Bat", "Sports", "2799.00"),
    ("Football", "Sports", "999.00"),
    ("Badminton Racket", "Sports", "1599.00"),
    ("Coffee Maker", "Home & Kitchen", "4499.00"),
    ("Electric Kettle", "Home & Kitchen", "1399.00"),
    ("Non-stick Frying Pan", "Home & Kitchen", "1199.00"),
    ("Steel Water Bottle", "Home & Kitchen", "499.00"),
    ("Insulated Lunch Box", "Home & Kitchen", "899.00"),
]


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def make_email(first: str, last: str, number: int, domain: str) -> str:
    # .example is a reserved domain, so these can never be real addresses
    def clean(part: str) -> str:
        return re.sub(r"[^a-z]", "", part.lower())

    return f"{clean(first)}.{clean(last)}{number}@{domain}"


def make_phone(rng: random.Random) -> str:
    return f"+91 {rng.randint(70000, 99999)}{rng.randint(10000, 99999)}"


def build_rows() -> list[tuple[type, list[dict]]]:
    """Generate all sample rows, in the order they must be inserted."""
    rng = random.Random(SEED)
    fake = Faker("en_IN")
    fake.seed_instance(SEED)

    departments = [
        {"department_id": i, "department_name": name}
        for i, (name, _, _, _) in enumerate(DEPARTMENTS, start=1)
    ]

    employees = []
    weights = [weight for _, _, _, weight in DEPARTMENTS]
    for employee_id in range(1, EMPLOYEE_COUNT + 1):
        index = rng.choices(range(len(DEPARTMENTS)), weights=weights)[0]
        _, low, high, _ = DEPARTMENTS[index]
        first, last = fake.first_name(), fake.last_name()
        employees.append({
            "employee_id": employee_id,
            "first_name": first,
            "last_name": last,
            "email": make_email(first, last, employee_id, "company.example"),
            "phone": make_phone(rng),
            "salary": Decimal(rng.randrange(low, high + 1, 500)),
            "hire_date": random_date(rng, date(2018, 1, 1), date(2025, 12, 31)),
            "department_id": index + 1,
        })

    customers = []
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        first, last = fake.first_name(), fake.last_name()
        customers.append({
            "customer_id": customer_id,
            "customer_name": f"{first} {last}",
            "email": make_email(first, last, customer_id, "mail.example"),
            "city": rng.choice(CITIES),
            "phone": make_phone(rng),
            "join_date": random_date(rng, date(2022, 1, 1), date(2026, 6, 30)),
        })

    products = []
    for product_id, (name, category, price) in enumerate(PRODUCTS, start=1):
        # About 1 in 5 products is low on stock
        low_stock = rng.random() < 0.2
        products.append({
            "product_id": product_id,
            "product_name": name,
            "category": category,
            "price": Decimal(price),
            "stock_quantity": rng.randint(0, 9) if low_stock else rng.randint(20, 250),
        })

    orders, order_items = [], []
    for order_id in range(1, ORDER_COUNT + 1):
        customer = rng.choice(customers)
        total = Decimal("0.00")

        for product in rng.sample(products, k=rng.randint(1, 4)):
            quantity = rng.choices([1, 2, 3, 4, 5], weights=[50, 25, 12, 8, 5])[0]
            order_items.append({
                "order_item_id": len(order_items) + 1,
                "order_id": order_id,
                "product_id": product["product_id"],
                "quantity": quantity,
                "unit_price": product["price"],
            })
            total += product["price"] * quantity

        orders.append({
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "order_date": random_date(rng, customer["join_date"], DATA_END),
            "total_amount": total,
        })

    return [
        (Department, departments),
        (Employee, employees),
        (Customer, customers),
        (Product, products),
        (Order, orders),
        (OrderItem, order_items),
    ]


def create_read_only_user(engine, database: str, user: str, password: str) -> None:
    """Create (or update) an account with SELECT access to one database only."""
    if len(password) < 12:
        sys.exit("DB_PASSWORD must be at least 12 characters for the app's user.")

    account = {"user": user, "host": "%", "password": password}
    with engine.begin() as conn:
        conn.execute(
            text("CREATE USER IF NOT EXISTS :user@:host IDENTIFIED BY :password"),
            account,
        )
        conn.execute(text("ALTER USER :user@:host IDENTIFIED BY :password"), account)
        # Start from zero privileges, then allow reading this one database only
        conn.execute(text("REVOKE ALL PRIVILEGES, GRANT OPTION FROM :user@:host"), account)
        conn.execute(text(f"GRANT SELECT ON `{database}`.* TO :user@:host"), account)


def create_tables_and_data(engine, reset: bool = False) -> dict[str, int]:
    """Create missing tables and fill them if they are all empty.

    Returns the row count of each table afterwards.
    """
    if reset:
        Base.metadata.drop_all(engine)
        print("Dropped all tables.")
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        tables = Base.metadata.sorted_tables
        has_data = any(
            conn.execute(select(func.count()).select_from(table)).scalar()
            for table in tables
        )

        if has_data:
            print("Tables already contain data, so no sample data was added.")
            print("Run with --reset to rebuild everything with fresh sample data.")
        else:
            for model, rows in build_rows():
                conn.execute(model.__table__.insert(), rows)

        return {
            table.name: conn.execute(select(func.count()).select_from(table)).scalar()
            for table in tables
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop all tables and rebuild them with fresh sample data",
    )
    args = parser.parse_args()
    settings = get_settings()

    if not settings.db_admin_user or not settings.db_admin_password:
        sys.exit("Set DB_ADMIN_USER and DB_ADMIN_PASSWORD in backend/.env first.")

    # The name goes into SQL as an identifier, so allow only safe characters
    if not re.fullmatch(r"\w+", settings.db_name):
        sys.exit("DB_NAME may only contain letters, numbers and underscores.")

    admin = (settings.db_admin_user, settings.db_admin_password)

    server = create_engine(database_url(settings, *admin, database=None))
    with server.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}`"))
    server.dispose()

    engine = create_engine(database_url(settings, *admin, database=settings.db_name))
    for table, count in create_tables_and_data(engine, reset=args.reset).items():
        print(f"  {table:<12} {count} rows")

    if settings.db_user == settings.db_admin_user:
        print(
            "WARNING: DB_USER is the admin account, so the app is NOT read-only.\n"
            "         Set DB_USER/DB_PASSWORD to a separate user and run this again."
        )
    else:
        create_read_only_user(engine, settings.db_name, settings.db_user, settings.db_password)
        print(
            f"Read-only user '{settings.db_user}' can SELECT from '{settings.db_name}' only."
        )
    engine.dispose()


if __name__ == "__main__":
    main()
