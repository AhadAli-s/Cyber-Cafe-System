from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt


class LockScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
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

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        self.setLayout(layout)

        self.hide()

    def show_locked(self, message: str = None):
        if message:
            self.message_label.setText(message)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def show_message_only(self, text: str):
        """For remote 'Send Message' command — briefly overlays text without full lockdown state"""
        self.title_label.setText("MESSAGE FROM ADMIN")
        self.message_label.setText(text)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def unlock(self):
        self.hide()