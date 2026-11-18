"""
tasks.py

The real work behind the buttons. Each task is a plain function that calls the
backend modules step by step and reports which step it is on.

Tasks run in a background thread (TaskThread), so the window never freezes and
the progress display can animate while the work happens.
"""

import hashlib
import os
import time

from PySide6.QtCore import QThread, Signal

import activity_log
import certificate_generator
import folders
import identity_storage
import key_generator
import pdf_checks
import pdf_signer
import pdf_verifier
import trust_store


# After each stage the thread rests briefly. The stages themselves take only
# a fraction of a second, and this pause lets the person follow them on screen.
PAUSE_BETWEEN_STAGES_IN_SECONDS = 0.25


class TaskThread(QThread):
    # Runs one task function in the background.
    #   progress_changed(step_number)   the task moved on to the next stage
    #   succeeded(result)               the task finished, result is a dictionary
    #   failed(message)                 the task stopped, message is shown to the person
    progress_changed = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, task_function, task_arguments, parent=None):
        super().__init__(parent)
        self.task_function = task_function
        self.task_arguments = task_arguments

    def report_progress(self, step_number):
        # Called by the task at the start of every stage.
        self.progress_changed.emit(step_number)
        time.sleep(PAUSE_BETWEEN_STAGES_IN_SECONDS)

    def run(self):
        try:
            result = self.task_function(self.report_progress, *self.task_arguments)
        except ValueError as error:
            # ValueError is how the backend reports a problem the person can fix.
            self.failed.emit(str(error))
            return
        except OSError as error:
            self.failed.emit("A file could not be read or written: " + str(error))
            return
        except Exception as error:
            self.failed.emit("Something unexpected went wrong: " + str(error))
            return

        self.succeeded.emit(result)


def read_pdf_file(pdf_path):
    # Read a PDF from disk. The size is checked first, so a huge file is never loaded.
    if not os.path.isfile(pdf_path):
        raise ValueError("The file could not be found.")

    if os.path.getsize(pdf_path) > pdf_checks.MAXIMUM_PDF_SIZE_IN_BYTES:
        raise ValueError("The file is larger than 25 MB.")

    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()

    return pdf_bytes


def calculate_sha256_hex(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


# ----------------------------------------------------------------------
# Check that a file is a usable PDF (used right after the person picks it)
# ----------------------------------------------------------------------

def check_pdf_file(pdf_path):
    # Returns the file size in bytes, or raises ValueError with a friendly message.
    pdf_bytes = read_pdf_file(pdf_path)
    pdf_checks.check_pdf_bytes(pdf_bytes)

    return len(pdf_bytes)


# ----------------------------------------------------------------------
# Generate a key pair and certificate
# ----------------------------------------------------------------------

CREATE_IDENTITY_STEPS = [
    "Generating the ECDSA P-256 key pair",
    "Creating the X.509 certificate",
    "Saving the key and certificate",
]


def create_identity_task(report_progress, common_name, organization, country,
                         validity_days, password, allow_unprotected):
    # A private key is only saved without a password if the person agreed explicitly.
    if password == "" and not allow_unprotected:
        raise ValueError("Choose a password, or confirm that the key may be stored without one.")

    if password != "":
        key_generator.check_password_is_strong_enough(password)

    report_progress(0)
    private_key = key_generator.generate_private_key()

    report_progress(1)
    certificate = certificate_generator.create_self_signed_certificate(
        private_key, common_name, organization, country, validity_days
    )

    report_progress(2)
    private_key_pem = key_generator.private_key_to_pem(private_key, password)
    public_key_pem = key_generator.public_key_to_pem(private_key)
    certificate_pem = certificate_generator.certificate_to_pem(certificate)
    identity_id = identity_storage.save_new_identity(private_key_pem, public_key_pem, certificate_pem)

    return identity_storage.build_identity_summary(identity_id)


# ----------------------------------------------------------------------
# Sign a PDF
# ----------------------------------------------------------------------

SIGN_STEPS = [
    "Checking the PDF",
    "Unlocking the private key",
    "Signing with ECDSA P-256 and SHA-256",
    "Verifying the new signature",
    "Saving the signed PDF",
]


def sign_document_task(report_progress, pdf_path, identity_id, password, reason, location):
    report_progress(0)
    pdf_bytes = read_pdf_file(pdf_path)
    pdf_checks.check_pdf_bytes(pdf_bytes)
    original_filename = os.path.basename(pdf_path)

    if not identity_storage.identity_exists(identity_id):
        raise ValueError("Please select a signing identity.")

    report_progress(1)
    private_key_pem = identity_storage.load_private_key_pem(identity_id)
    private_key = key_generator.load_private_key_from_pem(private_key_pem, password)
    certificate = identity_storage.load_certificate(identity_id)

    report_progress(2)
    signed_pdf_bytes = pdf_signer.sign_pdf_bytes(pdf_bytes, private_key, certificate, reason, location)

    # Check our own work by verifying the signature we just created.
    report_progress(3)
    trusted_certificates = trust_store.load_trusted_certificates()
    verification = pdf_verifier.verify_pdf_bytes(signed_pdf_bytes, trusted_certificates)
    new_signature = verification["signatures"][-1]

    if not new_signature["signature_valid"]:
        raise ValueError("The new signature did not pass its own check, so the file was not saved.")

    report_progress(4)
    signed_file_name = pdf_signer.save_signed_pdf(signed_pdf_bytes, original_filename)
    signed_file_path = os.path.join(folders.SIGNED_DOCUMENTS_FOLDER, signed_file_name)

    certificate_details = certificate_generator.describe_certificate(certificate)
    activity_log.add_activity(
        "sign", original_filename, "Signed as " + certificate_details["common_name"], signed_file_name
    )

    result = {
        "original_filename": original_filename,
        "original_size": len(pdf_bytes),
        "original_sha256": calculate_sha256_hex(pdf_bytes),
        "signed_file_name": signed_file_name,
        "signed_file_path": signed_file_path,
        "signed_size": len(signed_pdf_bytes),
        "signed_sha256": calculate_sha256_hex(signed_pdf_bytes),
        "certificate": certificate_details,
        "signature": new_signature,
    }

    return result


# ----------------------------------------------------------------------
# Verify a PDF
# ----------------------------------------------------------------------

VERIFY_STEPS = [
    "Reading the PDF",
    "Checking the signatures and what changed since signing",
    "Checking the certificates against your trusted list",
]


def verify_document_task(report_progress, pdf_path, record_in_activity):
    report_progress(0)
    pdf_bytes = read_pdf_file(pdf_path)
    original_filename = os.path.basename(pdf_path)

    report_progress(1)
    trusted_certificates = trust_store.load_trusted_certificates()

    report_progress(2)
    verification = pdf_verifier.verify_pdf_bytes(pdf_bytes, trusted_certificates)

    if record_in_activity:
        activity_log.add_activity("verify", original_filename, verification["overall_title"])

    verification["filename"] = original_filename
    verification["size"] = len(pdf_bytes)
    verification["sha256"] = calculate_sha256_hex(pdf_bytes)

    return verification
