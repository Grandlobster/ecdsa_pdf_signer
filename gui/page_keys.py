"""
page_keys.py

Key generation: create an ECDSA P-256 key pair with an X.509 certificate,
and list the identities that already exist.
Clicking an identity card opens its detailed view (it grows out of the card).
"""

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRect, QUrl
from PySide6.QtGui import QDesktopServices, QIntValidator
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import certificate_generator
import folders
import formatting
import identity_storage
import theme
import widgets
import tasks
from identity_detail import IdentityDetailView
from page_base import BasePage


class IdentityCard(widgets.HoverCard):
    # One saved identity in the list. Clicking it opens the detailed view.
    def __init__(self, summary, parent=None):
        super().__init__(clickable=True, parent=parent)
        self.identity_id = summary["identity_id"]
        certificate = summary["certificate"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        if summary["password_protected"]:
            lock_icon = "lock"
        else:
            lock_icon = "warning"

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.addWidget(widgets.make_label(summary["common_name"], "strong"))
        text_column.addWidget(widgets.make_label(formatting.short_fingerprint(certificate["fingerprint_sha256"]), "mono", color=theme.MUTE))
        text_column.addWidget(widgets.make_label(formatting.describe_validity(certificate), "mute"))

        if summary["is_trusted"]:
            trust_text = "Trusted"
        else:
            trust_text = "Not trusted"

        layout.addWidget(widgets.make_icon_label("key", 24, theme.INK), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_column, 1)

        side_column = QVBoxLayout()
        side_column.setSpacing(6)
        side_column.addWidget(widgets.make_icon_label(lock_icon, 18, theme.INK), 0, Qt.AlignmentFlag.AlignRight)
        side_column.addWidget(widgets.make_label(trust_text, "mute"), 0, Qt.AlignmentFlag.AlignRight)
        side_column.addStretch(1)
        layout.addLayout(side_column)


class KeysPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Key generation",
            "Create a signing identity: a private key, its public key and a certificate that names you.",
            parent,
        )
        self.task_thread = None
        self.detail_view = None
        self.detail_animation = None

        self.content_layout.addWidget(widgets.Notice(
            "Your private key is what proves your identity. Anyone who has it can sign in your name. "
            "Protect it with a strong password and never share it.", "warning"))
        self.content_layout.addSpacing(32)

        columns = QHBoxLayout()
        columns.setSpacing(48)
        columns.addLayout(self.build_form_column(), 5)
        columns.addLayout(self.build_list_column(), 6)
        self.content_layout.addLayout(columns)
        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Left column: the form
    # ------------------------------------------------------------------

    def build_form_column(self):
        column = QVBoxLayout()
        column.setSpacing(0)
        self.form_column_layout = column

        column.addWidget(widgets.make_label("New identity", "heading"))
        column.addSpacing(14)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name or the name of your organisation")
        self.name_input.setMaxLength(64)
        column.addWidget(self.build_field("Name", self.name_input))

        self.organization_input = QLineEdit()
        self.organization_input.setPlaceholderText("Optional")
        self.organization_input.setMaxLength(64)
        column.addWidget(self.build_field("Organisation", self.organization_input))

        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("Optional, two letters such as IN or US")
        self.country_input.setMaxLength(2)
        column.addWidget(self.build_field("Country", self.country_input))

        self.validity_input = QLineEdit("365")
        self.validity_input.setValidator(QIntValidator(1, certificate_generator.MAXIMUM_VALIDITY_DAYS))
        self.validity_input.setPlaceholderText("Number of days")
        column.addWidget(self.build_field("Valid for (days)", self.validity_input))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("At least 12 characters")
        column.addWidget(self.build_field("Password for the private key", self.password_input))

        self.password_repeat_input = QLineEdit()
        self.password_repeat_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_repeat_input.setPlaceholderText("Type it again")
        column.addWidget(self.build_field("Repeat password", self.password_repeat_input))

        self.unprotected_checkbox = QCheckBox("Store the private key without a password (not recommended)")
        self.unprotected_checkbox.setFont(theme.make_font("sans", 13))
        self.unprotected_checkbox.toggled.connect(self.update_password_fields)
        column.addWidget(self.unprotected_checkbox)
        column.addSpacing(20)

        self.generate_button = widgets.SoftButton("Generate key pair and certificate", "primary")
        self.generate_button.clicked.connect(self.start_generation)
        column.addWidget(self.generate_button)
        column.addSpacing(18)

        self.progress = widgets.StepProgress(tasks.CREATE_IDENTITY_STEPS)
        self.progress.hide()
        column.addWidget(self.progress)
        column.addSpacing(14)

        self.message_notice = widgets.Notice("", "info")
        self.message_notice.hide()
        column.addWidget(self.message_notice)
        column.addSpacing(20)

        self.folder_button = widgets.SoftButton("Open the folder with my keys", "quiet")
        self.folder_button.clicked.connect(self.open_keys_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_button)
        folder_row.addStretch(1)
        column.addLayout(folder_row)
        column.addStretch(1)

        return column

    def build_field(self, label_text, input_widget):
        field = QWidget()
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 16)
        field_layout.setSpacing(6)
        field_layout.addWidget(widgets.make_label(label_text, "mute"))
        field_layout.addWidget(input_widget)

        return field

    def update_password_fields(self, store_without_password):
        # Choosing "no password" switches the two password boxes off.
        self.password_input.setEnabled(not store_without_password)
        self.password_repeat_input.setEnabled(not store_without_password)

        if store_without_password:
            self.password_input.clear()
            self.password_repeat_input.clear()

    # ------------------------------------------------------------------
    # Right column: the list of identities
    # ------------------------------------------------------------------

    def build_list_column(self):
        column = QVBoxLayout()
        column.setSpacing(0)
        column.addWidget(widgets.make_label("Your identities", "heading"))
        column.addSpacing(14)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        column.addWidget(self.list_container)
        column.addStretch(1)

        return column

    def refresh(self):
        widgets.clear_layout(self.list_layout)
        summaries = identity_storage.list_identity_summaries()

        if len(summaries) == 0:
            self.list_layout.addWidget(widgets.make_label(
                "You have no identities yet. Fill in the form to create your first one.",
                "mute", wrap=True))
            return

        for summary in summaries:
            card = IdentityCard(summary)
            card.clicked.connect(self.open_detail_of_sender)
            self.list_layout.addWidget(card)

    def open_keys_folder(self):
        folders.make_sure_folders_exist()
        QDesktopServices.openUrl(QUrl.fromLocalFile(folders.PROJECT_FOLDER))

    # ------------------------------------------------------------------
    # Generating a new identity
    # ------------------------------------------------------------------

    def show_message(self, message_text, kind):
        # Replace the notice under the progress display with a fresh one of the right kind.
        old_notice = self.message_notice
        notice_position = self.form_column_layout.indexOf(old_notice)

        self.form_column_layout.removeWidget(old_notice)
        old_notice.deleteLater()

        self.message_notice = widgets.Notice(message_text, kind)
        self.form_column_layout.insertWidget(notice_position, self.message_notice)
        widgets.fade_in(self.message_notice)

    def start_generation(self):
        password = self.password_input.text()
        repeated_password = self.password_repeat_input.text()
        store_without_password = self.unprotected_checkbox.isChecked()

        if self.name_input.text().strip() == "":
            self.show_message("Enter a name for the identity.", "error")
            return

        if password != repeated_password:
            self.show_message("The two passwords do not match.", "error")
            return

        if password == "" and not store_without_password:
            self.show_message(
                "Choose a password to protect the private key, or tick the box to store it without one.",
                "error")
            return

        try:
            validity_days = int(self.validity_input.text())
        except ValueError:
            self.show_message("Enter how many days the certificate should be valid, for example 365.", "error")
            return

        arguments = (
            self.name_input.text(),
            self.organization_input.text(),
            self.country_input.text(),
            validity_days,
            password,
            store_without_password,
        )

        self.message_notice.hide()
        self.generate_button.setEnabled(False)
        self.progress.reset()
        self.progress.show()

        self.task_thread = tasks.TaskThread(tasks.create_identity_task, arguments)
        self.task_thread.progress_changed.connect(self.progress.show_step)
        self.task_thread.succeeded.connect(self.finish_generation)
        self.task_thread.failed.connect(self.fail_generation)
        self.task_thread.finished.connect(self.forget_task_thread)
        self.task_thread.start()

    def forget_task_thread(self):
        # Qt reports "finished" only when the thread has really stopped.
        # Dropping the thread any earlier would destroy it while it is still running.
        self.task_thread = None
        self.generate_button.setEnabled(True)

    def finish_generation(self, summary):
        self.progress.show_all_done()
        self.password_input.clear()
        self.password_repeat_input.clear()
        self.name_input.clear()
        self.organization_input.clear()
        self.country_input.clear()

        self.show_message(
            "Identity \"" + summary["common_name"] + "\" was created. Open it from the list to see "
            "its certificate or to export it.", "info")
        self.refresh()

    def fail_generation(self, error_message):
        self.progress.hide()
        self.show_message(error_message, "error")

    # ------------------------------------------------------------------
    # The detailed view that grows out of a card
    # ------------------------------------------------------------------

    def open_detail_of_sender(self):
        card = self.sender()

        if self.detail_view is not None:
            return

        self.detail_view = IdentityDetailView(card.identity_id, self)
        self.detail_view.close_requested.connect(self.close_detail)
        self.detail_view.data_changed.connect(self.refresh)

        # Start exactly where the card is, then grow to fill the whole page.
        card_top_left = card.mapTo(self, QPoint(0, 0))
        card_rectangle = QRect(card_top_left, card.size())

        self.detail_view.scroll_area.hide()
        self.detail_view.setGeometry(card_rectangle)
        self.detail_view.show()
        self.detail_view.raise_()

        self.detail_animation = QPropertyAnimation(self.detail_view, b"geometry", self)
        self.detail_animation.setDuration(380)
        self.detail_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.detail_animation.setStartValue(card_rectangle)
        self.detail_animation.setEndValue(self.rect())
        self.detail_animation.finished.connect(self.show_detail_content)
        self.detail_animation.start()

    def show_detail_content(self):
        self.detail_animation.finished.disconnect(self.show_detail_content)
        self.detail_view.scroll_area.show()
        widgets.fade_in(self.detail_view.scroll_area, 220)

    def close_detail(self):
        if self.detail_view is None:
            return

        self.detail_view.scroll_area.hide()

        # Shrink back to the card when it still exists, otherwise just disappear.
        target_rectangle = self.find_card_rectangle(self.detail_view.identity_id)

        if target_rectangle is None:
            self.remove_detail_view()
            return

        self.detail_animation = QPropertyAnimation(self.detail_view, b"geometry", self)
        self.detail_animation.setDuration(300)
        self.detail_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.detail_animation.setStartValue(self.detail_view.geometry())
        self.detail_animation.setEndValue(target_rectangle)
        self.detail_animation.finished.connect(self.remove_detail_view)
        self.detail_animation.start()

    def find_card_rectangle(self, identity_id):
        for position in range(self.list_layout.count()):
            card = self.list_layout.itemAt(position).widget()

            if isinstance(card, IdentityCard) and card.identity_id == identity_id:
                return QRect(card.mapTo(self, QPoint(0, 0)), card.size())

        return None

    def remove_detail_view(self):
        if self.detail_view is not None:
            self.detail_view.hide()
            self.detail_view.deleteLater()
            self.detail_view = None

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # While the detailed view is fully open it always fills the page.
        detail_is_open = self.detail_view is not None
        animation_is_running = (
            self.detail_animation is not None
            and self.detail_animation.state() == QPropertyAnimation.State.Running
        )

        if detail_is_open and not animation_is_running and self.detail_view.scroll_area.isVisible():
            self.detail_view.setGeometry(self.rect())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.detail_view is not None:
            self.close_detail()
            return

        super().keyPressEvent(event)
