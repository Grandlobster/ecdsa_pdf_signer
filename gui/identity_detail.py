"""
identity_detail.py

The detailed view of one signing identity. It opens by growing out of the
identity's card (see page_keys.py) and shows the certificate, the export buttons
and the trust and delete actions.
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QMessageBox, QScrollArea, QVBoxLayout, QWidget

import certificate_generator
import formatting
import identity_storage
import theme
import trust_store
import widgets


class IdentityDetailView(QFrame):
    close_requested = Signal()
    data_changed = Signal()

    def __init__(self, identity_id, parent=None):
        super().__init__(parent)
        self.identity_id = identity_id
        self.setObjectName("detail_card")
        self.setStyleSheet(
            "QFrame#detail_card { background: #FFFFFF; border: 1px solid " + theme.LINE
            + "; border-radius: " + str(theme.CORNER_RADIUS) + "px; }"
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scroll_area)

        self.build_content()

    def build_content(self):
        # (Re)build everything from the current state of the identity on disk.
        summary = identity_storage.build_identity_summary(self.identity_id)
        certificate = summary["certificate"]
        self.summary = summary

        surface = QWidget()
        surface.setObjectName("detail_surface")
        surface.setStyleSheet("QWidget#detail_surface { background: #FFFFFF; }")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(48, 32, 48, 48)

        column = QWidget()
        column.setMaximumWidth(860)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        surface_layout.addWidget(column, 1, Qt.AlignmentFlag.AlignTop)
        surface_layout.addStretch(0)

        back_button = widgets.SoftButton("Back to identities", "quiet")
        back_button.clicked.connect(self.close_requested.emit)
        back_row = QHBoxLayout()
        back_row.addWidget(back_button)
        back_row.addStretch(1)
        layout.addLayout(back_row)
        layout.addSpacing(20)

        layout.addWidget(widgets.make_label(summary["common_name"], "title", wrap=True))
        layout.addSpacing(6)
        layout.addWidget(widgets.make_label(
            "Created " + formatting.format_date_time(summary["created_at"]), "mute"))
        layout.addSpacing(28)

        # Two status lines: how the private key is stored, and whether it is trusted.
        if summary["password_protected"]:
            layout.addWidget(widgets.StatusRow(
                "pass", "Private key is protected by a password",
                "It is stored encrypted. The password is needed every time you sign."))
        else:
            layout.addWidget(widgets.StatusRow(
                "warn", "Private key is stored without a password",
                "Anyone who can read your files can sign as you. This key cannot be exported."))

        if summary["is_trusted"]:
            layout.addWidget(widgets.StatusRow(
                "pass", "Certificate is in your trusted list",
                "Documents signed with it are reported as trusted on this computer."))
        else:
            layout.addWidget(widgets.StatusRow(
                "unknown", "Certificate is not in your trusted list",
                "Signatures are valid, but reported as not trusted until you trust this certificate."))

        layout.addSpacing(20)
        layout.addWidget(widgets.Notice(
            "The private key proves your identity. Anyone who has it can sign in your name. "
            "Never share it, and keep any exported copy somewhere safe. "
            "Your certificate and public key are safe to share.", "warning"))
        layout.addSpacing(32)

        layout.addWidget(widgets.make_label("Certificate", "heading"))
        layout.addSpacing(6)
        layout.addWidget(widgets.CertificateDetailsView(certificate, first_panel_open=True))
        layout.addSpacing(32)

        layout.addWidget(widgets.make_label("Export", "heading"))
        layout.addSpacing(12)

        export_row = QHBoxLayout()
        export_row.setSpacing(10)

        certificate_button = widgets.SoftButton("Certificate (.pem)", "secondary")
        certificate_button.clicked.connect(self.export_certificate)
        public_key_button = widgets.SoftButton("Public key (.pem)", "secondary")
        public_key_button.clicked.connect(self.export_public_key)
        private_key_button = widgets.SoftButton("Encrypted private key (.pem)", "secondary")
        private_key_button.clicked.connect(self.export_private_key)
        private_key_button.setEnabled(summary["password_protected"])

        export_row.addWidget(certificate_button)
        export_row.addWidget(public_key_button)
        export_row.addWidget(private_key_button)
        export_row.addStretch(1)
        layout.addLayout(export_row)
        layout.addSpacing(32)

        layout.addWidget(widgets.make_label("Manage", "heading"))
        layout.addSpacing(12)

        manage_row = QHBoxLayout()
        manage_row.setSpacing(10)

        if summary["is_trusted"]:
            trust_button = widgets.SoftButton("Remove from trusted list", "secondary")
            trust_button.clicked.connect(self.remove_trust)
        else:
            trust_button = widgets.SoftButton("Trust this certificate", "secondary")
            trust_button.clicked.connect(self.add_trust)

        delete_button = widgets.SoftButton("Delete identity", "secondary")
        delete_button.clicked.connect(self.delete_identity)

        manage_row.addWidget(trust_button)
        manage_row.addWidget(delete_button)
        manage_row.addStretch(1)
        layout.addLayout(manage_row)
        layout.addStretch(1)

        self.scroll_area.setWidget(surface)

    # ------------------------------------------------------------------
    # Exporting
    # ------------------------------------------------------------------

    def build_default_file_name(self, ending):
        safe_name = ""

        for character in self.summary["common_name"]:
            if character.isalnum():
                safe_name = safe_name + character
            else:
                safe_name = safe_name + "_"

        if safe_name.strip("_") == "":
            safe_name = "identity"

        return safe_name + ending

    def save_bytes_with_dialog(self, dialog_title, default_name, file_bytes):
        # Ask where to save, then write the file. Returns the path, or "" if cancelled.
        chosen_path, selected_filter = QFileDialog.getSaveFileName(
            self, dialog_title, default_name, "PEM files (*.pem)"
        )

        if chosen_path == "":
            return ""

        try:
            with open(chosen_path, "wb") as output_file:
                output_file.write(file_bytes)
        except OSError as error:
            QMessageBox.warning(self, "Could not save", "The file could not be saved: " + str(error))
            return ""

        return chosen_path

    def export_certificate(self):
        certificate = identity_storage.load_certificate(self.identity_id)
        certificate_pem = certificate_generator.certificate_to_pem(certificate)
        self.save_bytes_with_dialog(
            "Save certificate", self.build_default_file_name("-certificate.pem"), certificate_pem)

    def export_public_key(self):
        public_key_pem = identity_storage.load_public_key_pem(self.identity_id)
        self.save_bytes_with_dialog(
            "Save public key", self.build_default_file_name("-public-key.pem"), public_key_pem)

    def export_private_key(self):
        # A private key is only exported when it is encrypted with a password.
        if not self.summary["password_protected"]:
            return

        answer = QMessageBox.warning(
            self, "Export private key",
            "You are about to save a copy of your private key.\n\n"
            "The file is encrypted with your password, but anyone who obtains it and guesses "
            "the password can sign in your name. Store it somewhere safe, such as an "
            "encrypted drive, and never send it to anyone.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        private_key_pem = identity_storage.load_private_key_pem(self.identity_id)
        saved_path = self.save_bytes_with_dialog(
            "Save encrypted private key",
            self.build_default_file_name("-private-key-ENCRYPTED.pem"),
            private_key_pem,
        )

        if saved_path != "":
            # Ask the operating system to keep the file private (works on Linux and macOS).
            try:
                os.chmod(saved_path, 0o600)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Trust and delete
    # ------------------------------------------------------------------

    def add_trust(self):
        certificate = identity_storage.load_certificate(self.identity_id)
        trust_store.add_trusted_certificate(certificate)
        self.build_content()
        self.data_changed.emit()

    def remove_trust(self):
        fingerprint_hex = self.summary["certificate"]["fingerprint_hex"]
        trust_store.remove_trusted_certificate(fingerprint_hex)
        self.build_content()
        self.data_changed.emit()

    def delete_identity(self):
        answer = QMessageBox.warning(
            self, "Delete identity",
            "Delete \"" + self.summary["common_name"] + "\" permanently?\n\n"
            "The private key will be erased and cannot be recovered. Documents you already signed "
            "stay valid, but you will not be able to sign anything else with this identity.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        identity_storage.delete_identity(self.identity_id)
        self.data_changed.emit()
        self.close_requested.emit()
