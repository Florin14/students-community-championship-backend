import binascii
import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
    hashed = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, 100000)
    return (salt + binascii.hexlify(hashed)).decode("ascii")


def verify_password(stored_password: str, provided_password: str) -> bool:
    salt = stored_password[:64]
    stored_hash = stored_password[64:]
    hashed = hashlib.pbkdf2_hmac(
        "sha512", provided_password.encode("utf-8"), salt.encode("ascii"), 100000
    )
    return hmac.compare_digest(binascii.hexlify(hashed).decode("ascii"), stored_hash)
