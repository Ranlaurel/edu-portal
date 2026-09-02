"""Create an additional portal user without storing the password in the repo."""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models import User


def main():
    parser = argparse.ArgumentParser(description="Add an Edu Portal user")
    parser.add_argument("username")
    parser.add_argument("--password")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password must not be empty")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(User).filter_by(username=args.username).first():
            raise SystemExit(f"User already exists: {args.username}")
        db.add(User(username=args.username, password_hash=hash_password(password)))
        db.commit()
    print(f"Created user: {args.username}")


if __name__ == "__main__":
    main()
