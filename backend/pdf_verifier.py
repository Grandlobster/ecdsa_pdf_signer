"""
pdf_verifier.py

Checks the digital signatures inside a PDF.

Four different questions are answered, and they are kept apart on purpose:

  1. Is the signature cryptographically valid?
     (Does the signature match the signed bytes and the certificate's public key?)
  2. Was the document changed after it was signed?
  3. Is the certificate valid today and can its chain be trusted?
     (Only certificates the user has chosen to trust count as trusted.)
  4. Is the certificate revoked?
     (This application does not check revocation, and says so.)

A valid signature alone NEVER means the signer can be trusted.
"""

import io
import logging

from asn1crypto import x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import validation
from pyhanko.sign.diff_analysis import ModificationLevel
from pyhanko.sign.validation.status import SignatureCoverageLevel
from pyhanko_certvalidator import ValidationContext

import certificate_generator
import pdf_checks


# pyHanko writes long error messages to the log for every untrusted
# certificate. We report these problems ourselves, so the log is quieted.
logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)


DIGEST_ALGORITHM_NAMES = {
    "sha1": "SHA-1",
    "sha224": "SHA-224",
    "sha256": "SHA-256",
    "sha384": "SHA-384",
    "sha512": "SHA-512",
}

SIGNATURE_ALGORITHM_NAMES = {
    "sha256_ecdsa": "ECDSA with SHA-256",
    "sha384_ecdsa": "ECDSA with SHA-384",
    "sha512_ecdsa": "ECDSA with SHA-512",
    "sha256_rsa": "RSA (PKCS#1 v1.5) with SHA-256",
    "sha384_rsa": "RSA (PKCS#1 v1.5) with SHA-384",
    "sha512_rsa": "RSA (PKCS#1 v1.5) with SHA-512",
    "rsassa_pss": "RSASSA-PSS",
}

SIGNATURE_FORMAT_NAMES = {
    "ETSI.CAdES.detached": "PAdES (CMS, ETSI.CAdES.detached)",
    "adbe.pkcs7.detached": "Adobe CMS (adbe.pkcs7.detached)",
    "adbe.pkcs7.sha1": "Adobe CMS (adbe.pkcs7.sha1)",
}

# The title and explanation shown for each possible outcome.
VERDICT_TEXT = {
    "valid_trusted": {
        "title": "Signature valid, signer trusted",
        "message": "The signature is cryptographically valid, the document has not been changed "
                   "since signing, and the certificate is in your trusted list. "
                   "Revocation status was not checked.",
    },
    "valid_untrusted": {
        "title": "Signature valid, signer not trusted",
        "message": "The signature is cryptographically valid and the document has not been "
                   "changed since signing. However, the certificate is not in your trusted list, "
                   "so the signer's identity has not been verified.",
    },
    "modified": {
        "title": "Document changed after signing",
        "message": "The signature was valid for the original document, but the file now contains "
                   "changes that the signature does not allow. Do not rely on this file.",
    },
    "signature_invalid": {
        "title": "Signature is not valid",
        "message": "The signature does not match the document. The file was changed after signing, "
                   "or the signature is damaged or forged.",
    },
    "no_signatures": {
        "title": "No signatures found",
        "message": "This PDF does not contain any digital signatures.",
    },
}

# When a file has several signatures, the most serious outcome is shown first.
VERDICT_ORDER_WORST_FIRST = ["signature_invalid", "modified", "valid_untrusted", "valid_trusted"]


def convert_to_asn1_certificate(certificate):
    # pyHanko works with asn1crypto certificates, so convert ours.
    certificate_der_bytes = certificate.public_bytes(serialization.Encoding.DER)

    return asn1_x509.Certificate.load(certificate_der_bytes)


def convert_to_cryptography_certificate(asn1_certificate):
    # The other direction: from pyHanko's certificate back to ours.
    return x509.load_der_x509_certificate(asn1_certificate.dump())


def describe_changes_after_signing(status):
    # Work out whether the document was changed after this signature was made.
    # Returns a small dictionary with a level and a plain-language explanation.

    # If the signed bytes no longer match the signature, the content was altered.
    if not status.intact:
        return {
            "modified": True,
            "level": "unauthorised_changes",
            "explanation": "The signed part of the document no longer matches the signature. "
                           "Its content was changed after signing.",
        }

    # The signature covers the whole file: nothing was added afterwards.
    if status.coverage == SignatureCoverageLevel.ENTIRE_FILE:
        return {
            "modified": False,
            "level": "none",
            "explanation": "The signature covers the entire file. Nothing was added or changed after signing.",
        }

    # From here on, the file contains something after the signed part.
    if status.coverage == SignatureCoverageLevel.UNCLEAR:
        return {
            "modified": True,
            "level": "unknown",
            "explanation": "It is unclear which parts of the file are covered by the signature.",
        }

    if status.modification_level == ModificationLevel.OTHER:
        return {
            "modified": True,
            "level": "unauthorised_changes",
            "explanation": "The document was changed after signing in ways the signature does not allow.",
        }

    if status.modification_level == ModificationLevel.ANNOTATIONS:
        return {
            "modified": True,
            "level": "permitted_changes",
            "explanation": "Comments or annotations were added after signing. "
                           "The document's rules allow this.",
        }

    if status.modification_level == ModificationLevel.FORM_FILLING:
        return {
            "modified": True,
            "level": "permitted_changes",
            "explanation": "Form fields were filled in or another signature was added after signing. "
                           "The document's rules allow this.",
        }

    if status.modification_level == ModificationLevel.LTA_UPDATES:
        return {
            "modified": True,
            "level": "permitted_changes",
            "explanation": "Only long-term validation data (such as timestamps) was added after signing.",
        }

    # No visible change, but there are extra bytes after the signed part.
    return {
        "modified": True,
        "level": "extra_data",
        "explanation": "Extra data was added after the signature. No change to the document "
                       "content was detected, but the file is not exactly what was signed.",
    }


def describe_trust(status, signature_is_valid, certificate_details):
    # Explain whether the certificate chain can be trusted, and why (or why not).
    if not signature_is_valid:
        return {
            "trusted": False,
            "explanation": "Trust was not evaluated because the signature itself is not valid.",
        }

    if status.trusted:
        return {
            "trusted": True,
            "explanation": "The certificate is in your trusted list, or is issued by a "
                           "certificate that is in your trusted list.",
        }

    if not certificate_details["is_currently_valid"]:
        return {
            "trusted": False,
            "explanation": "The certificate is expired or not valid yet, so it cannot be trusted today.",
        }

    if certificate_details["is_self_signed"]:
        return {
            "trusted": False,
            "explanation": "This is a self-signed certificate that is not in your trusted list. "
                           "Anyone can create a certificate with any name, so the signer's "
                           "identity has not been verified.",
        }

    return {
        "trusted": False,
        "explanation": "The certificate chain does not lead to any certificate in your trusted list.",
    }


def describe_revocation(status):
    # Revocation checking needs a network connection to the certificate
    # authority (CRL or OCSP). This application works offline, so it is
    # never checked, unless revocation data says "revoked" explicitly.
    if status.revoked:
        return {
            "checked": True,
            "revoked": True,
            "explanation": "The certificate has been revoked by its issuer.",
        }

    return {
        "checked": False,
        "revoked": False,
        "explanation": "Revocation was not checked. Self-signed certificates have no revocation "
                       "service, and this application does not contact certificate authorities.",
    }


def choose_verdict(signature_is_valid, changes, trust):
    # Combine the separate answers into one verdict code.
    if not signature_is_valid:
        return "signature_invalid"

    if changes["level"] == "unauthorised_changes" or changes["level"] == "unknown":
        return "modified"

    if trust["trusted"]:
        return "valid_trusted"

    return "valid_untrusted"


def read_signature_format(embedded_signature):
    # Read the signature format name, for example "ETSI.CAdES.detached".
    sub_filter = embedded_signature.sig_object.get("/SubFilter")

    if sub_filter is None:
        return "Unknown"

    raw_name = str(sub_filter).lstrip("/")

    return SIGNATURE_FORMAT_NAMES.get(raw_name, raw_name)


def read_optional_text(embedded_signature, key):
    # Read an optional text entry such as /Reason or /Location.
    value = embedded_signature.sig_object.get(key)

    if value is None:
        return ""

    return str(value)


def build_failed_result(embedded_signature, error_message):
    # Used when a signature is so damaged that it could not be checked at all.
    verdict = "signature_invalid"

    result = {
        "field_name": str(embedded_signature.field_name),
        "verdict": verdict,
        "verdict_title": VERDICT_TEXT[verdict]["title"],
        "verdict_message": VERDICT_TEXT[verdict]["message"],
        "error": error_message,
        "signature_valid": False,
        "changes": {
            "modified": True,
            "level": "unknown",
            "explanation": "The document could not be compared with the signature.",
        },
        "trust": {"trusted": False, "explanation": "Trust was not evaluated because the signature could not be checked."},
        "revocation": {"checked": False, "revoked": False, "explanation": "Revocation was not checked."},
        "certificate": None,
        "certificate_pem": "",
        "signer_name": "",
        "signature_format": read_signature_format(embedded_signature),
        "digest_algorithm": "Unknown",
        "signature_algorithm": "Unknown",
        "signing_time": "",
        "reason": "",
        "location": "",
    }

    return result


def verify_one_signature(embedded_signature, validation_context):
    # Check a single signature and build a result dictionary for the interface.
    try:
        status = validation.validate_pdf_signature(
            embedded_signature,
            signer_validation_context=validation_context,
        )
    except Exception as error:
        # A damaged signature can fail in many ways. All of them mean "not valid".
        return build_failed_result(embedded_signature, "The signature could not be checked: " + str(error))

    signing_certificate = convert_to_cryptography_certificate(status.signing_cert)
    certificate_details = certificate_generator.describe_certificate(signing_certificate)
    certificate_pem = certificate_generator.certificate_to_pem(signing_certificate).decode("ascii")

    # The signature is cryptographically valid only when BOTH checks pass:
    #   "intact" = the hash of the signed bytes matches the hash inside the signature
    #   "valid"  = the ECDSA/RSA signature itself matches the certificate's public key
    signature_is_valid = bool(status.intact and status.valid)

    changes = describe_changes_after_signing(status)
    trust = describe_trust(status, signature_is_valid, certificate_details)
    revocation = describe_revocation(status)
    verdict = choose_verdict(signature_is_valid, changes, trust)

    digest_key = str(status.md_algorithm)
    signature_key = str(status.pkcs7_signature_mechanism)

    # The signing time is what the signer's computer claimed. Without a
    # trusted timestamp it is not proven, so the interface says so.
    signing_time = ""

    if status.signer_reported_dt is not None:
        signing_time = status.signer_reported_dt.isoformat()

    result = {
        "field_name": str(embedded_signature.field_name),
        "verdict": verdict,
        "verdict_title": VERDICT_TEXT[verdict]["title"],
        "verdict_message": VERDICT_TEXT[verdict]["message"],
        "error": "",
        "signature_valid": signature_is_valid,
        "changes": changes,
        "trust": trust,
        "revocation": revocation,
        "certificate": certificate_details,
        "certificate_pem": certificate_pem,
        "signer_name": certificate_details["common_name"],
        "signature_format": read_signature_format(embedded_signature),
        "digest_algorithm": DIGEST_ALGORITHM_NAMES.get(digest_key, digest_key),
        "signature_algorithm": SIGNATURE_ALGORITHM_NAMES.get(signature_key, signature_key),
        "signing_time": signing_time,
        "reason": read_optional_text(embedded_signature, "/Reason"),
        "location": read_optional_text(embedded_signature, "/Location"),
    }

    return result


def choose_overall_verdict(signature_results):
    # Pick the most serious verdict among all signatures in the file.
    if len(signature_results) == 0:
        return "no_signatures"

    for verdict_code in VERDICT_ORDER_WORST_FIRST:
        for signature_result in signature_results:
            if signature_result["verdict"] == verdict_code:
                return verdict_code

    return "signature_invalid"


def verify_pdf_bytes(pdf_bytes, trusted_certificates):
    # Verify every signature in a PDF.
    # "trusted_certificates" is the list of certificates the user chose to trust.
    pdf_checks.check_pdf_bytes(pdf_bytes)

    trust_roots = []

    for trusted_certificate in trusted_certificates:
        trust_roots.append(convert_to_asn1_certificate(trusted_certificate))

    # allow_fetching=False keeps verification fully offline.
    validation_context = ValidationContext(trust_roots=trust_roots, allow_fetching=False)

    try:
        pdf_reader = PdfFileReader(io.BytesIO(pdf_bytes))
        embedded_signatures = list(pdf_reader.embedded_regular_signatures)
    except Exception:
        raise ValueError("The signatures in this PDF could not be read. The file may be damaged.")

    signature_results = []

    for embedded_signature in embedded_signatures:
        signature_result = verify_one_signature(embedded_signature, validation_context)
        signature_results.append(signature_result)

    overall_verdict = choose_overall_verdict(signature_results)

    verification_result = {
        "signature_count": len(signature_results),
        "overall_verdict": overall_verdict,
        "overall_title": VERDICT_TEXT[overall_verdict]["title"],
        "overall_message": VERDICT_TEXT[overall_verdict]["message"],
        "signatures": signature_results,
    }

    return verification_result
