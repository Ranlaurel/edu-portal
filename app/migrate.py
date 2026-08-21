"""Lightweight, idempotent schema migrations for the SQLite DB.

No Alembic here on purpose -- this is a single-file personal app. Runs at
startup, safe to call every time: only adds columns that don't already
exist, never touches existing data.
"""
from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
        if "user_progress" not in tables:
            return  # fresh DB, create_all() already made the table with all columns

        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user_progress)"))]
        if "interval_stage" not in cols:
            conn.execute(text("ALTER TABLE user_progress ADD COLUMN interval_stage INTEGER DEFAULT 0"))
        if "next_review_at" not in cols:
            conn.execute(text("ALTER TABLE user_progress ADD COLUMN next_review_at DATE"))
        if "wrong_question_ids" not in cols:
            conn.execute(text("ALTER TABLE user_progress ADD COLUMN wrong_question_ids VARCHAR"))
        conn.commit()
