from __future__ import annotations

from PySide6 import QtWidgets


def create_qt_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app  # type: ignore
