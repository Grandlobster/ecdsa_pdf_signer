"""
folders.py

Knows where the application keeps its files on disk.

  * Running from source code:  next to the "backend" folder (keys/, certificates/, ...).
  * Running as the packaged .exe:  in  Documents/ECDSA PDF Signer  of the current user,
    because the folder that holds the .exe may not be writable.
  * Setting the environment variable ECDSA_SIGNER_HOME overrides both. Tests use
    this so that real keys are never touched.
"""

import os
import sys


BACKEND_FOLDER = os.path.dirname(os.path.abspath(__file__))
SOURCE_PROJECT_FOLDER = os.path.dirname(BACKEND_FOLDER)


def choose_project_folder():
    # Decide where all keys, certificates and signed documents are stored.
    override_folder = os.environ.get("ECDSA_SIGNER_HOME")

    if override_folder:
        return override_folder

    program_is_packaged = getattr(sys, "frozen", False)

    if program_is_packaged:
        documents_folder = os.path.join(os.path.expanduser("~"), "Documents")
        return os.path.join(documents_folder, "ECDSA PDF Signer")

    return SOURCE_PROJECT_FOLDER


PROJECT_FOLDER = choose_project_folder()

KEYS_FOLDER = os.path.join(PROJECT_FOLDER, "keys")
CERTIFICATES_FOLDER = os.path.join(PROJECT_FOLDER, "certificates")
TRUSTED_FOLDER = os.path.join(CERTIFICATES_FOLDER, "trusted")
SIGNED_DOCUMENTS_FOLDER = os.path.join(PROJECT_FOLDER, "signed_documents")
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")


def make_sure_folders_exist():
    # Create every folder the application needs, if it is not there yet.
    folders_to_create = [
        KEYS_FOLDER,
        CERTIFICATES_FOLDER,
        TRUSTED_FOLDER,
        SIGNED_DOCUMENTS_FOLDER,
        DATA_FOLDER,
    ]

    for folder in folders_to_create:
        os.makedirs(folder, exist_ok=True)
