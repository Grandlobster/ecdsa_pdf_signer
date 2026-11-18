"""
key_generator.py

Creates, converts and loads ECDSA P-256 key pairs.
All cryptography is done by the "cryptography" library.
Nothing is implemented by hand.
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


# A password must be at least this long, because the encrypted key file
# could be copied and attacked offline by someone who steals it.
MINIMUM_PASSWORD_LENGTH = 12


def generate_private_key():
    # Generate a new ECDSA private key using the P-256 curve.
    private_key = ec.generate_private_key(ec.SECP256R1())

    return private_key


def check_password_is_strong_enough(password):
    # Raise an error if the password is too short to protect a private key.
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        message = "The password must be at least " + str(MINIMUM_PASSWORD_LENGTH) + " characters long."
        raise ValueError(message)


def private_key_to_pem(private_key, password):
    # Convert the private key to PEM text (PKCS#8 format).
    # If a password is given, the key is encrypted with that password.
    if password:
        password_bytes = password.encode("utf-8")
        encryption_method = serialization.BestAvailableEncryption(password_bytes)
    else:
        encryption_method = serialization.NoEncryption()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption_method,
    )

    return private_key_pem


def public_key_to_pem(private_key):
    # Take the public half of the key pair and convert it to PEM text.
    public_key = private_key.public_key()

    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return public_key_pem


def private_key_pem_is_password_protected(private_key_pem):
    # An encrypted PKCS#8 key always has "ENCRYPTED" in its PEM header line.
    if b"ENCRYPTED" in private_key_pem:
        return True

    return False


def load_private_key_from_pem(private_key_pem, password):
    # Load a private key from PEM text.
    # The password is only needed when the key file is encrypted.
    key_is_protected = private_key_pem_is_password_protected(private_key_pem)

    if key_is_protected and not password:
        raise ValueError("This private key is protected by a password. Please enter it.")

    if key_is_protected:
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = None

    try:
        private_key = serialization.load_pem_private_key(private_key_pem, password=password_bytes)
    except (ValueError, TypeError):
        raise ValueError("The private key could not be unlocked. The password may be wrong.")

    # This application only works with ECDSA keys on the P-256 curve.
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("The private key is not an elliptic curve key.")

    if private_key.curve.name != "secp256r1":
        raise ValueError("The private key is not on the P-256 curve.")

    return private_key
