"""
pdf_signer.py

Signs PDF documents with a real digital signature.

How it works:
  1. pyHanko calculates a SHA-256 hash of the whole PDF (except the space
     reserved for the signature itself).
  2. That hash is signed with the ECDSA P-256 private key.
  3. The result is packed into a CMS (PKCS#7) container together with the
     signer's certificate. The container follows the PAdES baseline format
     (sub-filter ETSI.CAdES.detached).
  4. The container is written into the PDF as an "incremental update".
     The original bytes of the PDF stay exactly as they were.
"""

import datetime
import io
import os
import secrets

from asn1crypto import keys as asn1_keys
from asn1crypto import x509 as asn1_x509
from cryptography.hazmat.primitives import serialization
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields
from pyhanko.sign import signers
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko_certvalidator.registry import SimpleCertificateStore

import certificate_generator
import folders
import pdf_checks


def check_certificate_can_sign_now(certificate):
    # A certificate that has expired (or is not valid yet) must not be used.
    now = datetime.datetime.now(datetime.timezone.utc)

    if now < certificate.not_valid_before_utc:
        raise ValueError("This certificate is not valid yet.")

    if now > certificate.not_valid_after_utc:
        raise ValueError("This certificate has expired. Please generate a new identity.")


def create_pyhanko_signer(private_key, certificate):
    # pyHanko uses a different library (asn1crypto) to represent keys and
    # certificates, so we hand them over in the standard DER byte format.
    certificate_der_bytes = certificate.public_bytes(serialization.Encoding.DER)

    private_key_der_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    signing_certificate = asn1_x509.Certificate.load(certificate_der_bytes)
    signing_key = asn1_keys.PrivateKeyInfo.load(private_key_der_bytes)

    certificate_store = SimpleCertificateStore()

    signer = signers.SimpleSigner(
        signing_cert=signing_certificate,
        signing_key=signing_key,
        cert_registry=certificate_store,
    )

    return signer


def choose_signature_field_name(pdf_bytes):
    # Every signature lives in a named field. A PDF that was already signed
    # has "Signature1", so the next signer gets "Signature2", and so on.
    pdf_reader = PdfFileReader(io.BytesIO(pdf_bytes))

    existing_field_names = []

    for field_information in fields.enumerate_sig_fields(pdf_reader):
        existing_field_names.append(field_information[0])

    number = 1

    while "Signature" + str(number) in existing_field_names:
        number = number + 1

    return "Signature" + str(number)


def sign_pdf_bytes(pdf_bytes, private_key, certificate, reason, location):
    # Sign the PDF and return the bytes of the new, signed PDF.
    # The original bytes passed in are never modified.
    pdf_checks.check_pdf_bytes(pdf_bytes)
    check_certificate_can_sign_now(certificate)

    signer = create_pyhanko_signer(private_key, certificate)
    field_name = choose_signature_field_name(pdf_bytes)
    signer_name = certificate_generator.get_common_name(certificate.subject)

    # Empty texts are replaced by None, so no empty entries end up in the PDF.
    if reason == "":
        reason = None

    if location == "":
        location = None

    signature_settings = signers.PdfSignatureMetadata(
        field_name=field_name,
        md_algorithm="sha256",
        subfilter=SigSeedSubFilter.PADES,
        name=signer_name,
        reason=reason,
        location=location,
    )

    pdf_signer = signers.PdfSigner(signature_settings, signer=signer)
    pdf_writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    signed_pdf_stream = io.BytesIO()

    try:
        pdf_signer.sign_pdf(pdf_writer, output=signed_pdf_stream)
    except Exception as error:
        raise ValueError("The PDF could not be signed: " + str(error))

    return signed_pdf_stream.getvalue()


def make_file_name_safe(file_name):
    # Keep only letters, digits, dots, dashes and underscores, so the
    # name can never contain a path or a character Windows does not allow.
    safe_characters = []

    for character in file_name:
        if character.isalnum() or character in "._-":
            safe_characters.append(character)
        else:
            safe_characters.append("_")

    return "".join(safe_characters).strip("._")


def build_signed_file_name(original_filename):
    # "contract.pdf" becomes something like "contract_signed_20261117_093000_ab12.pdf".
    safe_file_name = make_file_name_safe(original_filename)
    file_name_without_extension = os.path.splitext(safe_file_name)[0]

    if file_name_without_extension == "":
        file_name_without_extension = "document"

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_ending = secrets.token_hex(2)

    return file_name_without_extension + "_signed_" + timestamp + "_" + random_ending + ".pdf"


def save_signed_pdf(signed_pdf_bytes, original_filename):
    # Save the signed PDF as a NEW file. The original is never overwritten.
    folders.make_sure_folders_exist()

    signed_file_name = build_signed_file_name(original_filename)
    signed_file_path = os.path.join(folders.SIGNED_DOCUMENTS_FOLDER, signed_file_name)

    # Mode "xb" refuses to open a file that already exists.
    with open(signed_file_path, "xb") as signed_file:
        signed_file.write(signed_pdf_bytes)

    return signed_file_name
