"""
self_test.py

A quick end-to-end check that signing and verifying really work, used to
confirm that a packaged copy of the program is complete.
Start it with:   Signet --self-test    (or: python main.py --self-test)

It works in a temporary folder, so your own keys are never touched.
"""

import tempfile
import os


def run_self_test():
    # Everything happens in a throw-away folder.
    # This must be set before the other modules are imported.
    os.environ["ECDSA_SIGNER_HOME"] = tempfile.mkdtemp(prefix="signet_self_test_")

    import certificate_generator
    import key_generator
    import pdf_signer
    import pdf_verifier
    import sample_pdf

    results = []

    private_key = key_generator.generate_private_key()
    certificate = certificate_generator.create_self_signed_certificate(
        private_key, "Self Test", "Signet", "IN", 1
    )
    results.append("Created an ECDSA P-256 key pair and certificate")

    original_pdf = sample_pdf.build_sample_pdf(["Self test document"])
    signed_pdf = pdf_signer.sign_pdf_bytes(original_pdf, private_key, certificate, "", "")
    results.append("Signed a PDF (" + str(len(signed_pdf)) + " bytes)")

    verification = pdf_verifier.verify_pdf_bytes(signed_pdf, [])
    signature = verification["signatures"][0]

    if not signature["signature_valid"]:
        raise ValueError("The new signature was not valid.")

    if signature["trust"]["trusted"]:
        raise ValueError("A self-signed certificate must not be trusted automatically.")

    results.append("Verified the signature: valid, not trusted (correct for a self-signed certificate)")

    tampered_pdf = signed_pdf.replace(b"Self test document", b"Self test DOCUMENT")
    tampered_verification = pdf_verifier.verify_pdf_bytes(tampered_pdf, [])

    if tampered_verification["signatures"][0]["signature_valid"]:
        raise ValueError("A changed document was not detected.")

    results.append("Detected a document that was changed after signing")

    return results
