import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import DATABASE_URL
from core.utils import logger

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not initialize pgvector extension: {e}")

    try:
        from models.models import Base
        from sqlalchemy.schema import CreateColumn
        inspector = inspect(engine)
        missing_tables = [t for t in Base.metadata.tables if not inspector.has_table(t)]
        if missing_tables:
            tables = [Base.metadata.tables[t] for t in missing_tables]
            Base.metadata.create_all(bind=engine, tables=tables)
            logger.info(f"Initialized missing database tables: {missing_tables}")

        with engine.begin() as conn:
            for table_name, table in Base.metadata.tables.items():
                if inspector.has_table(table_name):
                    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                    for col in table.columns:
                        if col.name not in existing_cols:
                            ddl = CreateColumn(col).compile(dialect=engine.dialect)
                            try:
                                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {ddl}"))
                                logger.info(f"[migration] added missing column {table_name}.{col.name}")
                            except Exception as ex:
                                logger.warning(f"[migration] failed to add {table_name}.{col.name}: {ex}")
    except Exception as e:
        logger.warning(f"Could not auto-sync schema: {e}")

    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        logger.warning("No alembic_version table found. Run `alembic upgrade head` before serving traffic.")
    else:
        logger.info("PostgreSQL database connected")


def db_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    init_db()
