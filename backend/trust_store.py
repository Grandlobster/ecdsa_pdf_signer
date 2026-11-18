"""
trust_store.py

Keeps the list of certificates the user has chosen to trust.

Trusting a certificate is a personal decision: "I believe this certificate
really belongs to the person it names." The signature check alone can never
tell you that, so a certificate is only reported as trusted when it is in
this list (or is issued by a certificate in this list).
"""

import os

from cryptography.hazmat.primitives import hashes

import certificate_generator
import folders


def fingerprint_is_valid(fingerprint_hex):
    # A SHA-256 fingerprint written in hex is exactly 64 characters of 0-9 and a-f.
    if len(fingerprint_hex) != 64:
        return False

    for character in fingerprint_hex:
        if character not in "0123456789abcdef":
            return False

    return True


def build_trusted_file_path(fingerprint_hex):
    # Every trusted certificate is saved under the name of its fingerprint.
    file_name = fingerprint_hex + ".pem"

    return os.path.join(folders.TRUSTED_FOLDER, file_name)


def certificate_is_trusted(fingerprint_hex):
    # Check whether a certificate with this fingerprint is in the trusted list.
    if not fingerprint_is_valid(fingerprint_hex):
        return False

    return os.path.exists(build_trusted_file_path(fingerprint_hex))


def add_trusted_certificate(certificate):
    # Save a certificate in the trusted list and return its fingerprint.
    folders.make_sure_folders_exist()

    fingerprint_hex = certificate.fingerprint(hashes.SHA256()).hex()
    certificate_pem = certificate_generator.certificate_to_pem(certificate)

    with open(build_trusted_file_path(fingerprint_hex), "wb") as trusted_file:
        trusted_file.write(certificate_pem)

    return fingerprint_hex


def remove_trusted_certificate(fingerprint_hex):
    # Remove a certificate from the trusted list. Returns False if it was not there.
    if not certificate_is_trusted(fingerprint_hex):
        return False

    os.remove(build_trusted_file_path(fingerprint_hex))

    return True


def load_trusted_certificates():
    # Read every certificate in the trusted list from disk.
    folders.make_sure_folders_exist()
    trusted_certificates = []

    for file_name in sorted(os.listdir(folders.TRUSTED_FOLDER)):
        if not file_name.endswith(".pem"):
            continue

        file_path = os.path.join(folders.TRUSTED_FOLDER, file_name)

        try:
            with open(file_path, "rb") as trusted_file:
                certificate = certificate_generator.load_certificate_from_pem(trusted_file.read())
        except (OSError, ValueError):
            # A damaged file is skipped instead of stopping the whole application.
            continue

        trusted_certificates.append(certificate)

    return trusted_certificates


def list_trusted_certificate_details():
    # Describe every trusted certificate so the interface can list them.
    details_list = []

    for certificate in load_trusted_certificates():
        details_list.append(certificate_generator.describe_certificate(certificate))

    return details_list
