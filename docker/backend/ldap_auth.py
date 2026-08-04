Authorized uses only. All activity may be monitored and reported.
"""
LDAP Authentication Module
Authenticate users against Active Directory (ad.analog.com)
Uses ldap3 (pure Python) instead of python-ldap
"""
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# JWT Configuration - IMPORTANT: Set JWT_SECRET_KEY environment variable
import os
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'CHANGE_THIS_SECRET_KEY_IN_PRODUCTION')  # Use: openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', '480'))  # Default 8 hours

# Password hashing (for local admin accounts if needed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LDAPAuthenticator:
    def __init__(self):
        # Active Directory configuration - CUSTOMIZE FOR YOUR DOMAIN
        self.ldap_server = os.getenv('LDAP_SERVER', 'ldap://ldap.example.com')
        self.ldap_port = int(os.getenv('LDAP_PORT', '389'))
        self.base_dn = os.getenv('LDAP_BASE_DN', 'dc=example,dc=com')
        self.domain = os.getenv('LDAP_DOMAIN', 'EXAMPLE')  # Domain prefix for authentication

        # LDAP search filters
        self.user_search_filter = "(sAMAccountName={username})"
        self.group_search_filter = "(member={user_dn})"

        # Authorized groups (optional - restrict access)
        # Empty list = allow all AD users
        self.authorized_groups = []

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate user against Active Directory using ldap3

        Args:
            username: AD username (sAMAccountName)
            password: User password

        Returns:
            User info dict if successful, None if failed
        """
        try:
            # Clean username (remove domain if provided)
            if '\\' in username:
                username = username.split('\\')[1]
            elif '@' in username:
                username = username.split('@')[0]

            username = username.strip().lower()

            logger.info(f"Attempting LDAP authentication for user: {username}")

            # Initialize LDAP server
            server = Server(self.ldap_server, get_info=ALL)

            # User DN for authentication (DOMAIN\username format)
            user_dn = f"{self.domain}\\{username}"

            # Bind with user credentials
            conn = Connection(server, user=user_dn, password=password, auto_bind=True)

            if not conn.bind():
                logger.warning(f"✗ Invalid credentials for: {username}")
                return None

            logger.info(f"✓ LDAP bind successful for: {username}")

            # Search for user details
            search_filter = self.user_search_filter.format(username=username)

            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                attributes=['displayName', 'mail', 'memberOf', 'department', 'title']
            )

            if not conn.entries:
                logger.warning(f"✗ User not found in directory: {username}")
                conn.unbind()
                return None

            entry = conn.entries[0]

            # Extract user information
            user_info = {
                'username': username,
                'dn': str(entry.entry_dn),
                'display_name': str(entry.displayName) if hasattr(entry, 'displayName') else '',
                'email': str(entry.mail) if hasattr(entry, 'mail') else '',
                'department': str(entry.department) if hasattr(entry, 'department') else '',
                'title': str(entry.title) if hasattr(entry, 'title') else '',
                'groups': [str(g) for g in entry.memberOf] if hasattr(entry, 'memberOf') else [],
                'auth_time': datetime.utcnow().isoformat()
            }

            logger.info(f"✓ User details retrieved: {user_info['display_name']} ({user_info['email']})")

            # Optional: Check group membership
            if self.authorized_groups:
                is_authorized = any(
                    group in user_info['groups']
                    for group in self.authorized_groups
                )

                if not is_authorized:
                    logger.warning(f"✗ User {username} not in authorized groups")
                    conn.unbind()
                    return None

                logger.info(f"✓ User {username} authorized (group membership verified)")

            conn.unbind()
            return user_info

        except Exception as e:
            logger.error(f"✗ LDAP authentication error: {e}")
            return None

    def create_access_token(self, user_info: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token

        Args:
            user_info: User information dict
            expires_delta: Optional token expiration time

        Returns:
            JWT token string
        """
        to_encode = {
            'sub': user_info['username'],
            'email': user_info.get('email', ''),
            'display_name': user_info.get('display_name', ''),
            'department': user_info.get('department', ''),
            'title': user_info.get('title', '')
        }

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({'exp': expire})

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded token payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            return payload
        except JWTError:
            return None


# Global authenticator instance
ldap_auth = LDAPAuthenticator()


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate user and return user info

    Args:
        username: AD username
        password: User password

    Returns:
        User info dict if successful, None if failed
    """
    return ldap_auth.authenticate(username, password)


def create_token(user_info: Dict) -> str:
    """
    Create JWT token for authenticated user

    Args:
        user_info: User information dict

    Returns:
        JWT token string
    """
    return ldap_auth.create_access_token(user_info)


def verify_token(token: str) -> Optional[Dict]:
    """
    Verify JWT token and return user info

    Args:
        token: JWT token string

    Returns:
        User info dict if valid, None if invalid
    """
    return ldap_auth.verify_token(token)


# Test function
if __name__ == "__main__":
    # Test LDAP authentication
    import sys

    if len(sys.argv) != 3:
        print("Usage: python ldap_auth.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    print(f"Testing LDAP authentication for: {username}")
    print(f"LDAP Server: {ldap_auth.ldap_server}")
    print(f"Base DN: {ldap_auth.base_dn}")
    print()

    user_info = authenticate_user(username, password)

    if user_info:
        print("✅ Authentication successful!")
        print(f"Display Name: {user_info['display_name']}")
        print(f"Email: {user_info['email']}")
        print(f"Department: {user_info['department']}")
        print(f"Title: {user_info['title']}")
        print(f"Groups: {len(user_info['groups'])} groups")
        print()

        # Create token
        token = create_token(user_info)
        print(f"JWT Token: {token[:50]}...")
        print()

        # Verify token
        verified = verify_token(token)
        if verified:
            print("✅ Token verification successful!")
            print(f"Username: {verified['sub']}")
            print(f"Email: {verified['email']}")
        else:
            print("❌ Token verification failed!")
    else:
        print("❌ Authentication failed!")
        sys.exit(1)
