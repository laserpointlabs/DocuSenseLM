
import os
import sys

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from api.db import get_db_session
from api.db.schema import User
from api.auth import get_password_hash
import uuid

def check_and_create_user():
    db = get_db_session()
    try:
        print("Checking for existing users...")
        users = db.query(User).all()
        for user in users:
            print(f"Found user: {user.username} (Role: {user.role})")
        
        target_user = "das_service"
        target_pass = "das_service_2024!"
        
        user = db.query(User).filter(User.username == target_user).first()
        if not user:
            print(f"\nUser '{target_user}' not found. Creating...")
            new_user = User(
                id=uuid.uuid4(),
                username=target_user,
                password_hash=get_password_hash(target_pass),
                role="admin", # Assuming admin role for testing
                is_active=True
            )
            db.add(new_user)
            db.commit()
            print(f"User '{target_user}' created successfully.")
        else:
            print(f"\nUser '{target_user}' already exists. Updating password...")
            user.password_hash = get_password_hash(target_pass)
            db.commit()
            print(f"Password updated for '{target_user}'.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_and_create_user()


