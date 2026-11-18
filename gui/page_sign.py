"""
page_sign.py

The signing workflow:
  1. choose or drop a PDF
  2. choose a signing identity (and enter its password)
  3. optional reason and location
  then "Sign document", watch the progress, and save the signed PDF.
"""

import os
import shutil

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

import formatting
import identity_storage
import tasks
import widgets
from page_base import BasePage


class SignPage(BasePage):
    # Sent when the person wants to verify the file they just signed.
    verify_file_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(
            "Sign a PDF",
            "Add a cryptographic signature that shows who signed the document "
            "and that it has not changed since.",
            parent,
        )
        self.pdf_path = ""
        self.pdf_size = 0
        self.identities = []
        self.task_thread = None
        self.last_result = None

        # Page 0 is the form, page 1 is the result after signing.
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_form_view())
        self.result_holder = QWidget()
        self.result_holder_layout = QVBoxLayout(self.result_holder)
        self.result_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.result_holder)

        self.content_layout.addWidget(self.stack)
        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------
    # The form
    # ------------------------------------------------------------------

    def build_form_view(self):
        form_view = QWidget()
        columns = QHBoxLayout(form_view)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(48)

        left_column = QVBoxLayout()
        left_column.setSpacing(0)

        # Step 1: the document
        left_column.addWidget(widgets.make_label("1.  Document", "heading"))
        left_column.addSpacing(12)
        self.drop_zone = widgets.DropZone("Drop a PDF here", "or click to choose a file")
        self.drop_zone.file_chosen.connect(self.load_pdf_file)
        left_column.addWidget(self.drop_zone)
        left_column.addSpacing(10)

        self.file_error_holder = QVBoxLayout()
        left_column.addLayout(self.file_error_holder)
        left_column.addSpacing(26)

        # Step 2: the identity
        left_column.addWidget(widgets.make_label("2.  Signing identity", "heading"))
        left_column.addSpacing(12)

        self.identity_picker = QComboBox()
        self.identity_picker.currentIndexChanged.connect(self.identity_changed)
        left_column.addWidget(self.identity_picker)

        self.no_identity_holder = QVBoxLayout()
        left_column.addLayout(self.no_identity_holder)

        left_column.addSpacing(12)
        self.password_field = QWidget()
        password_layout = QVBoxLayout(self.password_field)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(6)
        password_layout.addWidget(widgets.make_label("Password for this private key", "mute"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.start_signing)
        password_layout.addWidget(self.password_input)
        left_column.addWidget(self.password_field)
        left_column.addSpacing(26)

        # Step 3: optional details
        left_column.addWidget(widgets.make_label("3.  Details (optional)", "heading"))
        left_column.addSpacing(12)

        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Reason, for example: I approve this contract")
        self.reason_input.setMaxLength(200)
        left_column.addWidget(self.reason_input)
        left_column.addSpacing(10)

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Location, for example: Pune, India")
        self.location_input.setMaxLength(200)
        left_column.addWidget(self.location_input)
        left_column.addSpacing(26)

        self.sign_button = widgets.SoftButton("Sign document", "primary")
        self.sign_button.clicked.connect(self.start_signing)
        self.sign_button.setEnabled(False)
        left_column.addWidget(self.sign_button)
        left_column.addSpacing(18)

        self.progress = widgets.StepProgress(tasks.SIGN_STEPS)
        self.progress.hide()
        left_column.addWidget(self.progress)
        left_column.addSpacing(14)

        self.sign_error_holder = QVBoxLayout()
        left_column.addLayout(self.sign_error_holder)
        left_column.addStretch(1)

        # The summary on the right
        right_column = QVBoxLayout()
        right_column.setSpacing(0)
        right_column.addWidget(widgets.make_label("Summary", "heading"))
        right_column.addSpacing(14)

        self.summary_container = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        right_column.addWidget(self.summary_container)
        right_column.addSpacing(28)

        self.certificate_container = QWidget()
        self.certificate_layout = QVBoxLayout(self.certificate_container)
        self.certificate_layout.setContentsMargins(0, 0, 0, 0)
        right_column.addWidget(self.certificate_container)
        right_column.addStretch(1)

        columns.addLayout(left_column, 6)
        columns.addLayout(right_column, 5)

        return form_view

    def show_error_in(self, holder_layout, message_text):
        widgets.clear_layout(holder_layout)

        if message_text == "":
            return

        notice = widgets.Notice(message_text, "error")
        holder_layout.addWidget(notice)
        widgets.fade_in(notice)

    # ------------------------------------------------------------------
    # Loading the list of identities and the summary
    # ------------------------------------------------------------------

    def refresh(self):
        # Reload identities every time the page opens, remembering the current choice.
        previous_identity_id = self.current_identity_id()
        self.identities = identity_storage.list_identity_summaries()

        self.identity_picker.blockSignals(True)
        self.identity_picker.clear()
        selected_position = 0

        for position in range(len(self.identities)):
            identity = self.identities[position]
            self.identity_picker.addItem(identity["common_name"], identity["identity_id"])

            if identity["identity_id"] == previous_identity_id:
                selected_position = position

        if len(self.identities) > 0:
            self.identity_picker.setCurrentIndex(selected_position)

        self.identity_picker.blockSignals(False)

        widgets.clear_layout(self.no_identity_holder)

        if len(self.identities) == 0:
            self.no_identity_holder.addSpacing(10)
            self.no_identity_holder.addWidget(widgets.Notice(
                "You need a signing identity first. It only takes a few seconds.", "info"))
            create_button = widgets.SoftButton("Create an identity", "secondary")
            create_button.clicked.connect(self.open_key_generation)
            self.no_identity_holder.addSpacing(10)
            self.no_identity_holder.addWidget(create_button)

        self.identity_changed()

    def open_key_generation(self):
        self.navigate_requested.emit("keys")

    def current_identity(self):
        position = self.identity_picker.currentIndex()

        if position < 0 or position >= len(self.identities):
            return None

        return self.identities[position]

    def current_identity_id(self):
        identity = self.current_identity()

        if identity is None:
            return ""

        return identity["identity_id"]

    def identity_changed(self):
        identity = self.current_identity()

        if identity is not None:
            self.password_field.setVisible(identity["password_protected"])
            self.password_input.clear()
        else:
            self.password_field.setVisible(False)

        self.identity_picker.setVisible(identity is not None)
        self.rebuild_summary()
        self.rebuild_certificate_view()
        self.update_sign_button()

    def update_sign_button(self):
        ready = self.pdf_path != "" and self.current_identity() is not None
        self.sign_button.setEnabled(ready and self.task_thread is None)

    def rebuild_summary(self):
        widgets.clear_layout(self.summary_layout)
        identity = self.current_identity()

        if self.pdf_path == "":
            file_name = "No file chosen"
            file_size = "Not available"
            status_text = "Waiting for a document"
        else:
            file_name = os.path.basename(self.pdf_path)
            file_size = formatting.format_bytes(self.pdf_size)
            status_text = "Ready to sign"

        if identity is None:
            certificate_text = "No identity selected"
            status_text = "Waiting for an identity"
        else:
            certificate_text = identity["common_name"]

        rows = [
            ("Original file", file_name, False),
            ("File size", file_size, False),
            ("Signing certificate", certificate_text, False),
            ("Signature algorithm", "ECDSA, P-256 curve", False),
            ("Hash algorithm", "SHA-256", False),
            ("Signature format", "PAdES (CMS, ETSI.CAdES.detached)", False),
            ("Signature status", status_text, False),
        ]
        self.summary_layout.addWidget(widgets.build_key_value_widget(rows))

    def rebuild_certificate_view(self):
        widgets.clear_layout(self.certificate_layout)
        identity = self.current_identity()

        if identity is None:
            return

        self.certificate_layout.addWidget(widgets.make_label("Certificate", "heading"))
        self.certificate_layout.addSpacing(6)
        self.certificate_layout.addWidget(widgets.CertificateDetailsView(identity["certificate"]))

    # ------------------------------------------------------------------
    # Choosing a PDF
    # ------------------------------------------------------------------

    def load_pdf_file(self, pdf_path):
        # Check the file straight away, so problems show up before signing.
        self.show_error_in(self.file_error_holder, "")
        self.show_error_in(self.sign_error_holder, "")

        try:
            file_size = tasks.check_pdf_file(pdf_path)
        except ValueError as error:
            self.pdf_path = ""
            self.pdf_size = 0
            self.drop_zone.clear_chosen_file()
            self.show_error_in(self.file_error_holder, str(error))
            self.rebuild_summary()
            self.update_sign_button()
            return

        self.pdf_path = pdf_path
        self.pdf_size = file_size
        self.drop_zone.show_chosen_file(os.path.basename(pdf_path), formatting.format_bytes(file_size))
        self.rebuild_summary()
        self.update_sign_button()

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def start_signing(self):
        identity = self.current_identity()

        if self.task_thread is not None or self.pdf_path == "" or identity is None:
            return

        if identity["password_protected"] and self.password_input.text() == "":
            self.show_error_in(self.sign_error_holder, "Enter the password for this private key.")
            return

        self.show_error_in(self.sign_error_holder, "")
        self.sign_button.setEnabled(False)
        self.progress.reset()
        self.progress.show()

        arguments = (
            self.pdf_path,
            identity["identity_id"],
            self.password_input.text(),
            self.reason_input.text().strip(),
            self.location_input.text().strip(),
        )

        self.task_thread = tasks.TaskThread(tasks.sign_document_task, arguments)
        self.task_thread.progress_changed.connect(self.progress.show_step)
        self.task_thread.succeeded.connect(self.finish_signing)
        self.task_thread.failed.connect(self.fail_signing)
        self.task_thread.finished.connect(self.forget_task_thread)
        self.task_thread.start()

    def forget_task_thread(self):
        # Qt reports "finished" only when the thread has really stopped.
        # Dropping the thread any earlier would destroy it while it is still running.
        self.task_thread = None
        self.update_sign_button()

    def fail_signing(self, error_message):
        self.progress.hide()
        self.show_error_in(self.sign_error_holder, error_message)

    def finish_signing(self, result):
        self.last_result = result
        self.progress.show_all_done()
        self.password_input.clear()

        # Let the finished progress bar be seen for a moment, then show the result.
        widgets.clear_layout(self.result_holder_layout)
        self.result_holder_layout.addWidget(self.build_result_view(result))
        self.stack.setCurrentIndex(1)
        widgets.fade_in(self.result_holder, 300)

    # ------------------------------------------------------------------
    # The result
    # ------------------------------------------------------------------

    def build_result_view(self, result):
        signature = result["signature"]
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(widgets.StatusRow(
            "pass", "The document was signed",
            "The new signature passed its own check. The original file was not changed; "
            "the signed copy is a new file."))
        layout.addSpacing(18)

        rows = [
            ("Original file", result["original_filename"] + "  (" + formatting.format_bytes(result["original_size"]) + ")", False),
            ("Signed file", result["signed_file_name"] + "  (" + formatting.format_bytes(result["signed_size"]) + ")", False),
            ("Saved in", os.path.dirname(result["signed_file_path"]), False),
            ("Signing certificate", result["certificate"]["subject"], False),
            ("Signature algorithm", signature["signature_algorithm"], False),
            ("Hash algorithm", signature["digest_algorithm"], False),
            ("Signature format", signature["signature_format"], False),
            ("Signature status", signature["verdict_title"], False),
            ("SHA-256 of signed file", formatting.split_fingerprint_in_two_lines(
                self.colon_separate(result["signed_sha256"])), True),
        ]
        layout.addWidget(widgets.build_key_value_widget(rows))
        layout.addSpacing(24)

        layout.addWidget(widgets.Notice(
            "Anyone who opens this file will see the signature is valid, but they will only see "
            "it as trusted after they add your certificate to their own trusted list. "
            "Share your certificate (Key generation, then Export) so they can do that.", "info"))
        layout.addSpacing(28)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        save_button = widgets.SoftButton("Save a copy as...", "primary")
        save_button.clicked.connect(self.save_copy_of_signed_pdf)
        folder_button = widgets.SoftButton("Show in folder", "secondary")
        folder_button.clicked.connect(self.show_signed_pdf_in_folder)
        verify_button = widgets.SoftButton("Verify this file", "secondary")
        verify_button.clicked.connect(self.verify_signed_pdf)
        again_button = widgets.SoftButton("Sign another document", "quiet")
        again_button.clicked.connect(self.start_over)

        button_row.addWidget(save_button)
        button_row.addWidget(folder_button)
        button_row.addWidget(verify_button)
        button_row.addWidget(again_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)

        return view

    def colon_separate(self, hex_text):
        # "ab12cd..." becomes "AB:12:CD:..." like a certificate fingerprint.
        pairs = []

        for position in range(0, len(hex_text), 2):
            pairs.append(hex_text[position:position + 2].upper())

        return ":".join(pairs)

    def save_copy_of_signed_pdf(self):
        signed_file_path = self.last_result["signed_file_path"]
        chosen_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save signed PDF", self.last_result["signed_file_name"], "PDF documents (*.pdf)"
        )

        if chosen_path == "":
            return

        try:
            shutil.copyfile(signed_file_path, chosen_path)
        except OSError as error:
            QMessageBox.warning(self, "Could not save", "The file could not be saved: " + str(error))

    def show_signed_pdf_in_folder(self):
        folder_path = os.path.dirname(self.last_result["signed_file_path"])
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def verify_signed_pdf(self):
        self.verify_file_requested.emit(self.last_result["signed_file_path"])

    def start_over(self):
        self.pdf_path = ""
        self.pdf_size = 0
        self.last_result = None
        self.drop_zone.clear_chosen_file()
        self.progress.reset()
        self.progress.hide()
        self.show_error_in(self.file_error_holder, "")
        self.show_error_in(self.sign_error_holder, "")
        self.stack.setCurrentIndex(0)
        widgets.fade_in(self.stack, 240)
        self.rebuild_summary()
        self.update_sign_button()
