"""
certificate_generator.py

Creates self-signed X.509 certificates and turns any certificate
into a simple dictionary that can be shown in the user interface.

IMPORTANT: A self-signed certificate is signed by its own private key.
Nobody else vouches for the identity inside it, so other people have no
reason to trust it unless they choose to trust it themselves.
A certificate from a trusted Certificate Authority (CA) is different:
the CA checked who you are before signing your certificate.
"""

import datetime

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


# Short labels for the most common parts of a certificate name.
NAME_LABELS = {
    "2.5.4.3": "CN",
    "2.5.4.10": "O",
    "2.5.4.11": "OU",
    "2.5.4.6": "C",
    "2.5.4.7": "L",
    "2.5.4.8": "ST",
    "1.2.840.113549.1.9.1": "E",
}

# Friendly names for common certificate signature algorithms.
SIGNATURE_ALGORITHM_NAMES = {
    "1.2.840.10045.4.3.2": "ECDSA with SHA-256",
    "1.2.840.10045.4.3.3": "ECDSA with SHA-384",
    "1.2.840.10045.4.3.4": "ECDSA with SHA-512",
    "1.2.840.113549.1.1.11": "RSA with SHA-256",
    "1.2.840.113549.1.1.12": "RSA with SHA-384",
    "1.2.840.113549.1.1.13": "RSA with SHA-512",
    "1.2.840.113549.1.1.10": "RSASSA-PSS",
    "1.2.840.113549.1.1.5": "RSA with SHA-1",
    "1.3.101.112": "Ed25519",
}

# Friendly names for the elliptic curves we may meet.
CURVE_NAMES = {
    "secp256r1": "P-256 (secp256r1)",
    "secp384r1": "P-384 (secp384r1)",
    "secp521r1": "P-521 (secp521r1)",
}

MAXIMUM_VALIDITY_DAYS = 3650


def create_self_signed_certificate(private_key, common_name, organization, country, validity_days):
    # Build a self-signed X.509 certificate for the given private key.
    # The same name is used as subject and issuer, because it signs itself.
    common_name = common_name.strip()
    organization = organization.strip()
    country = country.strip().upper()

    if common_name == "":
        raise ValueError("A name is required.")

    if len(common_name) > 64:
        raise ValueError("The name must be 64 characters or fewer.")

    if len(organization) > 64:
        raise ValueError("The organization must be 64 characters or fewer.")

    if country != "" and len(country) != 2:
        raise ValueError("The country must be a two-letter code such as IN or US.")

    if validity_days < 1 or validity_days > MAXIMUM_VALIDITY_DAYS:
        raise ValueError("The validity must be between 1 and " + str(MAXIMUM_VALIDITY_DAYS) + " days.")

    # Collect the parts of the name that were filled in.
    name_parts = []
    name_parts.append(x509.NameAttribute(NameOID.COMMON_NAME, common_name))

    if organization != "":
        name_parts.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization))

    if country != "":
        name_parts.append(x509.NameAttribute(NameOID.COUNTRY_NAME, country))

    certificate_name = x509.Name(name_parts)

    # Start a few minutes in the past so small clock differences between
    # computers do not make a brand new certificate look "not yet valid".
    now = datetime.datetime.now(datetime.timezone.utc)
    valid_from = now - datetime.timedelta(minutes=5)
    valid_until = now + datetime.timedelta(days=validity_days)

    public_key = private_key.public_key()

    # This certificate is for signing documents only. It is not a CA.
    basic_constraints = x509.BasicConstraints(ca=False, path_length=None)

    key_usage = x509.KeyUsage(
        digital_signature=True,
        content_commitment=True,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
    )

    certificate_builder = x509.CertificateBuilder()
    certificate_builder = certificate_builder.subject_name(certificate_name)
    certificate_builder = certificate_builder.issuer_name(certificate_name)
    certificate_builder = certificate_builder.public_key(public_key)
    certificate_builder = certificate_builder.serial_number(x509.random_serial_number())
    certificate_builder = certificate_builder.not_valid_before(valid_from)
    certificate_builder = certificate_builder.not_valid_after(valid_until)
    certificate_builder = certificate_builder.add_extension(basic_constraints, critical=True)
    certificate_builder = certificate_builder.add_extension(key_usage, critical=True)
    certificate_builder = certificate_builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False
    )

    # Sign the certificate with its own private key, using SHA-256.
    certificate = certificate_builder.sign(private_key, hashes.SHA256())

    return certificate


def certificate_to_pem(certificate):
    # Convert a certificate to PEM text.
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)

    return certificate_pem


def load_certificate_from_pem(certificate_pem):
    # Load a certificate from PEM text and complain clearly if it is broken.
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem)
    except ValueError:
        raise ValueError("The certificate could not be read. It must be in PEM format.")

    return certificate


def format_certificate_name(name):
    # Turn a certificate name into readable text such as "CN=Alice, O=Acme, C=IN".
    text_parts = []

    for attribute in name:
        dotted_code = attribute.oid.dotted_string
        label = NAME_LABELS.get(dotted_code, dotted_code)
        text_parts.append(label + "=" + str(attribute.value))

    return ", ".join(text_parts)


def get_common_name(name):
    # Return the common name (CN) part of a certificate name, or an empty text.
    common_name_attributes = name.get_attributes_for_oid(NameOID.COMMON_NAME)

    if len(common_name_attributes) == 0:
        return ""

    return str(common_name_attributes[0].value)


def format_fingerprint(fingerprint_bytes):
    # Show a fingerprint as pairs of hex digits separated by colons.
    hex_text = fingerprint_bytes.hex().upper()
    pairs = []

    for position in range(0, len(hex_text), 2):
        pairs.append(hex_text[position:position + 2])

    return ":".join(pairs)


def describe_public_key(certificate):
    # Work out the public key type, curve and size of a certificate.
    public_key = certificate.public_key()

    if isinstance(public_key, ec.EllipticCurvePublicKey):
        curve_name = CURVE_NAMES.get(public_key.curve.name, public_key.curve.name)
        return "ECDSA (elliptic curve)", curve_name, public_key.key_size

    if isinstance(public_key, rsa.RSAPublicKey):
        return "RSA", "Not applicable", public_key.key_size

    return "Other", "Not applicable", 0


def certificate_is_self_signed(certificate):
    # A certificate is self-signed when it was issued and signed by itself.
    if certificate.subject != certificate.issuer:
        return False

    try:
        certificate.verify_directly_issued_by(certificate)
    except (InvalidSignature, ValueError, TypeError):
        return False

    return True


def list_key_usages(certificate):
    # Return the key usages of the certificate as readable words.
    usage_names = []

    try:
        key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
    except x509.ExtensionNotFound:
        return usage_names

    if key_usage.digital_signature:
        usage_names.append("Digital signature")

    if key_usage.content_commitment:
        usage_names.append("Non-repudiation")

    if key_usage.key_encipherment:
        usage_names.append("Key encipherment")

    if key_usage.key_agreement:
        usage_names.append("Key agreement")

    if key_usage.key_cert_sign:
        usage_names.append("Certificate signing")

    if key_usage.crl_sign:
        usage_names.append("CRL signing")

    return usage_names


def describe_certificate(certificate):
    # Collect everything the interface needs to show about a certificate.
    now = datetime.datetime.now(datetime.timezone.utc)
    valid_from = certificate.not_valid_before_utc
    valid_until = certificate.not_valid_after_utc

    key_algorithm, curve_name, key_size_in_bits = describe_public_key(certificate)

    signature_oid = certificate.signature_algorithm_oid.dotted_string
    signature_algorithm_name = SIGNATURE_ALGORITHM_NAMES.get(signature_oid, signature_oid)

    fingerprint_bytes = certificate.fingerprint(hashes.SHA256())

    if valid_from <= now <= valid_until:
        is_currently_valid = True
    else:
        is_currently_valid = False

    days_remaining = (valid_until - now).days

    details = {
        "subject": format_certificate_name(certificate.subject),
        "common_name": get_common_name(certificate.subject),
        "issuer": format_certificate_name(certificate.issuer),
        "serial_number": format(certificate.serial_number, "X"),
        "not_valid_before": valid_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "not_valid_after": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_currently_valid": is_currently_valid,
        "days_remaining": days_remaining,
        "public_key_algorithm": key_algorithm,
        "curve": curve_name,
        "key_size_bits": key_size_in_bits,
        "fingerprint_sha256": format_fingerprint(fingerprint_bytes),
        "fingerprint_hex": fingerprint_bytes.hex(),
        "signature_algorithm": signature_algorithm_name,
        "is_self_signed": certificate_is_self_signed(certificate),
        "key_usages": list_key_usages(certificate),
        "version": "v" + str(certificate.version.value + 1),
    }

    return details
