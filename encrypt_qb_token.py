from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os

# Load environment variables (works locally or in Azure)
load_dotenv()

key = os.getenv("ENCRYPTION_SECRET")
if not key:
    raise ValueError("❌ ENCRYPTION_SECRET not found in environment variables")

fernet = Fernet(key.encode())

def encrypt_token(value: str) -> str:
    """Encrypt a string using Fernet encryption."""
    return fernet.encrypt(value.encode()).decode()

def decrypt_token(value: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    return fernet.decrypt(value.encode()).decode()
