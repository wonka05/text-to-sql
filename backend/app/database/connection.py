import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

load_dotenv()

REQUIRED_VARS = ["DB_NAME", "DB_USER", "DB_PASSWORD"]

missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
if missing:
    raise RuntimeError(
        f"Missing database settings in .env: {', '.join(missing)}"
    )

# URL.create escapes special characters (e.g. @ or /) in the password
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
