#!/usr/bin/env python3
"""
Script to create initial admin and usermgt users in the database.
Run this after setting up the database schema.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session, init_db
from api.db.schema import User
from api.auth import get_password_hash

def create_users():
    """Create admin and usermgt users if they don't exist"""
    # Initialize database tables
    init_db()
    
    db = get_db_session()
    try:
        # Create admin user
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_password = "Admin2024!Secure"
            admin_user = User(
                username="admin",
                password_hash=get_password_hash(admin_password),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            print(f"✓ Created admin user (username: admin, password: {admin_password})")
        else:
            print("ℹ Admin user already exists")
        
        # Create usermgt user
        usermgt_user = db.query(User).filter(User.username == "usermgt").first()
        if not usermgt_user:
            usermgt_password = "UserMgt2024!Secure"
            usermgt_user = User(
                username="usermgt",
                password_hash=get_password_hash(usermgt_password),
                role="usermgt",
                is_active=True
            )
            db.add(usermgt_user)
            print(f"✓ Created usermgt user (username: usermgt, password: {usermgt_password})")
        else:
            print("ℹ Usermgt user already exists")
        
        db.commit()
        print("\n✅ User creation complete!")
        print("\nDefault credentials:")
        print("  Admin: username=admin, password=Admin2024!Secure")
        print("  UserMgt: username=usermgt, password=UserMgt2024!Secure")
        print("\n⚠️  IMPORTANT: Consider changing these passwords for production use!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating users: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_users()

