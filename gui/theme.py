"""
theme.py

Colours, fonts and the global style sheet.
The whole interface uses only white, near black, grey and a light line colour.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


PAPER = "#FFFFFF"
INK = "#111111"
MUTE = "#777777"
LINE = "#E5E5E5"
PITCH = "#000000"
WASH = "#F5F5F5"
FAINT = "#B5B5B5"

# One corner radius is used for every card, field and button.
CORNER_RADIUS = 10

SANS_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]
SERIF_FAMILIES = ["Georgia", "Iowan Old Style", "Times New Roman", "DejaVu Serif"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"]


def make_font(kind, pixel_size, weight=QFont.Weight.Normal):
    # Build a font. "kind" is "sans", "serif" or "mono".
    font = QFont()

    if kind == "serif":
        font.setFamilies(SERIF_FAMILIES)
    elif kind == "mono":
        font.setFamilies(MONO_FAMILIES)
    else:
        font.setFamilies(SANS_FAMILIES)

    font.setPixelSize(pixel_size)
    font.setWeight(weight)

    return font


def mix_colors(first_hex, second_hex, amount):
    # Blend two "#RRGGBB" colours. amount 0 gives the first, 1 gives the second.
    first_red = int(first_hex[1:3], 16)
    first_green = int(first_hex[3:5], 16)
    first_blue = int(first_hex[5:7], 16)

    second_red = int(second_hex[1:3], 16)
    second_green = int(second_hex[3:5], 16)
    second_blue = int(second_hex[5:7], 16)

    red = round(first_red + (second_red - first_red) * amount)
    green = round(first_green + (second_green - first_green) * amount)
    blue = round(first_blue + (second_blue - first_blue) * amount)

    return "#%02X%02X%02X" % (red, green, blue)


GLOBAL_STYLE_SHEET = """
QWidget {
    color: #111111;
}

QMainWindow, QWidget#window_background, QDialog, QMessageBox {
    background: #FFFFFF;
}

QLineEdit, QSpinBox, QComboBox {
    border: 1px solid #E5E5E5;
    border-radius: 10px;
    padding: 9px 12px;
    background: #FFFFFF;
    selection-background-color: #111111;
    selection-color: #FFFFFF;
    min-height: 20px;
}

QLineEdit:hover, QSpinBox:hover, QComboBox:hover {
    border: 1px solid #B5B5B5;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #111111;
}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background: #F5F5F5;
    color: #B5B5B5;
}

QSpinBox::up-button, QSpinBox::down-button {
    width: 0px;
    border: none;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    border: 1px solid #E5E5E5;
    background: #FFFFFF;
    selection-background-color: #F5F5F5;
    selection-color: #111111;
    outline: 0;
    padding: 4px;
}

QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #111111;
    border-radius: 4px;
    background: #FFFFFF;
}

QCheckBox::indicator:checked {
    background: #111111;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    width: 10px;
    background: transparent;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #D9D9D9;
    border-radius: 3px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: #B5B5B5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QToolTip {
    background: #111111;
    color: #FFFFFF;
    border: none;
    padding: 6px 8px;
}

QMessageBox QPushButton, QDialog QPushButton {
    border: 1px solid #E5E5E5;
    border-radius: 10px;
    padding: 8px 18px;
    background: #FFFFFF;
    min-width: 72px;
}

QMessageBox QPushButton:hover, QDialog QPushButton:hover {
    border: 1px solid #111111;
}

QMessageBox QPushButton:default {
    background: #111111;
    color: #FFFFFF;
    border: 1px solid #111111;
}
"""


def focus_reason_shows_ring(focus_reason):
    # The focus ring is only drawn when the person navigates with the keyboard,
    # not when they click with the mouse or when the window first opens.
    keyboard_reasons = [
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    ]

    return focus_reason in keyboard_reasons
