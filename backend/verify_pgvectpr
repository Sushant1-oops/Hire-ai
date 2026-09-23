
from core.database import engine
from sqlalchemy import text

queries = {
    "embedding_column": """
        SELECT
            column_name,
            data_type,
            udt_name,
            format_type(a.atttypid, a.atttypmod) AS actual_type
        FROM information_schema.columns c
        JOIN pg_attribute a
            ON a.attrelid = c.table_name::regclass
           AND a.attname = c.column_name
        WHERE c.table_name = 'resume_chunks'
          AND c.column_name = 'embedding';
    """,

    "indexes": """
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'resume_chunks';
    """,

    "vector_extension": """
        SELECT
            extname,
            extversion,
            extnamespace::regnamespace AS schema_name
        FROM pg_extension
        WHERE extname = 'vector';
    """
}

with engine.connect() as conn:
    for name, query in queries.items():
        print(f"\n===== {name.upper()} =====")
        rows = conn.execute(text(query)).fetchall()

        if rows:
            for row in rows:
                print(row)
        else:
            print("No result")
