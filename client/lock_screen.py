from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

import lockdown


class LockScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("SESSION LOCKED")
        self.title_label.setStyleSheet("color: white; font-size: 40px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.message_label = QLabel("Please see the front desk to continue.")
        self.message_label.setStyleSheet("color: #cccccc; font-size: 18px;")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.dev_hint_label = QLabel("Staff: press ESC to override lock")
        self.dev_hint_label.setStyleSheet("color: #555555; font-size: 12px;")
        self.dev_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.dev_hint_label)
        self.setLayout(layout)

        self.hide()

    def keyPressEvent(self, event: QKeyEvent):
        # Kept intentionally as a permanent staff override, not just a dev convenience —
        # gives front-desk staff a local way to clear a stuck lock without needing the
        # Admin app if something goes wrong.
        if event.key() == Qt.Key.Key_Escape:
            self.unlock()

    def show_locked(self, message: str = None):
        if message:
            self.message_label.setText(message)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()
        try:
            lockdown.install_hook()
        except Exception as e:
            print(f"[LOCKDOWN] Could not enable keyboard blocking: {e}")

    def show_message_only(self, text: str):
        """For remote 'Send Message' command — briefly overlays text without full lockdown state"""
        self.title_label.setText("MESSAGE FROM ADMIN")
        self.message_label.setText(text)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def unlock(self):
        self.hide()
        lockdown.uninstall_hook()