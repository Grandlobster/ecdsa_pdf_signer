"""
demo.py

A complete, real demonstration of signing and verifying a PDF.
No web server is needed. Run it from the backend folder:

    python demo.py

It uses its own private workspace (demo_output/workspace), so the keys in
your real keys/ folder are never touched. All files it creates are kept in
the demo_output/ folder so you can open them in any PDF reader.
"""

import io
import os
import shutil
import sys

# The demo must choose its own workspace BEFORE the application modules are
# imported, because they read this setting when they are loaded.
BACKEND_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(BACKEND_FOLDER)
DEMO_FOLDER = os.path.join(PROJECT_FOLDER, "demo_output")
DEMO_WORKSPACE = os.path.join(DEMO_FOLDER, "workspace")

if os.path.exists(DEMO_FOLDER):
    shutil.rmtree(DEMO_FOLDER)

os.makedirs(DEMO_WORKSPACE)
os.environ["ECDSA_SIGNER_HOME"] = DEMO_WORKSPACE

from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

import certificate_generator
import identity_storage
import key_generator
import pdf_signer
import pdf_verifier
import sample_pdf
import trust_store


DEMO_PASSWORD = "demo-password-123456"


def save_file(file_name, file_bytes):
    file_path = os.path.join(DEMO_FOLDER, file_name)

    with open(file_path, "wb") as output_file:
        output_file.write(file_bytes)

    return file_path


def print_heading(title):
    print("")
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_verification(label, verification_result):
    print("")
    print("[" + label + "]")
    print("  Overall: " + verification_result["overall_title"])

    for signature in verification_result["signatures"]:
        print("  Signature field : " + signature["field_name"])
        print("  Signer          : " + signature["signer_name"])
        print("  Signature valid : " + str(signature["signature_valid"]))
        print("  Changed after   : " + str(signature["changes"]["modified"]) + " (" + signature["changes"]["level"] + ")")
        print("  Certificate OK  : " + str(signature["certificate"]["is_currently_valid"]) + " (within its validity period)")
        print("  Trusted         : " + str(signature["trust"]["trusted"]))
        print("  Revocation      : " + ("checked" if signature["revocation"]["checked"] else "not checked"))
        print("  Algorithms      : " + signature["signature_algorithm"] + " / digest " + signature["digest_algorithm"])
        print("  Format          : " + signature["signature_format"])


def run_demo():
    print_heading("1. Generate an ECDSA P-256 key pair and a self-signed certificate")
    private_key = key_generator.generate_private_key()
    certificate = certificate_generator.create_self_signed_certificate(
        private_key, "Demo Signer", "Demo Organization", "IN", 365
    )
    private_key_pem = key_generator.private_key_to_pem(private_key, DEMO_PASSWORD)
    public_key_pem = key_generator.public_key_to_pem(private_key)
    certificate_pem = certificate_generator.certificate_to_pem(certificate)
    identity_id = identity_storage.save_new_identity(private_key_pem, public_key_pem, certificate_pem)

    details = certificate_generator.describe_certificate(certificate)
    print("  Identity id      : " + identity_id)
    print("  Subject          : " + details["subject"])
    print("  Public key       : " + details["public_key_algorithm"] + ", curve " + details["curve"])
    print("  Signature algo   : " + details["signature_algorithm"])
    print("  Fingerprint      : " + details["fingerprint_sha256"])
    print("  Private key file : encrypted with a password = "
          + str(key_generator.private_key_pem_is_password_protected(private_key_pem)))

    print_heading("2. Create a sample PDF and sign it")
    original_pdf = sample_pdf.build_sample_pdf(["Payment Agreement", "Pay Alice 100 dollars by Friday."])
    save_file("sample.pdf", original_pdf)

    # Load the private key back from disk, exactly like the application does.
    stored_private_key_pem = identity_storage.load_private_key_pem(identity_id)
    unlocked_private_key = key_generator.load_private_key_from_pem(stored_private_key_pem, DEMO_PASSWORD)
    stored_certificate = identity_storage.load_certificate(identity_id)

    signed_pdf = pdf_signer.sign_pdf_bytes(
        original_pdf, unlocked_private_key, stored_certificate, "Demo approval", "Pune, India"
    )
    save_file("sample_signed.pdf", signed_pdf)
    print("  Original PDF : " + str(len(original_pdf)) + " bytes (sample.pdf, left untouched)")
    print("  Signed PDF   : " + str(len(signed_pdf)) + " bytes (sample_signed.pdf)")
    print("  The original file starts the signed file: "
          + str(signed_pdf.startswith(original_pdf)))

    print_heading("3. Verify the signed PDF")
    result = pdf_verifier.verify_pdf_bytes(signed_pdf, trust_store.load_trusted_certificates())
    print_verification("Nobody has chosen to trust this certificate yet", result)

    print_heading("4. Trust the certificate (a personal decision) and verify again")
    trust_store.add_trusted_certificate(stored_certificate)
    result = pdf_verifier.verify_pdf_bytes(signed_pdf, trust_store.load_trusted_certificates())
    print_verification("Certificate is now in the trusted list", result)

    print_heading("5. Tamper with the signed PDF: change 'Pay Alice 100' to 'Pay Alice 900'")
    tampered_pdf = signed_pdf.replace(b"Pay Alice 100", b"Pay Alice 900")
    save_file("sample_signed_TAMPERED_content.pdf", tampered_pdf)
    result = pdf_verifier.verify_pdf_bytes(tampered_pdf, trust_store.load_trusted_certificates())
    print_verification("Content edited inside the signed area", result)

    print_heading("6. Tamper in a different way: add a change after signing (rotate the page)")
    pdf_writer = IncrementalPdfFileWriter(io.BytesIO(signed_pdf))
    first_page = pdf_writer.root["/Pages"]["/Kids"][0].get_object()
    first_page["/Rotate"] = generic.NumberObject(90)
    pdf_writer.update_container(first_page)
    rotated_stream = io.BytesIO()
    pdf_writer.write(rotated_stream)
    save_file("sample_signed_TAMPERED_rotated.pdf", rotated_stream.getvalue())
    result = pdf_verifier.verify_pdf_bytes(rotated_stream.getvalue(), trust_store.load_trusted_certificates())
    print_verification("A new revision was appended after signing", result)

    print_heading("7. Verify an unsigned PDF")
    result = pdf_verifier.verify_pdf_bytes(original_pdf, trust_store.load_trusted_certificates())
    print_verification("Original, unsigned PDF", result)

    print_heading("8. Reject files that are not valid PDFs")
    bad_inputs = [b"", b"This is just text, not a PDF", original_pdf[:200]]

    for bad_input in bad_inputs:
        try:
            pdf_verifier.verify_pdf_bytes(bad_input, [])
        except ValueError as error:
            print("  Rejected: " + str(error))

    print("")
    print("Demo files are in: " + DEMO_FOLDER)


try:
    run_demo()
except Exception as error:
    print("The demo failed: " + str(error))
    sys.exit(1)
