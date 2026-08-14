from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt


class SessionHUD(QWidget):
    """A small floating widget showing elapsed session time and cost.
    Hidden entirely when there's no active session."""

    def __init__(self, on_logout_click, on_extra_time_click):
        super().__init__()
        self.on_logout_click = on_logout_click
        self.on_extra_time_click = on_extra_time_click

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(260, 110)
        self.setStyleSheet("""
            background-color: rgba(30, 30, 30, 230);
            border-radius: 10px;
        """)

        self.plan_label = QLabel("—")
        self.plan_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")

        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: white; font-size: 26px; font-weight: bold;")

        self.cost_label = QLabel("Rs. 0.00")
        self.cost_label.setStyleSheet("color: #2ecc71; font-size: 16px; font-weight: bold;")

        extra_time_btn = QPushButton("Request Extra Time")
        extra_time_btn.setStyleSheet(self._button_style("#3498db"))
        extra_time_btn.clicked.connect(self.on_extra_time_click)

        logout_btn = QPushButton("Logout")
        logout_btn.setStyleSheet(self._button_style("#e74c3c"))
        logout_btn.clicked.connect(self.on_logout_click)

        top_row = QHBoxLayout()
        top_row.addWidget(self.time_label)
        top_row.addWidget(self.cost_label)

        button_row = QHBoxLayout()
        button_row.addWidget(extra_time_btn)
        button_row.addWidget(logout_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.plan_label)
        layout.addLayout(top_row)
        layout.addLayout(button_row)
        self.setLayout(layout)

        self.hide()
        self._position_top_right()

    def _button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border-radius: 5px;
                padding: 4px;
                font-size: 11px;
            }}
        """

    def _position_top_right(self):
        screen = self.screen().availableGeometry()
        self.move(screen.width() - self.width() - 20, 20)

    def update_session(self, session_data: dict | None):
        if session_data is None:
            self.hide()
            return

        elapsed = session_data.get("elapsed_minutes", 0)
        cost = session_data.get("cost", 0)
        plan_name = session_data.get("plan_name", "Standard")
        session_type = session_data.get("session_type", "")

        minutes = int(elapsed)
        seconds = int((elapsed - minutes) * 60)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.cost_label.setText(f"Rs. {cost:.2f}")
        self.plan_label.setText(f"{plan_name} ({session_type})")

        if not self.isVisible():
            self.show()
            self._position_top_right()