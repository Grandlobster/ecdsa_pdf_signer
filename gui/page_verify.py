"""
page_verify.py

Verify a signed PDF. Four questions are answered separately and never mixed up:
  * Is the signature cryptographically valid?
  * Was the document changed after it was signed?
  * Is the certificate valid today?
  * Can the certificate be trusted?  (Revocation is reported as "not checked".)
A valid signature on its own never means the signer is trusted.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

import certificate_generator
import formatting
import tasks
import theme
import trust_store
import widgets
from page_base import BasePage


class VerdictBlock(QFrame):
    # The big headline result. Colour is never used, only weight and line style:
    #   trusted                black block with white text
    #   valid, not trusted     solid black outline
    #   changed / not valid    dashed black outline
    #   no signatures          light grey outline
    def __init__(self, verdict_code, title_text, message_text, parent=None):
        super().__init__(parent)
        self.setObjectName("verdict_block")
        radius_text = str(theme.CORNER_RADIUS) + "px"

        if verdict_code == "valid_trusted":
            style = "background: #000000; border: 1px solid #000000;"
            icon_name = "shield"
            icon_color = theme.PAPER
            text_color = theme.PAPER
            message_color = "#CFCFCF"
        elif verdict_code == "valid_untrusted":
            style = "background: #FFFFFF; border: 2px solid #111111;"
            icon_name = "warning"
            icon_color = theme.INK
            text_color = theme.INK
            message_color = theme.MUTE
        elif verdict_code in ("modified", "signature_invalid"):
            style = "background: #FFFFFF; border: 2px dashed #111111;"
            icon_name = "cross"
            icon_color = theme.INK
            text_color = theme.INK
            message_color = theme.MUTE
        else:
            style = "background: #FFFFFF; border: 1px solid " + theme.LINE + ";"
            icon_name = "minus"
            icon_color = theme.MUTE
            text_color = theme.INK
            message_color = theme.MUTE

        self.setStyleSheet("QFrame#verdict_block { " + style + " border-radius: " + radius_text + "; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(20)

        text_column = QVBoxLayout()
        text_column.setSpacing(6)
        text_column.addWidget(widgets.make_label(title_text, "subtitle", color=text_color, wrap=True))
        text_column.addWidget(widgets.make_label(message_text, "body", color=message_color, wrap=True))

        layout.addWidget(widgets.make_icon_label(icon_name, 32, icon_color), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_column, 1)


class VerifyPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Verify a PDF",
            "Check who signed a document, whether the signature is genuine, "
            "and whether the file was changed afterwards.",
            parent,
        )
        self.pdf_path = ""
        self.task_thread = None

        self.drop_zone = widgets.DropZone("Drop a signed PDF here", "or click to choose a file")
        self.drop_zone.file_chosen.connect(self.verify_file)
        self.content_layout.addWidget(self.drop_zone)
        self.content_layout.addSpacing(24)

        self.progress = widgets.StepProgress(tasks.VERIFY_STEPS)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.error_holder = QVBoxLayout()
        self.content_layout.addLayout(self.error_holder)

        self.result_holder = QVBoxLayout()
        self.result_holder.setSpacing(0)
        self.content_layout.addLayout(self.result_holder)
        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Running a verification
    # ------------------------------------------------------------------

    def verify_file(self, pdf_path, record_in_activity=True):
        if self.task_thread is not None:
            return

        self.pdf_path = pdf_path
        widgets.clear_layout(self.error_holder)
        widgets.clear_layout(self.result_holder)

        try:
            file_size = tasks.check_pdf_file(pdf_path)
        except ValueError as error:
            self.drop_zone.clear_chosen_file()
            self.progress.hide()
            self.show_error(str(error))
            return

        self.drop_zone.show_chosen_file(os.path.basename(pdf_path), formatting.format_bytes(file_size))
        self.progress.reset()
        self.progress.show()

        self.task_thread = tasks.TaskThread(tasks.verify_document_task, (pdf_path, record_in_activity))
        self.task_thread.progress_changed.connect(self.progress.show_step)
        self.task_thread.succeeded.connect(self.show_result)
        self.task_thread.failed.connect(self.fail_verification)
        self.task_thread.finished.connect(self.forget_task_thread)
        self.task_thread.start()

    def show_error(self, message_text):
        notice = widgets.Notice(message_text, "error")
        self.error_holder.addWidget(notice)
        widgets.fade_in(notice)

    def forget_task_thread(self):
        # Qt reports "finished" only when the thread has really stopped.
        # Dropping the thread any earlier would destroy it while it is still running.
        self.task_thread = None

    def fail_verification(self, error_message):
        self.progress.hide()
        self.show_error(error_message)

    def show_result(self, verification):
        self.progress.show_all_done()
        widgets.clear_layout(self.result_holder)

        result_view = self.build_result_view(verification)
        self.result_holder.addWidget(result_view)
        widgets.fade_in(result_view, 320)

    # ------------------------------------------------------------------
    # Building the result
    # ------------------------------------------------------------------

    def build_result_view(self, verification):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addSpacing(28)
        layout.addWidget(VerdictBlock(
            verification["overall_verdict"], verification["overall_title"], verification["overall_message"]))
        layout.addSpacing(16)

        file_summary = (
            verification["filename"] + "  (" + formatting.format_bytes(verification["size"]) + ")"
        )
        layout.addWidget(widgets.build_key_value_widget([
            ("File", file_summary, False),
            ("Signatures found", str(verification["signature_count"]), False),
            ("SHA-256 of file", formatting.split_fingerprint_in_two_lines(
                self.colon_separate(verification["sha256"])), True),
        ]))
        layout.addSpacing(36)

        signature_number = 1

        for signature in verification["signatures"]:
            layout.addWidget(self.build_signature_section(signature, signature_number, verification["signature_count"]))
            layout.addSpacing(36)
            signature_number = signature_number + 1

        layout.addWidget(self.build_explanation_panel())

        return view

    def colon_separate(self, hex_text):
        pairs = []

        for position in range(0, len(hex_text), 2):
            pairs.append(hex_text[position:position + 2].upper())

        return ":".join(pairs)

    def build_signature_section(self, signature, signature_number, signature_count):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if signature["signer_name"] != "":
            heading_text = signature["signer_name"]
        else:
            heading_text = "Unknown signer"

        layout.addWidget(widgets.make_label(heading_text, "subtitle", wrap=True))
        position_text = (
            "Signature " + str(signature_number) + " of " + str(signature_count)
            + ", in field " + signature["field_name"]
        )

        if not signature["signature_valid"]:
            position_text = position_text + ". The name comes from the file itself and is not verified."

        layout.addWidget(widgets.make_label(position_text, "mute", wrap=True))
        layout.addSpacing(12)

        # The four questions, each answered on its own line.
        for status_row in self.build_status_rows(signature):
            layout.addWidget(status_row)
            layout.addWidget(widgets.make_divider())

        layout.addSpacing(20)

        if signature["signing_time"] != "":
            time_text = formatting.format_date_time(signature["signing_time"]) + "  (claimed by the signer, not proven)"
        else:
            time_text = "Not recorded"

        detail_rows = [
            ("Signature algorithm", signature["signature_algorithm"], False),
            ("Digest algorithm", signature["digest_algorithm"], False),
            ("Signature format", signature["signature_format"], False),
            ("Signing time", time_text, False),
        ]

        if signature["reason"] != "":
            detail_rows.append(("Reason", signature["reason"], False))

        if signature["location"] != "":
            detail_rows.append(("Location", signature["location"], False))

        layout.addWidget(widgets.build_key_value_widget(detail_rows))

        if signature["certificate"] is not None:
            layout.addSpacing(22)
            layout.addWidget(widgets.make_label("Signing certificate", "heading"))
            layout.addSpacing(6)
            layout.addWidget(widgets.CertificateDetailsView(signature["certificate"]))

            can_be_trusted = signature["signature_valid"] and not signature["trust"]["trusted"]

            if can_be_trusted:
                layout.addSpacing(20)
                trust_row = QHBoxLayout()
                trust_button = widgets.SoftButton("Trust this certificate", "secondary")
                trust_button.certificate_pem = signature["certificate_pem"]
                trust_button.clicked.connect(self.trust_certificate_of_sender)
                trust_row.addWidget(trust_button)
                trust_row.addStretch(1)
                layout.addLayout(trust_row)

        return section

    def build_status_rows(self, signature):
        rows = []
        certificate = signature["certificate"]
        changes = signature["changes"]

        # 1. Is the signature itself cryptographically valid?
        if signature["signature_valid"]:
            rows.append(widgets.StatusRow(
                "pass", "Signature is cryptographically valid",
                "The signature matches the signed content and the public key in the certificate."))
        else:
            detail = "The signature does not match the document, so it was altered or the signature is damaged."

            if signature["error"] != "":
                detail = signature["error"]

            rows.append(widgets.StatusRow("fail", "Signature is not valid", detail))

        # 2. Was the document changed after signing?
        if not changes["modified"]:
            rows.append(widgets.StatusRow("pass", "Not changed since signing", changes["explanation"]))
        elif changes["level"] in ("permitted_changes", "extra_data"):
            rows.append(widgets.StatusRow("warn", "Additions after signing", changes["explanation"]))
        else:
            rows.append(widgets.StatusRow("fail", "Changed after signing", changes["explanation"]))

        # 3. Is the certificate valid today?
        if certificate is None:
            rows.append(widgets.StatusRow(
                "unknown", "Certificate could not be read", "The signing certificate is missing or damaged."))
        elif certificate["is_currently_valid"]:
            rows.append(widgets.StatusRow(
                "pass", "Certificate is valid today",
                "Valid from " + formatting.format_date(certificate["not_valid_before"])
                + " until " + formatting.format_date(certificate["not_valid_after"]) + "."))
        else:
            rows.append(widgets.StatusRow(
                "fail", "Certificate is expired or not valid yet",
                "Valid from " + formatting.format_date(certificate["not_valid_before"])
                + " until " + formatting.format_date(certificate["not_valid_after"]) + "."))

        # 4. Can the certificate chain be trusted?
        trust = signature["trust"]

        if trust["trusted"]:
            rows.append(widgets.StatusRow("pass", "Certificate chain is trusted", trust["explanation"]))
        elif not signature["signature_valid"]:
            rows.append(widgets.StatusRow("unknown", "Trust was not evaluated", trust["explanation"]))
        else:
            rows.append(widgets.StatusRow("warn", "Certificate is not trusted", trust["explanation"]))

        # 5. Revocation (always honest about what was and was not checked).
        revocation = signature["revocation"]

        if revocation["revoked"]:
            rows.append(widgets.StatusRow("fail", "Certificate is revoked", revocation["explanation"]))
        else:
            rows.append(widgets.StatusRow("unknown", "Revocation was not checked", revocation["explanation"]))

        return rows

    def build_explanation_panel(self):
        explanation_text = (
            "A certificate says \"this public key belongs to this name\". A self-signed certificate "
            "is signed by its own owner, so nobody else has vouched for the name inside it: anyone "
            "can create one with any name. A certificate issued by a trusted certificate authority "
            "is different, because the authority checked who the owner is before signing it.\n\n"
            "That is why a valid signature is not the same as a trusted signer. Signet only calls a "
            "certificate trusted when you have added it, or the certificate that issued it, to your "
            "trusted list."
        )
        body_label = widgets.make_label(explanation_text, "body", color=theme.MUTE, wrap=True)

        return widgets.ExpandablePanel(
            "Self-signed and authority-issued certificates", "", body_label)

    # ------------------------------------------------------------------
    # Trusting a certificate
    # ------------------------------------------------------------------

    def trust_certificate_of_sender(self):
        certificate_pem = self.sender().certificate_pem
        certificate = certificate_generator.load_certificate_from_pem(certificate_pem.encode("ascii"))
        details = certificate_generator.describe_certificate(certificate)

        answer = QMessageBox.question(
            self, "Trust this certificate?",
            "Only trust a certificate if you are sure it belongs to \"" + details["common_name"] + "\", "
            "for example because that person or organisation gave you its fingerprint directly.\n\n"
            "SHA-256 fingerprint:\n" + formatting.split_fingerprint_in_two_lines(details["fingerprint_sha256"])
            + "\n\nTrust it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        trust_store.add_trusted_certificate(certificate)

        # Check the same file again, now that the trusted list has changed.
        self.verify_file(self.pdf_path, record_in_activity=False)
