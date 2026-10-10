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

        if "subjects" in tables:
            subj_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(subjects)"))]
            if "grade" not in subj_cols:
                conn.execute(text("ALTER TABLE subjects ADD COLUMN grade INTEGER DEFAULT 6 NOT NULL"))

        if "users" in tables:
            user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
            if "display_name" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR"))

        if "topics" in tables:
            topic_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(topics)"))]
            if "exam_task" not in topic_cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN exam_task VARCHAR"))

        if "questions" in tables:
            q_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(questions)"))]
            for col, ddl in (("exam_task", "VARCHAR"), ("exam_set", "VARCHAR"), ("extra", "TEXT")):
                if col not in q_cols:
                    conn.execute(text(f"ALTER TABLE questions ADD COLUMN {col} {ddl}"))

        conn.commit()
