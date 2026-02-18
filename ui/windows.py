from __future__ import annotations

from PySide6 import QtWidgets


class LogWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tiny Signaling Server")

        self._text = QtWidgets.QTextEdit(self)
        self._text.setReadOnly(True)
        self.setCentralWidget(self._text)

        self.resize(900, 600)

    def append_log(self, line: str) -> None:
        self._text.append(line)
