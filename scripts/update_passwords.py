#!/usr/bin/env python3
"""
Script to update user passwords in the database.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import User
from api.auth import get_password_hash

def update_passwords():
    """Update admin and usermgt passwords"""
    db = get_db_session()
    try:
        # Update admin password
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            new_admin_password = "Admin2024!Secure"
            admin_user.password_hash = get_password_hash(new_admin_password)
            print(f"✓ Updated admin password to: {new_admin_password}")
        else:
            print("ℹ Admin user not found")
        
        # Update usermgt password
        usermgt_user = db.query(User).filter(User.username == "usermgt").first()
        if usermgt_user:
            new_usermgt_password = "UserMgt2024!Secure"
            usermgt_user.password_hash = get_password_hash(new_usermgt_password)
            print(f"✓ Updated usermgt password to: {new_usermgt_password}")
        else:
            print("ℹ Usermgt user not found")
        
        db.commit()
        print("\n✅ Password update complete!")
        print("\nNew credentials:")
        print("  Admin: username=admin, password=Admin2024!Secure")
        print("  UserMgt: username=usermgt, password=UserMgt2024!Secure")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating passwords: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_passwords()

