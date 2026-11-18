"""
page_certificates.py

All certificates in one place: your own, and the ones you chose to trust.
You can also add somebody else's certificate (a PEM file) to the trusted list.
"""

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

import certificate_generator
import formatting
import identity_storage
import theme
import trust_store
import widgets
from page_base import BasePage


class CertificatesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Certificates",
            "Your own certificates, and the certificates you have decided to trust.",
            parent,
        )

        self.content_layout.addWidget(widgets.make_label("Your certificates", "heading"))
        self.content_layout.addSpacing(8)
        self.own_container = QWidget()
        self.own_layout = QVBoxLayout(self.own_container)
        self.own_layout.setContentsMargins(0, 0, 0, 0)
        self.own_layout.setSpacing(0)
        self.content_layout.addWidget(self.own_container)
        self.content_layout.addSpacing(44)

        heading_row = QHBoxLayout()
        heading_row.addWidget(widgets.make_label("Trusted certificates", "heading"))
        heading_row.addStretch(1)
        add_button = widgets.SoftButton("Add a certificate to trust", "secondary")
        add_button.clicked.connect(self.add_certificate_from_file)
        heading_row.addWidget(add_button)
        self.content_layout.addLayout(heading_row)
        self.content_layout.addSpacing(8)

        self.trusted_container = QWidget()
        self.trusted_layout = QVBoxLayout(self.trusted_container)
        self.trusted_layout.setContentsMargins(0, 0, 0, 0)
        self.trusted_layout.setSpacing(0)
        self.content_layout.addWidget(self.trusted_container)
        self.content_layout.addSpacing(44)

        explanation_text = (
            "A self-signed certificate is signed by its own owner. Nobody else has checked that the name "
            "inside it is real, so you should only trust one when you received its fingerprint directly "
            "from the owner.\n\n"
            "A certificate issued by a certificate authority was signed by that authority after it checked "
            "the owner's identity. Trusting the authority's certificate means trusting every certificate it issues.\n\n"
            "Signet treats a signer as trusted only if its certificate, or the certificate that issued it, "
            "is in the trusted list above. It does not contact certificate authorities, so revocation "
            "is never checked."
        )
        self.content_layout.addWidget(widgets.ExpandablePanel(
            "Self-signed and authority-issued certificates", "",
            widgets.make_label(explanation_text, "body", color=theme.MUTE, wrap=True)))
        self.content_layout.addStretch(1)

    def refresh(self):
        self.fill_own_certificates()
        self.fill_trusted_certificates()

    def fill_own_certificates(self):
        widgets.clear_layout(self.own_layout)
        summaries = identity_storage.list_identity_summaries()

        if len(summaries) == 0:
            self.own_layout.addWidget(widgets.make_divider())
            self.own_layout.addSpacing(14)
            self.own_layout.addWidget(widgets.make_label(
                "You have not created a certificate yet. Open Key generation to make one.", "mute", wrap=True))
            return

        self.own_layout.addWidget(widgets.make_divider())

        for summary in summaries:
            details_view = widgets.CertificateDetailsView(summary["certificate"])
            panel = widgets.ExpandablePanel(
                summary["common_name"], formatting.describe_validity(summary["certificate"]), details_view)
            self.own_layout.addWidget(panel)

    def fill_trusted_certificates(self):
        widgets.clear_layout(self.trusted_layout)
        trusted_details = trust_store.list_trusted_certificate_details()
        self.trusted_layout.addWidget(widgets.make_divider())

        if len(trusted_details) == 0:
            self.trusted_layout.addSpacing(14)
            self.trusted_layout.addWidget(widgets.make_label(
                "No certificates are trusted yet. Signatures are still checked, "
                "but every signer is reported as not trusted.", "mute", wrap=True))
            return

        for certificate in trusted_details:
            body = QWidget()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(14)
            body_layout.addWidget(widgets.CertificateDetailsView(certificate))

            remove_button = widgets.SoftButton("Remove from trusted list", "secondary")
            remove_button.fingerprint_hex = certificate["fingerprint_hex"]
            remove_button.clicked.connect(self.remove_certificate_of_sender)
            remove_row = QHBoxLayout()
            remove_row.addWidget(remove_button)
            remove_row.addStretch(1)
            body_layout.addLayout(remove_row)

            panel = widgets.ExpandablePanel(
                certificate["common_name"], formatting.short_fingerprint(certificate["fingerprint_sha256"]), body)
            self.trusted_layout.addWidget(panel)

    def remove_certificate_of_sender(self):
        fingerprint_hex = self.sender().fingerprint_hex
        trust_store.remove_trusted_certificate(fingerprint_hex)
        self.refresh()

    def add_certificate_from_file(self):
        chosen_path, selected_filter = QFileDialog.getOpenFileName(
            self, "Choose a certificate", "", "Certificates (*.pem *.crt *.cer);;All files (*)"
        )

        if chosen_path == "":
            return

        try:
            with open(chosen_path, "rb") as certificate_file:
                certificate_bytes = certificate_file.read(100000)

            certificate = certificate_generator.load_certificate_from_pem(certificate_bytes)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Could not add the certificate", str(error))
            return

        details = certificate_generator.describe_certificate(certificate)

        answer = QMessageBox.question(
            self, "Trust this certificate?",
            "Only trust a certificate if you are sure it belongs to \"" + details["common_name"] + "\".\n\n"
            "SHA-256 fingerprint:\n" + formatting.split_fingerprint_in_two_lines(details["fingerprint_sha256"])
            + "\n\nTrust it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            trust_store.add_trusted_certificate(certificate)
            self.refresh()
