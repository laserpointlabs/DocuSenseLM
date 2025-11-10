# User Management Guide

This guide explains how to manage user accounts in the NDA Dashboard, including creating users, updating passwords, and understanding user roles.

## Table of Contents

- [User Roles](#user-roles)
- [Creating Users](#creating-users)
- [Updating Passwords](#updating-passwords)
- [Managing Users via API](#managing-users-via-api)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## User Roles

The NDA Dashboard supports three user roles:

### Admin (`admin`)
- **Full system access**
- Can upload documents
- Can access admin functions
- Can manage all users
- Can re-index documents
- Can view all statistics

### User Management (`usermgt`)
- **User management access**
- Can create and manage users
- Can view user lists
- Cannot access admin functions (re-indexing, etc.)
- Can upload documents

### Standard User (`user`)
- **Basic access**
- Can search documents
- Can ask questions
- Can view documents
- Cannot upload documents
- Cannot manage users

## Creating Users

### Initial Setup

When setting up the system for the first time, use the `create_users.py` script to create the default admin and usermgt accounts:

```bash
# From the project root directory
docker compose exec -T api python scripts/create_users.py
```

This will create:
- **Admin user**: `admin` / `Admin2024!Secure`
- **UserMgt user**: `usermgt` / `UserMgt2024!Secure`

**⚠️ Important**: Change these default passwords immediately after first setup!

### Creating Additional Users

#### Option 1: Via API (Recommended)

Once logged in as an admin or usermgt user, you can create new users via the API:

```bash
# First, get an authentication token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin2024!Secure"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Create a new user
curl -X POST http://localhost:8000/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "SecurePassword123!",
    "role": "user"
  }'
```

#### Option 2: Via Python Script

You can create a custom script to add users:

```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import User
from api.auth import get_password_hash

db = get_db_session()
try:
    new_user = User(
        username="newuser",
        password_hash=get_password_hash("SecurePassword123!"),
        role="user",  # or "admin" or "usermgt"
        is_active=True
    )
    db.add(new_user)
    db.commit()
    print(f"✓ Created user: newuser")
finally:
    db.close()
```

## Updating Passwords

### Using the Update Passwords Script

The easiest way to update passwords is using the provided script:

```bash
# Update admin and usermgt passwords
docker compose exec -T api python scripts/update_passwords.py
```

**Note**: This script updates the default admin and usermgt passwords. To update other users, see the API method below.

### Updating Passwords via API

To update a user's password, you'll need to modify the script or use direct database access:

```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import User
from api.auth import get_password_hash

def update_user_password(username, new_password):
    db = get_db_session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.password_hash = get_password_hash(new_password)
            db.commit()
            print(f"✓ Updated password for user: {username}")
        else:
            print(f"✗ User not found: {username}")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

# Example: Update admin password
update_user_password("admin", "NewSecurePassword2024!")
```

### Updating Your Own Password

Currently, there's no self-service password change feature. Users need to contact an admin or usermgt user to reset their password.

## Managing Users via API

### List All Users

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin2024!Secure"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# List all users
curl -X GET http://localhost:8000/auth/users \
  -H "Authorization: Bearer $TOKEN"
```

### Get Current User Info

```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Create a New User

```bash
curl -X POST http://localhost:8000/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "SecurePassword123!",
    "role": "user"
  }'
```

**Valid roles**: `admin`, `usermgt`, `user`

## Best Practices

### Password Security

1. **Use Strong Passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and special characters
   - Avoid dictionary words or common patterns

2. **Change Default Passwords Immediately**
   - The default admin and usermgt passwords should be changed on first login
   - Use the `update_passwords.py` script or API to change them

3. **Regular Password Updates**
   - Consider updating passwords periodically
   - Use the update script or API methods described above

### User Account Management

1. **Principle of Least Privilege**
   - Only grant admin access to trusted users
   - Use `usermgt` role for users who need to manage accounts but not system functions
   - Use `user` role for standard access

2. **Account Deactivation**
   - To deactivate a user, set `is_active=False` in the database
   - Deactivated users cannot log in

3. **Audit Trail**
   - User creation timestamps are stored in `created_at`
   - User updates are tracked in `updated_at`

### Security Considerations

1. **JWT Secret Key**
   - Set `JWT_SECRET_KEY` environment variable in production
   - Use a strong, random secret key
   - Never commit secrets to version control

2. **Database Security**
   - Ensure PostgreSQL is not exposed to the internet
   - Use strong database passwords
   - Regularly backup user data

3. **Network Security**
   - Use HTTPS in production
   - Consider IP whitelisting for admin access
   - Monitor failed login attempts

## Troubleshooting

### User Cannot Log In

1. **Check Username and Password**
   ```bash
   # Test login via API
   curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"Admin2024!Secure"}'
   ```

2. **Check if User is Active**
   ```python
   from api.db import get_db_session
   from api.db.schema import User
   
   db = get_db_session()
   user = db.query(User).filter(User.username == "admin").first()
   print(f"Active: {user.is_active}")
   db.close()
   ```

3. **Reset Password**
   - Use the update password script or API method
   - Ensure password meets requirements

### Permission Denied Errors

- Verify the user has the correct role for the operation
- Admin operations require `admin` role
- User management requires `admin` or `usermgt` role
- Standard operations require any active user

### Database Connection Issues

```bash
# Check if database is accessible
docker compose exec -T postgres psql -U nda_user -d nda_db -c "SELECT username, role FROM users;"
```

## Scripts Reference

### `scripts/create_users.py`
Creates initial admin and usermgt users with secure default passwords.

**Usage:**
```bash
docker compose exec -T api python scripts/create_users.py
```

### `scripts/update_passwords.py`
Updates passwords for admin and usermgt users.

**Usage:**
```bash
docker compose exec -T api python scripts/update_passwords.py
```

**Note**: Edit the script to change the default passwords before running.

## Database Schema

The `users` table structure:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Example Workflows

### Setting Up a New Environment

1. Start the services:
   ```bash
   docker compose up -d
   ```

2. Initialize database tables:
   ```bash
   docker compose exec -T api python -c "from api.db import init_db; init_db()"
   ```

3. Create default users:
   ```bash
   docker compose exec -T api python scripts/create_users.py
   ```

4. Update default passwords:
   ```bash
   # Edit scripts/update_passwords.py with your desired passwords
   docker compose exec -T api python scripts/update_passwords.py
   ```

### Adding a New Team Member

1. Log in as admin or usermgt user
2. Create new user via API:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"YourPassword"}' \
     | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
   
   curl -X POST http://localhost:8000/auth/users \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "newteammember",
       "password": "SecurePassword123!",
       "role": "user"
     }'
   ```

3. Share credentials securely with the new team member

### Resetting a Forgotten Password

1. Log in as admin or usermgt user
2. Use the update password script or API to reset the password
3. Share the new password securely with the user
4. Recommend they change it after first login (when self-service is implemented)

## Support

For issues or questions about user management:
- Check the API documentation at `http://localhost:8000/docs`
- Review the authentication endpoints: `/auth/login`, `/auth/users`, `/auth/me`
- Check application logs: `docker compose logs api`

