"""Provision or promote a user from the server's trusted CLI."""
import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import _get_session_factory, close_db
from app.models.user import User


async def manage(args):
    try:
        async with _get_session_factory()() as db:
            user = (await db.execute(select(User).where(User.username == args.username))).scalar_one_or_none()
            if user is None:
                if not args.email:
                    raise ValueError("--email is required for a new user")
                password = getpass.getpass("Password: ")
                if len(password) < 8 or len(password.encode()) > 72:
                    raise ValueError("Password must be at least 8 characters and at most 72 UTF-8 bytes")
                user = User(username=args.username, email=args.email, password_hash=hash_password(password))
                db.add(user)
            user.role = args.role
            user.department = args.department
            await db.commit()
            print(f"Configured {user.username}: {user.role}, department={user.department}")
    finally:
        await close_db()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--email")
    parser.add_argument("--role", choices=["admin", "manager", "employee"], required=True)
    parser.add_argument("--department")
    args = parser.parse_args()
    if args.role != "admin" and not args.department:
        parser.error("--department is required for manager and employee")
    asyncio.run(manage(args))


if __name__ == "__main__":
    main()
