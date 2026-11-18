"""
main_window.py

The main window: a slim navigation column on the left and the pages on the right.
Pages fade in when you switch, and a black marker slides between navigation items.
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QPainter, QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

import icons
import theme
import widgets
from page_certificates import CertificatesPage
from page_dashboard import DashboardPage
from page_keys import KeysPage
from page_sign import SignPage
from page_verify import VerifyPage


NAVIGATION_ITEMS = [
    ("dashboard", "Dashboard", "grid"),
    ("keys", "Key generation", "key"),
    ("sign", "Sign PDF", "pen"),
    ("verify", "Verify PDF", "shield"),
    ("certificates", "Certificates", "certificate"),
]

SIDEBAR_WIDTH = 236
NAV_BUTTON_HEIGHT = 44


class NavigationButton(QPushButton):
    def __init__(self, page_name, label_text, icon_name, parent=None):
        super().__init__(parent)
        self.page_name = page_name
        self.label_text = label_text
        self.icon_name = icon_name
        self.is_current = False
        self.hovered = False
        self.show_focus_ring = False

        self.setFixedHeight(NAV_BUTTON_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(label_text)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.show_focus_ring = theme.focus_reason_shows_ring(event.reason())
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.show_focus_ring = False
        self.update()
        super().focusOutEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.is_current:
            text_color = theme.INK
            icon_color = theme.INK
            font = theme.make_font("sans", 14, QFont.Weight.DemiBold)
        elif self.hovered:
            text_color = theme.INK
            icon_color = theme.INK
            font = theme.make_font("sans", 14)
        else:
            text_color = theme.MUTE
            icon_color = theme.MUTE
            font = theme.make_font("sans", 14)

        painter.drawPixmap(26, int((self.height() - 20) / 2), icons.make_pixmap(self.icon_name, 20, icon_color))
        painter.setFont(font)
        painter.setPen(QColor(text_color))
        text_rectangle = QRect(60, 0, self.width() - 60, self.height())
        painter.drawText(text_rectangle, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.label_text)

        if self.show_focus_ring:
            painter.setPen(QColor(theme.INK))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRect(14, 2, self.width() - 28, self.height() - 4), 6, 6)

        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signet - ECDSA PDF Signer")
        self.setMinimumSize(1040, 700)
        self.resize(1240, 820)

        background = QWidget()
        background.setObjectName("window_background")
        self.setCentralWidget(background)

        root_layout = QHBoxLayout(background)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.build_sidebar())

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background: " + theme.LINE + ";")
        root_layout.addWidget(divider)

        self.page_stack = QStackedWidget()
        root_layout.addWidget(self.page_stack, 1)

        self.pages = {}
        self.page_order = []
        self.add_page("dashboard", DashboardPage())
        self.add_page("keys", KeysPage())
        self.add_page("sign", SignPage())
        self.add_page("verify", VerifyPage())
        self.add_page("certificates", CertificatesPage())

        self.pages["sign"].verify_file_requested.connect(self.verify_file_from_sign_page)

        self.current_page_name = ""
        self.marker_animation = None
        self.show_page("dashboard", animate=False)

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet("QWidget#sidebar { background: #FFFFFF; }")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 40, 0, 32)
        layout.setSpacing(0)

        brand_column = QVBoxLayout()
        brand_column.setContentsMargins(28, 0, 20, 0)
        brand_column.setSpacing(2)
        brand_column.addWidget(widgets.make_label("Signet", "subtitle"))
        brand_column.addWidget(widgets.make_label("PDF signatures", "mute"))
        layout.addLayout(brand_column)
        layout.addSpacing(44)

        self.navigation_buttons = {}
        self.navigation_container = QWidget()
        navigation_layout = QVBoxLayout(self.navigation_container)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(4)

        for page_name, label_text, icon_name in NAVIGATION_ITEMS:
            button = NavigationButton(page_name, label_text, icon_name)
            button.clicked.connect(self.open_page_of_sender)
            navigation_layout.addWidget(button)
            self.navigation_buttons[page_name] = button

        layout.addWidget(self.navigation_container)

        # A thin black marker that slides to the current item.
        self.marker = QFrame(self.navigation_container)
        self.marker.setStyleSheet("background: " + theme.INK + "; border-radius: 1px;")
        self.marker.setGeometry(0, 0, 3, 20)
        self.marker.raise_()

        layout.addStretch(1)

        footer_column = QVBoxLayout()
        footer_column.setContentsMargins(28, 0, 20, 0)
        footer_column.setSpacing(2)
        footer_column.addWidget(widgets.make_label("ECDSA P-256, SHA-256", "mute"))
        footer_column.addWidget(widgets.make_label("PAdES / CMS signatures", "mute"))
        footer_column.addWidget(widgets.make_label("Works offline", "mute"))
        layout.addLayout(footer_column)

        return sidebar

    def add_page(self, page_name, page):
        page.navigate_requested.connect(self.show_page_without_animation_flag)
        self.pages[page_name] = page
        self.page_order.append(page_name)
        self.page_stack.addWidget(page)

    # ------------------------------------------------------------------
    # Switching pages
    # ------------------------------------------------------------------

    def open_page_of_sender(self):
        self.show_page(self.sender().page_name)

    def show_page_without_animation_flag(self, page_name):
        self.show_page(page_name)

    def verify_file_from_sign_page(self, pdf_path):
        self.show_page("verify")
        self.pages["verify"].verify_file(pdf_path, record_in_activity=True)

    def show_page(self, page_name, animate=True):
        if page_name == self.current_page_name:
            return

        self.current_page_name = page_name
        page = self.pages[page_name]
        page.refresh()
        self.page_stack.setCurrentWidget(page)

        for name in self.navigation_buttons:
            button = self.navigation_buttons[name]
            button.is_current = (name == page_name)
            button.update()

        self.move_marker(animate)

        if animate:
            widgets.fade_in(page, 260)

    def move_marker(self, animate):
        button = self.navigation_buttons[self.current_page_name]
        target_rectangle = QRect(0, button.y() + int((NAV_BUTTON_HEIGHT - 20) / 2), 3, 20)

        if not animate or not self.isVisible():
            self.marker.setGeometry(target_rectangle)
            return

        self.marker_animation = QPropertyAnimation(self.marker, b"geometry", self)
        self.marker_animation.setDuration(320)
        self.marker_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.marker_animation.setStartValue(self.marker.geometry())
        self.marker_animation.setEndValue(target_rectangle)
        self.marker_animation.start()

    def showEvent(self, event):
        super().showEvent(event)

        # The buttons only have their final positions once the window is visible.
        if self.current_page_name != "":
            self.move_marker(False)
