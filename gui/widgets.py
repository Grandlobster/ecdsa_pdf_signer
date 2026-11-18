"""
widgets.py

Reusable interface pieces: buttons, cards, drop zone, expandable panels,
progress steps and the certificate details view.
Animations are short and calm: they only show what has changed.
"""

from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import formatting
import icons
import theme


UNLIMITED_HEIGHT = 16777215


# ----------------------------------------------------------------------
# Labels and small helpers
# ----------------------------------------------------------------------

def make_label(text, kind="body", color=None, wrap=False):
    # Create a label in one of the standard text styles.
    label = QLabel(text)
    text_color = theme.INK

    if kind == "title":
        label.setFont(theme.make_font("serif", 44))
    elif kind == "subtitle":
        label.setFont(theme.make_font("serif", 30))
    elif kind == "number":
        label.setFont(theme.make_font("serif", 64))
    elif kind == "heading":
        label.setFont(theme.make_font("sans", 16, QFont.Weight.DemiBold))
    elif kind == "strong":
        label.setFont(theme.make_font("sans", 14, QFont.Weight.DemiBold))
    elif kind == "mute":
        label.setFont(theme.make_font("sans", 13))
        text_color = theme.MUTE
    elif kind == "mono":
        label.setFont(theme.make_font("mono", 12))
    else:
        label.setFont(theme.make_font("sans", 14))

    if color is not None:
        text_color = color

    label.setStyleSheet("color: " + text_color + "; background: transparent;")
    label.setWordWrap(wrap)

    return label


def make_icon_label(icon_name, size_in_pixels, color_hex):
    label = QLabel()
    label.setPixmap(icons.make_pixmap(icon_name, size_in_pixels, color_hex))
    label.setFixedSize(size_in_pixels, size_in_pixels)
    label.setStyleSheet("background: transparent;")

    return label


def make_divider():
    # A thin horizontal line.
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background: " + theme.LINE + ";")

    return line


def clear_layout(layout):
    # Remove and delete everything inside a layout.
    while layout.count() > 0:
        layout_item = layout.takeAt(0)
        child_widget = layout_item.widget()

        if child_widget is not None:
            child_widget.setParent(None)
            child_widget.deleteLater()


class FadeIn(QPropertyAnimation):
    # Fades a widget from invisible to visible, then removes the effect again
    # so the widget is drawn normally afterwards.
    def __init__(self, widget, duration_in_milliseconds=240):
        self.opacity_effect = QGraphicsOpacityEffect(widget)
        self.opacity_effect.setOpacity(0.0)
        widget.setGraphicsEffect(self.opacity_effect)

        super().__init__(self.opacity_effect, b"opacity", widget)
        self.target_widget = widget
        self.setDuration(duration_in_milliseconds)
        self.setStartValue(0.0)
        self.setEndValue(1.0)
        self.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.finished.connect(self.remove_effect)

    def remove_effect(self):
        self.target_widget.setGraphicsEffect(None)


def fade_in(widget, duration_in_milliseconds=240):
    widget.fade_animation = FadeIn(widget, duration_in_milliseconds)
    widget.fade_animation.start()


# ----------------------------------------------------------------------
# Button
# ----------------------------------------------------------------------

class SoftButton(QPushButton):
    # A button with a gentle hover and press animation.
    # button_style: "primary" (black), "secondary" (outlined) or "quiet" (text only).
    def __init__(self, text, button_style="primary", parent=None):
        super().__init__(text, parent)
        self.button_style = button_style
        self.hover_value = 0.0
        self.press_value = 0.0
        self.show_focus_ring = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setFont(theme.make_font("sans", 14, QFont.Weight.Medium))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.hover_animation = QPropertyAnimation(self, b"hoverAmount", self)
        self.hover_animation.setDuration(160)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.press_animation = QPropertyAnimation(self, b"pressAmount", self)
        self.press_animation.setDuration(90)

    def get_hover_amount(self):
        return self.hover_value

    def set_hover_amount(self, new_value):
        self.hover_value = new_value
        self.update()

    def get_press_amount(self):
        return self.press_value

    def set_press_amount(self, new_value):
        self.press_value = new_value
        self.update()

    hoverAmount = Property(float, get_hover_amount, set_hover_amount)
    pressAmount = Property(float, get_press_amount, set_press_amount)

    def start_hover_animation(self, target_value):
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_value)
        self.hover_animation.setEndValue(target_value)
        self.hover_animation.start()

    def start_press_animation(self, target_value):
        self.press_animation.stop()
        self.press_animation.setStartValue(self.press_value)
        self.press_animation.setEndValue(target_value)
        self.press_animation.start()

    def enterEvent(self, event):
        self.start_hover_animation(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.start_hover_animation(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.start_press_animation(1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.start_press_animation(0.0)
        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        self.show_focus_ring = theme.focus_reason_shows_ring(event.reason())
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.show_focus_ring = False
        self.update()
        super().focusOutEvent(event)

    def sizeHint(self):
        # Wide enough for the text, with comfortable padding on both sides.
        text_width = self.fontMetrics().horizontalAdvance(self.text())

        return QSize(text_width + 44, 42)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # The button shrinks by one pixel while it is pressed.
        shrink = 0.5 + self.press_value * 1.0
        button_rectangle = QRectF(self.rect()).adjusted(shrink, shrink, -shrink, -shrink)

        if not self.isEnabled():
            fill_color = theme.WASH
            border_color = theme.WASH
            text_color = theme.FAINT
        elif self.button_style == "primary":
            fill_color = theme.mix_colors(theme.INK, "#3A3A3A", self.hover_value)
            border_color = fill_color
            text_color = theme.PAPER
        elif self.button_style == "secondary":
            fill_color = theme.mix_colors(theme.PAPER, theme.WASH, self.hover_value)
            border_color = theme.mix_colors(theme.LINE, theme.INK, self.hover_value)
            text_color = theme.INK
        else:
            fill_color = theme.mix_colors(theme.PAPER, theme.WASH, self.hover_value)
            border_color = fill_color
            text_color = theme.INK

        painter.setBrush(QColor(fill_color))
        painter.setPen(QPen(QColor(border_color), 1))
        painter.drawRoundedRect(button_rectangle, theme.CORNER_RADIUS, theme.CORNER_RADIUS)

        if self.show_focus_ring and self.isEnabled():
            focus_pen = QPen(QColor(theme.INK), 1.5)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                button_rectangle.adjusted(-2, -2, 2, 2), theme.CORNER_RADIUS + 2, theme.CORNER_RADIUS + 2
            )

        painter.setPen(QColor(text_color))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


# ----------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------

class HoverCard(QFrame):
    # A bordered card. When clickable, the border darkens on hover.
    clicked = Signal()

    def __init__(self, clickable=False, parent=None):
        super().__init__(parent)
        self.clickable = clickable
        self.hover_value = 0.0
        self.show_focus_ring = False

        self.hover_animation = QPropertyAnimation(self, b"hoverAmount", self)
        self.hover_animation.setDuration(180)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def get_hover_amount(self):
        return self.hover_value

    def set_hover_amount(self, new_value):
        self.hover_value = new_value
        self.update()

    hoverAmount = Property(float, get_hover_amount, set_hover_amount)

    def start_hover_animation(self, target_value):
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_value)
        self.hover_animation.setEndValue(target_value)
        self.hover_animation.start()

    def enterEvent(self, event):
        if self.clickable:
            self.start_hover_animation(1.0)

        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.clickable:
            self.start_hover_animation(0.0)

        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        inside_card = self.rect().contains(event.position().toPoint())

        if self.clickable and inside_card and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        self.show_focus_ring = theme.focus_reason_shows_ring(event.reason())
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.show_focus_ring = False
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        pressed_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)

        if self.clickable and pressed_enter:
            self.clicked.emit()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill_color = theme.mix_colors(theme.PAPER, theme.WASH, self.hover_value * 0.6)
        border_color = theme.mix_colors(theme.LINE, theme.INK, self.hover_value)

        if self.show_focus_ring:
            border_color = theme.INK

        painter.setBrush(QColor(fill_color))
        painter.setPen(QPen(QColor(border_color), 1))
        card_rectangle = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(card_rectangle, theme.CORNER_RADIUS, theme.CORNER_RADIUS)
        painter.end()


class Notice(QFrame):
    # A short message box. kind: "info", "warning" or "error".
    # Colour is never used. Warnings get a heavy border, errors a dashed one.
    def __init__(self, message_text, kind="info", parent=None):
        super().__init__(parent)
        self.setObjectName("notice")

        if kind == "error":
            border_style = "1px dashed " + theme.INK
            icon_name = "cross"
        elif kind == "warning":
            border_style = "1px solid " + theme.INK
            icon_name = "warning"
        else:
            border_style = "1px solid " + theme.LINE
            icon_name = "info"

        self.setStyleSheet(
            "QFrame#notice { border: " + border_style + "; border-radius: "
            + str(theme.CORNER_RADIUS) + "px; background: " + theme.PAPER + "; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_label = make_icon_label(icon_name, 20, theme.INK)
        self.message_label = make_label(message_text, "body", wrap=True)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.message_label, 1)

    def set_message(self, message_text):
        self.message_label.setText(message_text)


# ----------------------------------------------------------------------
# Status rows (used by the verification results)
# ----------------------------------------------------------------------

class StatusBadge(QWidget):
    # A round marker. state: "pass", "fail", "warn" or "unknown".
    #   pass    solid black circle with a tick
    #   fail    dashed circle with a cross
    #   warn    solid thin circle with an exclamation mark
    #   unknown grey circle with a dash
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setFixedSize(26, 26)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        circle_rectangle = QRectF(1.5, 1.5, 23, 23)

        if self.state == "pass":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.INK))
            painter.drawEllipse(circle_rectangle)
            painter.drawPixmap(5, 5, icons.make_pixmap("check", 16, theme.PAPER, 2.2))

        elif self.state == "fail":
            dashed_pen = QPen(QColor(theme.INK), 1.4, Qt.PenStyle.DashLine)
            painter.setPen(dashed_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle_rectangle)
            painter.drawPixmap(5, 5, icons.make_pixmap("cross", 16, theme.INK, 2.0))

        elif self.state == "warn":
            painter.setPen(QPen(QColor(theme.INK), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle_rectangle)
            painter.drawPixmap(5, 5, icons.make_pixmap("exclaim", 16, theme.INK, 2.2))

        else:
            painter.setPen(QPen(QColor(theme.FAINT), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle_rectangle)
            painter.drawPixmap(5, 5, icons.make_pixmap("minus", 16, theme.FAINT, 2.0))

        painter.end()


class StatusRow(QWidget):
    # One line of a result: badge, a short title and a longer explanation.
    def __init__(self, state, title_text, detail_text, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(14)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.addWidget(make_label(title_text, "strong", wrap=True))
        text_column.addWidget(make_label(detail_text, "mute", wrap=True))

        layout.addWidget(StatusBadge(state), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_column, 1)


# ----------------------------------------------------------------------
# Key / value lists and expandable panels
# ----------------------------------------------------------------------

def build_key_value_widget(rows):
    # rows is a list of (label, value, use_monospace_font) tuples.
    container = QWidget()
    grid = QGridLayout(container)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(24)
    grid.setVerticalSpacing(10)
    grid.setColumnMinimumWidth(0, 150)
    grid.setColumnStretch(1, 1)

    row_number = 0

    for label_text, value_text, use_monospace in rows:
        label = make_label(label_text, "mute")
        label.setAlignment(Qt.AlignmentFlag.AlignTop)

        if use_monospace:
            value_label = make_label(value_text, "mono")
        else:
            value_label = make_label(value_text, "body", wrap=True)

        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        grid.addWidget(label, row_number, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value_label, row_number, 1)
        row_number = row_number + 1

    return container


class PanelHeader(QWidget):
    # The clickable top line of an expandable panel.
    clicked = Signal()

    def __init__(self, title_text, summary_text, parent=None):
        super().__init__(parent)
        self.title_text = title_text
        self.summary_text = summary_text
        self.chevron_value = 0.0
        self.hover_value = 0.0
        self.show_focus_ring = False

        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.chevron_animation = QPropertyAnimation(self, b"chevronAmount", self)
        self.chevron_animation.setDuration(220)
        self.chevron_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_chevron_amount(self):
        return self.chevron_value

    def set_chevron_amount(self, new_value):
        self.chevron_value = new_value
        self.update()

    chevronAmount = Property(float, get_chevron_amount, set_chevron_amount)

    def turn_chevron(self, expanded):
        self.chevron_animation.stop()
        self.chevron_animation.setStartValue(self.chevron_value)

        if expanded:
            self.chevron_animation.setEndValue(1.0)
        else:
            self.chevron_animation.setEndValue(0.0)

        self.chevron_animation.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        self.show_focus_ring = theme.focus_reason_shows_ring(event.reason())
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.show_focus_ring = False
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setFont(theme.make_font("sans", 14, QFont.Weight.DemiBold))
        painter.setPen(QColor(theme.INK))
        painter.drawText(self.rect().adjusted(0, 0, -40, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.title_text)

        painter.setFont(theme.make_font("sans", 13))
        painter.setPen(QColor(theme.MUTE))
        painter.drawText(self.rect().adjusted(0, 0, -40, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.summary_text)

        # The chevron turns upside down when the panel opens.
        painter.save()
        painter.translate(self.width() - 12, self.height() / 2)
        painter.rotate(180 * self.chevron_value)
        painter.drawPixmap(-9, -9, icons.make_pixmap("chevron_down", 18, theme.INK, 1.8))
        painter.restore()

        if self.show_focus_ring:
            painter.setPen(QPen(QColor(theme.INK), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(-4, 4, 4, -4), 6, 6)

        painter.end()


class ExpandablePanel(QFrame):
    # A panel that opens and closes smoothly. Only a thin line separates panels.
    def __init__(self, title_text, summary_text, body_widget, start_expanded=False, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setStyleSheet(
            "QFrame#panel { border: none; border-bottom: 1px solid " + theme.LINE + "; background: transparent; }"
        )
        self.is_expanded = start_expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = PanelHeader(title_text, summary_text)
        self.header.clicked.connect(self.toggle)

        self.body_container = QWidget()
        body_layout = QVBoxLayout(self.body_container)
        body_layout.setContentsMargins(0, 2, 0, 20)
        body_layout.addWidget(body_widget)

        layout.addWidget(self.header)
        layout.addWidget(self.body_container)

        self.height_animation = QPropertyAnimation(self.body_container, b"maximumHeight", self)
        self.height_animation.setDuration(260)
        self.height_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.height_animation.finished.connect(self.finish_animation)

        if start_expanded:
            self.header.chevron_value = 1.0
        else:
            self.body_container.setMaximumHeight(0)

    def measure_body_height(self):
        # Work out how tall the content needs to be at the current width.
        available_width = self.width()

        if available_width < 100:
            available_width = 640

        body_layout = self.body_container.layout()

        if body_layout.hasHeightForWidth():
            return body_layout.totalHeightForWidth(available_width)

        return body_layout.sizeHint().height()

    def toggle(self):
        self.height_animation.stop()
        self.is_expanded = not self.is_expanded
        self.header.turn_chevron(self.is_expanded)

        current_height = self.body_container.height()

        if self.is_expanded:
            self.body_container.setMaximumHeight(current_height)
            self.height_animation.setStartValue(current_height)
            self.height_animation.setEndValue(self.measure_body_height())
        else:
            self.body_container.setMaximumHeight(current_height)
            self.height_animation.setStartValue(current_height)
            self.height_animation.setEndValue(0)

        self.height_animation.start()

    def finish_animation(self):
        # Once fully open, let the content size itself again (for window resizing).
        if self.is_expanded:
            self.body_container.setMaximumHeight(UNLIMITED_HEIGHT)


class CertificateDetailsView(QWidget):
    # The certificate shown as four expandable panels.
    # "certificate" is the dictionary made by certificate_generator.describe_certificate().
    def __init__(self, certificate, first_panel_open=False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if certificate["is_self_signed"]:
            certificate_type = "Self-signed (not issued by a certificate authority)"
        else:
            certificate_type = "Issued by another certificate"

        key_usage_text = ", ".join(certificate["key_usages"])

        if key_usage_text == "":
            key_usage_text = "Not specified"

        identity_rows = [
            ("Subject name", certificate["subject"], False),
            ("Issuer", certificate["issuer"], False),
            ("Serial number", certificate["serial_number"], True),
            ("Certificate type", certificate_type, False),
            ("X.509 version", certificate["version"], False),
        ]

        validity_rows = [
            ("Valid from", formatting.format_date_time(certificate["not_valid_before"]), False),
            ("Valid until", formatting.format_date_time(certificate["not_valid_after"]), False),
            ("Status today", formatting.describe_validity(certificate), False),
        ]

        if certificate["key_size_bits"]:
            key_size_text = str(certificate["key_size_bits"]) + " bits"
        else:
            key_size_text = "Not available"

        key_rows = [
            ("Public-key algorithm", certificate["public_key_algorithm"], False),
            ("Elliptic curve", certificate["curve"], False),
            ("Key size", key_size_text, False),
            ("Signature algorithm", certificate["signature_algorithm"], False),
            ("Key usage", key_usage_text, False),
        ]

        fingerprint_rows = [
            ("SHA-256", formatting.split_fingerprint_in_two_lines(certificate["fingerprint_sha256"]), True),
        ]

        if certificate["curve"] == "Not applicable":
            key_summary = certificate["public_key_algorithm"]
        else:
            key_summary = "ECDSA " + certificate["curve"].split(" ")[0]

        layout.addWidget(ExpandablePanel(
            "Subject and issuer", certificate["common_name"],
            build_key_value_widget(identity_rows), first_panel_open))
        layout.addWidget(ExpandablePanel(
            "Validity period", formatting.describe_validity(certificate),
            build_key_value_widget(validity_rows)))
        layout.addWidget(ExpandablePanel(
            "Public key and signature", key_summary,
            build_key_value_widget(key_rows)))
        layout.addWidget(ExpandablePanel(
            "Fingerprint", formatting.short_fingerprint(certificate["fingerprint_sha256"]),
            build_key_value_widget(fingerprint_rows)))


# ----------------------------------------------------------------------
# Drop zone
# ----------------------------------------------------------------------

class DropZone(QFrame):
    # Drag a PDF here or click to browse. The border reacts while a file hovers over it.
    file_chosen = Signal(str)

    def __init__(self, prompt_text, hint_text, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(150)
        self.show_focus_ring = False
        self.highlight_value = 0.0
        self.prompt_text = prompt_text
        self.hint_text = hint_text

        self.highlight_animation = QPropertyAnimation(self, b"highlightAmount", self)
        self.highlight_animation.setDuration(180)
        self.highlight_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self.icon_label = make_icon_label("upload", 28, theme.INK)
        self.prompt_label = make_label(prompt_text, "strong")
        self.hint_label = make_label(hint_text, "mute")

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(6)
        layout.addWidget(self.prompt_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.hint_label, 0, Qt.AlignmentFlag.AlignHCenter)

    def get_highlight_amount(self):
        return self.highlight_value

    def set_highlight_amount(self, new_value):
        self.highlight_value = new_value
        self.update()

    highlightAmount = Property(float, get_highlight_amount, set_highlight_amount)

    def start_highlight_animation(self, target_value):
        self.highlight_animation.stop()
        self.highlight_animation.setStartValue(self.highlight_value)
        self.highlight_animation.setEndValue(target_value)
        self.highlight_animation.start()

    def show_chosen_file(self, file_name, detail_text):
        # After a file is picked, the zone shows its name and size.
        self.icon_label.setPixmap(icons.make_pixmap("file", 28, theme.INK))
        self.prompt_label.setText(file_name)
        self.hint_label.setText(detail_text + ". Click or drop another PDF to replace it.")

    def clear_chosen_file(self):
        self.icon_label.setPixmap(icons.make_pixmap("upload", 28, theme.INK))
        self.prompt_label.setText(self.prompt_text)
        self.hint_label.setText(self.hint_text)

    def browse_for_file(self):
        chosen_path, selected_filter = QFileDialog.getOpenFileName(
            self, "Choose a PDF document", "", "PDF documents (*.pdf);;All files (*)"
        )

        if chosen_path != "":
            self.file_chosen.emit(chosen_path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.browse_for_file()

        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        self.show_focus_ring = theme.focus_reason_shows_ring(event.reason())
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.show_focus_ring = False
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.browse_for_file()
            return

        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            event.acceptProposedAction()
            self.start_highlight_animation(1.0)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.start_highlight_animation(0.0)

    def dropEvent(self, event):
        self.start_highlight_animation(0.0)
        dropped_urls = event.mimeData().urls()

        if len(dropped_urls) == 1 and dropped_urls[0].isLocalFile():
            event.acceptProposedAction()
            self.file_chosen.emit(dropped_urls[0].toLocalFile())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill_color = theme.mix_colors(theme.PAPER, theme.WASH, self.highlight_value)
        border_color = theme.mix_colors(theme.FAINT, theme.INK, self.highlight_value)

        if self.show_focus_ring:
            border_color = theme.INK

        # The dashed border becomes solid while a file is held over the zone.
        if self.highlight_value > 0.5:
            border_pen = QPen(QColor(border_color), 1.5)
        else:
            border_pen = QPen(QColor(border_color), 1.2, Qt.PenStyle.DashLine)

        painter.setBrush(QColor(fill_color))
        painter.setPen(border_pen)
        zone_rectangle = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(zone_rectangle, theme.CORNER_RADIUS, theme.CORNER_RADIUS)
        painter.end()


# ----------------------------------------------------------------------
# Progress
# ----------------------------------------------------------------------

class ProgressTrack(QWidget):
    # A thin bar that grows smoothly towards its target.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self.fraction_value = 0.0

        self.fraction_animation = QPropertyAnimation(self, b"fraction", self)
        self.fraction_animation.setDuration(320)
        self.fraction_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_fraction(self):
        return self.fraction_value

    def set_fraction(self, new_value):
        self.fraction_value = new_value
        self.update()

    fraction = Property(float, get_fraction, set_fraction)

    def move_to(self, target_fraction):
        self.fraction_animation.stop()
        self.fraction_animation.setStartValue(self.fraction_value)
        self.fraction_animation.setEndValue(target_fraction)
        self.fraction_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor(theme.LINE))
        painter.drawRoundedRect(QRectF(self.rect()), 1.5, 1.5)

        painter.setBrush(QColor(theme.INK))
        filled_width = self.width() * self.fraction_value
        painter.drawRoundedRect(QRectF(0, 0, filled_width, self.height()), 1.5, 1.5)
        painter.end()


class StepProgress(QWidget):
    # Shows the real stages of an operation, for example while signing.
    def __init__(self, step_names, parent=None):
        super().__init__(parent)
        self.step_names = step_names
        self.icon_labels = []
        self.text_labels = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.track = ProgressTrack()
        layout.addWidget(self.track)
        layout.addSpacing(4)

        for step_name in step_names:
            row = QHBoxLayout()
            row.setSpacing(10)

            icon_label = QLabel()
            icon_label.setFixedSize(18, 18)
            text_label = make_label(step_name, "body", color=theme.FAINT)

            row.addWidget(icon_label)
            row.addWidget(text_label, 1)
            layout.addLayout(row)

            self.icon_labels.append(icon_label)
            self.text_labels.append(text_label)

    def show_step(self, active_index):
        # Steps before the active one are done, the active one is highlighted.
        for position in range(len(self.step_names)):
            icon_label = self.icon_labels[position]
            text_label = self.text_labels[position]

            if position < active_index:
                icon_label.setPixmap(icons.make_pixmap("check", 18, theme.INK, 2.0))
                text_label.setStyleSheet("color: " + theme.MUTE + "; background: transparent;")
            elif position == active_index:
                icon_label.setPixmap(icons.make_pixmap("dot", 18, theme.INK))
                text_label.setStyleSheet("color: " + theme.INK + "; background: transparent;")
            else:
                icon_label.clear()
                text_label.setStyleSheet("color: " + theme.FAINT + "; background: transparent;")

        self.track.move_to(active_index / len(self.step_names))

    def show_all_done(self):
        for position in range(len(self.step_names)):
            self.icon_labels[position].setPixmap(icons.make_pixmap("check", 18, theme.INK, 2.0))
            self.text_labels[position].setStyleSheet("color: " + theme.MUTE + "; background: transparent;")

        self.track.move_to(1.0)

    def reset(self):
        for position in range(len(self.step_names)):
            self.icon_labels[position].clear()
            self.text_labels[position].setStyleSheet("color: " + theme.FAINT + "; background: transparent;")

        self.track.fraction_animation.stop()
        self.track.set_fraction(0.0)
