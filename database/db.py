import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:dev@34.11.229.123:5432/sasquatch",
)

# Cloud SQL Unix socket: set CLOUD_SQL_CONNECTION env var
# e.g. CLOUD_SQL_CONNECTION=gen-lang-client-0035403197:us-west1:sasquatch-db
_cloud_sql = os.getenv("CLOUD_SQL_CONNECTION")
if _cloud_sql:
    # Use Unix socket via Cloud SQL proxy
    engine = create_engine(
        DATABASE_URL,
        connect_args={"host": f"/cloudsql/{_cloud_sql}"},
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
