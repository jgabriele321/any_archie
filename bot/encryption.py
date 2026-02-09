"""
Encryption module for securely storing user credentials.
Uses Fernet (symmetric encryption) for encrypting/decrypting Google API keys.
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CREDENTIAL_ENCRYPTION_KEY


def get_encryption_key() -> bytes:
    """
    Get or generate the encryption key from environment variable.
    
    If CREDENTIAL_ENCRYPTION_KEY is set, uses that.
    Otherwise generates a new key (should only happen once during setup).
    
    Returns:
        Fernet encryption key as bytes
    """
    key_str = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    
    if key_str:
        # Use existing key
        try:
            # If it's base64 encoded, decode it
            if len(key_str) == 44:  # Fernet keys are 44 chars when base64 encoded
                return key_str.encode()
            # Otherwise, derive a key from it
            return _derive_key(key_str)
        except Exception:
            return _derive_key(key_str)
    else:
        # Generate a new key (for initial setup)
        key = Fernet.generate_key()
        print(f"\n⚠️  IMPORTANT: Add this to your .env file:\n")
        print(f"CREDENTIAL_ENCRYPTION_KEY={key.decode()}\n")
        return key


def _derive_key(password: str) -> bytes:
    """
    Derive a Fernet key from a password string.
    
    Args:
        password: Password string
        
    Returns:
        Fernet key as bytes
    """
    # Use a fixed salt for consistency (in production, you might want to store this)
    salt = b'anyarchie_credential_salt_v1'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_data(data: str) -> str:
    """
    Encrypt a string using Fernet.
    
    Args:
        data: Plain text string to encrypt
        
    Returns:
        Encrypted string (base64 encoded)
    """
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> Optional[str]:
    """
    Decrypt a string using Fernet.
    
    Args:
        encrypted_data: Encrypted string (base64 encoded)
        
    Returns:
        Decrypted plain text string, or None if decryption fails
    """
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return None