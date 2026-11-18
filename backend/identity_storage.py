"""
identity_storage.py

A "signing identity" is a private key, its public key and its certificate.
This module saves identities in the keys/ and certificates/ folders and
loads them again.

Files for one identity (the identity id is a random 12 character code):
    keys/<id>.private.pem        the private key (never sent to the browser)
    keys/<id>.public.pem         the public key
    certificates/<id>.cert.pem   the X.509 certificate
"""

import datetime
import os
import secrets

import certificate_generator
import folders
import key_generator
import trust_store


def identity_id_is_valid(identity_id):
    # Identity ids are 12 hex characters. Checking this also blocks
    # tricks such as "../../something" being used as a file name.
    if len(identity_id) != 12:
        return False

    for character in identity_id:
        if character not in "0123456789abcdef":
            return False

    return True


def build_private_key_path(identity_id):
    return os.path.join(folders.KEYS_FOLDER, identity_id + ".private.pem")


def build_public_key_path(identity_id):
    return os.path.join(folders.KEYS_FOLDER, identity_id + ".public.pem")


def build_certificate_path(identity_id):
    return os.path.join(folders.CERTIFICATES_FOLDER, identity_id + ".cert.pem")


def read_file_bytes(file_path):
    with open(file_path, "rb") as opened_file:
        file_content = opened_file.read()

    return file_content


def write_private_key_file(file_path, private_key_pem):
    # Create the private key file so that only the current user can read it.
    # O_EXCL makes sure we never overwrite an existing key by accident.
    file_descriptor = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    with os.fdopen(file_descriptor, "wb") as private_key_file:
        private_key_file.write(private_key_pem)


def save_new_identity(private_key_pem, public_key_pem, certificate_pem):
    # Save the three files of a new identity and return its id.
    folders.make_sure_folders_exist()

    identity_id = secrets.token_hex(6)

    write_private_key_file(build_private_key_path(identity_id), private_key_pem)

    with open(build_public_key_path(identity_id), "wb") as public_key_file:
        public_key_file.write(public_key_pem)

    with open(build_certificate_path(identity_id), "wb") as certificate_file:
        certificate_file.write(certificate_pem)

    return identity_id


def identity_exists(identity_id):
    if not identity_id_is_valid(identity_id):
        return False

    return os.path.exists(build_certificate_path(identity_id))


def load_certificate(identity_id):
    # Load the certificate of an identity.
    certificate_pem = read_file_bytes(build_certificate_path(identity_id))

    return certificate_generator.load_certificate_from_pem(certificate_pem)


def load_private_key_pem(identity_id):
    return read_file_bytes(build_private_key_path(identity_id))


def load_public_key_pem(identity_id):
    return read_file_bytes(build_public_key_path(identity_id))


def build_identity_summary(identity_id):
    # Collect what the interface needs to show about one identity.
    certificate = load_certificate(identity_id)
    private_key_pem = load_private_key_pem(identity_id)
    certificate_details = certificate_generator.describe_certificate(certificate)

    created_timestamp = os.path.getmtime(build_certificate_path(identity_id))
    created_at = datetime.datetime.fromtimestamp(created_timestamp, datetime.timezone.utc)

    is_trusted = trust_store.certificate_is_trusted(certificate_details["fingerprint_hex"])

    summary = {
        "identity_id": identity_id,
        "common_name": certificate_details["common_name"],
        "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "password_protected": key_generator.private_key_pem_is_password_protected(private_key_pem),
        "is_trusted": is_trusted,
        "certificate": certificate_details,
    }

    return summary


def list_identity_summaries():
    # Return all saved identities, newest first.
    folders.make_sure_folders_exist()
    found_identities = []

    for file_name in os.listdir(folders.CERTIFICATES_FOLDER):
        if not file_name.endswith(".cert.pem"):
            continue

        identity_id = file_name.replace(".cert.pem", "")

        if not identity_id_is_valid(identity_id):
            continue

        try:
            summary = build_identity_summary(identity_id)
        except (OSError, ValueError):
            # An identity with a missing or damaged file is skipped.
            continue

        found_identities.append((summary["created_at"], identity_id, summary))

    # Tuples are sorted by their first item (the creation time), newest first.
    found_identities = sorted(found_identities, reverse=True)

    summaries = []

    for created_at, identity_id, summary in found_identities:
        summaries.append(summary)

    return summaries


def delete_identity(identity_id):
    # Permanently remove the private key, public key and certificate.
    paths_to_remove = [
        build_private_key_path(identity_id),
        build_public_key_path(identity_id),
        build_certificate_path(identity_id),
    ]

    for file_path in paths_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)
