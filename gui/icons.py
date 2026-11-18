"""
icons.py

Simple line icons drawn with code, so no image files are needed.
Every icon is drawn on a 24 x 24 grid with thin rounded strokes.
"""

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QPixmap, QIcon


def build_polyline(coordinate_pairs):
    # Turn [(x, y), (x, y), ...] into a list of points Qt understands.
    points = []

    for x_position, y_position in coordinate_pairs:
        points.append(QPointF(x_position, y_position))

    return points


def draw_icon_shapes(painter, icon_name):
    # Draw one icon. Shapes are described on a 24 x 24 grid.
    if icon_name == "check":
        painter.drawPolyline(build_polyline([(5, 12.5), (10, 17.5), (19, 7)]))

    elif icon_name == "cross":
        painter.drawLine(QPointF(6, 6), QPointF(18, 18))
        painter.drawLine(QPointF(18, 6), QPointF(6, 18))

    elif icon_name == "dot":
        painter.setBrush(painter.pen().color())
        painter.drawEllipse(QPointF(12, 12), 3.2, 3.2)

    elif icon_name == "minus":
        painter.drawLine(QPointF(6, 12), QPointF(18, 12))

    elif icon_name == "plus":
        painter.drawLine(QPointF(12, 5), QPointF(12, 19))
        painter.drawLine(QPointF(5, 12), QPointF(19, 12))

    elif icon_name == "warning":
        triangle = QPainterPath()
        triangle.moveTo(12, 3.5)
        triangle.lineTo(21.5, 20)
        triangle.lineTo(2.5, 20)
        triangle.closeSubpath()
        painter.drawPath(triangle)
        painter.drawLine(QPointF(12, 10), QPointF(12, 14.5))
        painter.drawPoint(QPointF(12, 17.2))

    elif icon_name == "exclaim":
        painter.drawLine(QPointF(12, 6), QPointF(12, 14))
        painter.drawPoint(QPointF(12, 18))

    elif icon_name == "info":
        painter.drawLine(QPointF(12, 11), QPointF(12, 17))
        painter.drawPoint(QPointF(12, 7.5))

    elif icon_name == "chevron_down":
        painter.drawPolyline(build_polyline([(6, 9), (12, 15), (18, 9)]))

    elif icon_name == "chevron_left":
        painter.drawPolyline(build_polyline([(15, 6), (9, 12), (15, 18)]))

    elif icon_name == "upload":
        painter.drawLine(QPointF(12, 16), QPointF(12, 5))
        painter.drawPolyline(build_polyline([(7, 10), (12, 5), (17, 10)]))
        painter.drawLine(QPointF(5, 19.5), QPointF(19, 19.5))

    elif icon_name == "download":
        painter.drawLine(QPointF(12, 4), QPointF(12, 15))
        painter.drawPolyline(build_polyline([(7, 10.5), (12, 15.5), (17, 10.5)]))
        painter.drawLine(QPointF(5, 19.5), QPointF(19, 19.5))

    elif icon_name == "file":
        page = QPainterPath()
        page.moveTo(7, 3.5)
        page.lineTo(14, 3.5)
        page.lineTo(19, 8.5)
        page.lineTo(19, 20.5)
        page.lineTo(7, 20.5)
        page.closeSubpath()
        painter.drawPath(page)
        painter.drawPolyline(build_polyline([(14, 3.5), (14, 8.5), (19, 8.5)]))

    elif icon_name == "key":
        painter.drawEllipse(QPointF(8, 15.5), 4, 4)
        painter.drawLine(QPointF(11, 12.5), QPointF(20, 3.5))
        painter.drawLine(QPointF(16.5, 7), QPointF(19, 9.5))

    elif icon_name == "lock":
        painter.drawRoundedRect(QRectF(6, 11, 12, 9), 2, 2)
        shackle = QPainterPath()
        shackle.moveTo(8.5, 11)
        shackle.lineTo(8.5, 8)
        shackle.arcTo(QRectF(8.5, 4, 7, 7), 180, -180)
        shackle.lineTo(15.5, 11)
        painter.drawPath(shackle)

    elif icon_name == "shield":
        shield = QPainterPath()
        shield.moveTo(12, 3)
        shield.lineTo(19, 6)
        shield.lineTo(19, 12)
        shield.quadTo(19, 18, 12, 21)
        shield.quadTo(5, 18, 5, 12)
        shield.lineTo(5, 6)
        shield.closeSubpath()
        painter.drawPath(shield)

    elif icon_name == "grid":
        painter.drawRoundedRect(QRectF(4, 4, 6.5, 6.5), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(13.5, 4, 6.5, 6.5), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(4, 13.5, 6.5, 6.5), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(13.5, 13.5, 6.5, 6.5), 1.5, 1.5)

    elif icon_name == "pen":
        pen_shape = QPainterPath()
        pen_shape.moveTo(4, 20)
        pen_shape.lineTo(5, 15)
        pen_shape.lineTo(16, 4)
        pen_shape.lineTo(20, 8)
        pen_shape.lineTo(9, 19)
        pen_shape.closeSubpath()
        painter.drawPath(pen_shape)
        painter.drawLine(QPointF(14, 6), QPointF(18, 10))

    elif icon_name == "certificate":
        painter.drawRoundedRect(QRectF(3, 4.5, 18, 12), 2, 2)
        painter.drawLine(QPointF(7, 9), QPointF(17, 9))
        painter.drawLine(QPointF(7, 12.5), QPointF(12, 12.5))
        painter.drawPolyline(build_polyline([(15, 16.5), (15, 21), (17, 19.5), (19, 21), (19, 16.5)]))

    elif icon_name == "trash":
        painter.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
        painter.drawPolyline(build_polyline([(9, 7), (9, 4.5), (15, 4.5), (15, 7)]))
        painter.drawPolyline(build_polyline([(6.5, 7), (7.5, 20), (16.5, 20), (17.5, 7)]))

    elif icon_name == "folder":
        folder = QPainterPath()
        folder.moveTo(3.5, 7)
        folder.lineTo(3.5, 19)
        folder.lineTo(20.5, 19)
        folder.lineTo(20.5, 8.5)
        folder.lineTo(11.5, 8.5)
        folder.lineTo(9.5, 6)
        folder.lineTo(4.5, 6)
        folder.closeSubpath()
        painter.drawPath(folder)


def make_pixmap(icon_name, size_in_pixels, color_hex, line_width=1.7):
    # Draw an icon into a sharp pixmap (drawn at 2x for high resolution screens).
    pixel_ratio = 2.0
    pixmap = QPixmap(int(size_in_pixels * pixel_ratio), int(size_in_pixels * pixel_ratio))
    pixmap.setDevicePixelRatio(pixel_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size_in_pixels / 24.0, size_in_pixels / 24.0)

    pen = QPen(QColor(color_hex))
    pen.setWidthF(line_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    draw_icon_shapes(painter, icon_name)
    painter.end()

    return pixmap


def make_icon(icon_name, size_in_pixels, color_hex):
    return QIcon(make_pixmap(icon_name, size_in_pixels, color_hex))
