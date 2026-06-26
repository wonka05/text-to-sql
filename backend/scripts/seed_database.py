import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from sqlalchemy import text
from app.database.connection import engine

fake = Faker("en_IN")

with engine.begin() as conn:

    # Insert employees
    for _ in range(100):
        conn.execute(
            text("""
            INSERT INTO employees
            (first_name, last_name, email, phone, salary, hire_date, department_id)
            VALUES
            (:first_name, :last_name, :email, :phone, :salary, :hire_date, :department_id)
            """),
            {
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.unique.email(),
                "phone": fake.phone_number()[:20],
                "salary": random.randint(30000, 150000),
                "hire_date": fake.date_between(start_date="-5y", end_date="today"),
                "department_id": random.randint(1, 8),
            },
        )

print("100 employees inserted successfully!")