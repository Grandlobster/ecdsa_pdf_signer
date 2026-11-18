"""
page_dashboard.py

The first page: how many documents were signed and verified,
two quick actions and a short list of recent activity.
"""

from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import activity_log
import formatting
import identity_storage
import theme
import widgets
from page_base import BasePage


class CountUpLabel(QLabel):
    # A big number that counts up to its value when it appears.
    def __init__(self, parent=None):
        super().__init__("0", parent)
        self.setFont(theme.make_font("serif", 64))
        self.setStyleSheet("color: " + theme.INK + "; background: transparent;")

        self.count_animation = QVariantAnimation(self)
        self.count_animation.setDuration(700)
        self.count_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.count_animation.valueChanged.connect(self.show_number)

    def show_number(self, number):
        self.setText(str(int(number)))

    def count_up_to(self, final_number):
        self.count_animation.stop()
        self.count_animation.setStartValue(0)
        self.count_animation.setEndValue(final_number)
        self.count_animation.start()


class DashboardPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Signet",
            "Digital signatures for PDF documents. Everything is created and checked on this computer.",
            parent,
        )

        # Three numbers side by side, separated by thin vertical lines.
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        self.signed_number = CountUpLabel()
        self.verified_number = CountUpLabel()
        self.identity_number = CountUpLabel()

        stats_row.addWidget(self.build_stat_block(self.signed_number, "Documents signed"), 1)
        stats_row.addWidget(self.build_stat_divider())
        stats_row.addWidget(self.build_stat_block(self.verified_number, "Documents verified", 32), 1)
        stats_row.addWidget(self.build_stat_divider())
        stats_row.addWidget(self.build_stat_block(self.identity_number, "Signing identities", 32), 1)

        self.content_layout.addLayout(stats_row)
        self.content_layout.addSpacing(44)

        # Quick actions.
        action_row = QHBoxLayout()
        action_row.setSpacing(16)

        sign_card = self.build_action_card(
            "pen", "Sign a PDF", "Add a cryptographic signature with one of your identities.", "sign"
        )
        verify_card = self.build_action_card(
            "shield", "Verify a PDF", "Check a signature and whether the file changed after signing.", "verify"
        )

        action_row.addWidget(sign_card)
        action_row.addWidget(verify_card)
        self.content_layout.addLayout(action_row)
        self.content_layout.addSpacing(48)

        # Recent activity.
        self.content_layout.addWidget(widgets.make_label("Recent activity", "heading"))
        self.content_layout.addSpacing(8)

        self.activity_container = QWidget()
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(0, 0, 0, 0)
        self.activity_layout.setSpacing(0)
        self.content_layout.addWidget(self.activity_container)
        self.content_layout.addStretch(1)

    def build_stat_block(self, number_label, caption_text, left_padding=0):
        block = QWidget()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(left_padding, 0, 0, 0)
        block_layout.setSpacing(0)
        block_layout.addWidget(number_label)
        block_layout.addWidget(widgets.make_label(caption_text, "mute"))

        return block

    def build_stat_divider(self):
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background: " + theme.LINE + ";")

        return divider

    def build_action_card(self, icon_name, title_text, description_text, target_page):
        card = widgets.HoverCard(clickable=True)
        card.setMinimumHeight(178)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(4)

        card_layout.addWidget(widgets.make_icon_label(icon_name, 26, theme.INK))
        card_layout.addStretch(1)
        card_layout.addWidget(widgets.make_label(title_text, "subtitle"))
        description_label = widgets.make_label(description_text, "mute", wrap=True)
        description_label.setMinimumHeight(40)
        description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(description_label)

        # Remember which page this card opens, then connect its click.
        card.target_page = target_page
        card.clicked.connect(self.open_target_page_of_sender)

        return card

    def open_target_page_of_sender(self):
        clicked_card = self.sender()
        self.navigate_requested.emit(clicked_card.target_page)

    def build_activity_row(self, entry):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 14, 0, 14)
        row_layout.setSpacing(16)

        if entry["kind"] == "sign":
            icon_name = "pen"
        else:
            icon_name = "shield"

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        text_column.addWidget(widgets.make_label(entry["filename"], "strong"))
        text_column.addWidget(widgets.make_label(entry["result"], "mute"))

        time_label = widgets.make_label(formatting.format_date_time(entry["timestamp"]), "mute")

        row_layout.addWidget(widgets.make_icon_label(icon_name, 20, theme.INK), 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addLayout(text_column, 1)
        row_layout.addWidget(time_label, 0, Qt.AlignmentFlag.AlignTop)

        return row

    def refresh(self):
        activity_summary = activity_log.get_activity_summary(8)
        identity_count = len(identity_storage.list_identity_summaries())

        self.signed_number.count_up_to(activity_summary["signed_total"])
        self.verified_number.count_up_to(activity_summary["verified_total"])
        self.identity_number.count_up_to(identity_count)

        widgets.clear_layout(self.activity_layout)

        recent_entries = activity_summary["recent"]

        if len(recent_entries) == 0:
            empty_message = widgets.make_label(
                "Nothing here yet. Sign or verify a document and it will appear in this list.",
                "mute", wrap=True,
            )
            self.activity_layout.addWidget(widgets.make_divider())
            self.activity_layout.addSpacing(14)
            self.activity_layout.addWidget(empty_message)
            return

        for entry in recent_entries:
            self.activity_layout.addWidget(widgets.make_divider())
            self.activity_layout.addWidget(self.build_activity_row(entry))
