

import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from models import Base

load_dotenv(find_dotenv())
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))



DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./ai_hr_saas.db"
)


if DATABASE_URL.startswith("sqlite"):
    
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )



@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()





SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_lightweight_migrations():
    
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateColumn

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                ddl = CreateColumn(column).compile(dialect=engine.dialect)
                try:
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))
                    print(f"[migration] Added column {table.name}.{column.name}")
                except Exception as e:
                    print(f"[migration] Could not add column {table.name}.{column.name}: {e}")


def init_db():
    
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    print("[OK] Database initialized successfully")


def reset_db():
    
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Database reset successfully")


if __name__ == "__main__":
    init_db()