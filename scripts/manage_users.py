#!/usr/bin/env python3
"""
Script to manage users in the database (create, update, list).
"""
import argparse
import os
import sys
import uuid

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from api.db import get_db_session
from api.db.schema import User
from api.auth import get_password_hash

def list_users():
    db = get_db_session()
    try:
        users = db.query(User).all()
        print(f"{'Username':<20} {'Role':<10} {'Active':<10} {'ID'}")
        print("-" * 60)
        for user in users:
            print(f"{user.username:<20} {user.role:<10} {str(user.is_active):<10} {user.id}")
    finally:
        db.close()

def manage_user(username, password=None, role="user", delete=False):
    db = get_db_session()
    try:
        user = db.query(User).filter(User.username == username).first()
        
        if delete:
            if user:
                db.delete(user)
                db.commit()
                print(f"User '{username}' deleted.")
            else:
                print(f"User '{username}' not found.")
            return

        if user:
            print(f"User '{username}' exists. Updating...")
            if password:
                user.password_hash = get_password_hash(password)
            if role:
                user.role = role
            user.is_active = True
            print(f"User '{username}' updated.")
        else:
            if not password:
                print("Error: Password required for new user.")
                return
            print(f"Creating user '{username}' with role '{role}'...")
            new_user = User(
                id=uuid.uuid4(),
                username=username,
                password_hash=get_password_hash(password),
                role=role,
                is_active=True
            )
            db.add(new_user)
            print(f"User '{username}' created.")
        
        db.commit()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage users")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # List command
    list_parser = subparsers.add_parser("list", help="List all users")

    # Add/Update command
    add_parser = subparsers.add_parser("add", help="Add or update a user")
    add_parser.add_argument("username", help="Username")
    add_parser.add_argument("password", nargs="?", help="Password (required for new users)")
    add_parser.add_argument("--role", default="user", choices=["admin", "usermgt", "user"], help="User role (default: user)")

    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete a user")
    del_parser.add_argument("username", help="Username")

    args = parser.parse_args()

    if args.command == "list":
        list_users()
    elif args.command == "add":
        manage_user(args.username, args.password, args.role)
    elif args.command == "delete":
        manage_user(args.username, delete=True)
    else:
        parser.print_help()

