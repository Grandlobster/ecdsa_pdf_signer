"""
page_base.py

The common frame of every page: a scrolling area with a large title,
a short description and a content column that is never wider than 920 pixels.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

import widgets


class BasePage(QScrollArea):
    # Pages ask the main window to switch to another page with this signal.
    navigate_requested = Signal(str)

    def __init__(self, title_text, subtitle_text, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        surface = QWidget()
        surface.setObjectName("page_surface")
        surface.setStyleSheet("QWidget#page_surface { background: #FFFFFF; }")
        self.setWidget(surface)

        outer_layout = QHBoxLayout(surface)
        outer_layout.setContentsMargins(56, 48, 56, 64)
        outer_layout.setSpacing(0)

        self.content = QWidget()
        self.content.setMaximumWidth(920)
        outer_layout.addWidget(self.content, 1, Qt.AlignmentFlag.AlignTop)
        outer_layout.addStretch(0)

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.title_label = widgets.make_label(title_text, "title")
        self.subtitle_label = widgets.make_label(subtitle_text, "mute", wrap=True)
        self.subtitle_label.setMaximumWidth(620)

        self.content_layout.addWidget(self.title_label)
        self.content_layout.addSpacing(10)
        self.content_layout.addWidget(self.subtitle_label)
        self.content_layout.addSpacing(40)

    def refresh(self):
        # Called every time the page is shown. Pages override this to reload their data.
        pass
