import sys
import os
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "database"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QLabel,
    QPushButton, QVBoxLayout, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction

from database import SessionLocal
from models import Computer
import ws_server

STATUS_COLORS = {
    "Available": "#2ecc71",
    "Occupied": "#e74c3c",
    "Locked": "#f39c12",
    "Offline": "#7f8c8d",
    "Maintenance": "#9b59b6",
}


class SignalBridge(QObject):
    """Lets the background asyncio thread safely trigger a GUI refresh"""
    status_changed = pyqtSignal()


class PCTile(QPushButton):
    def __init__(self, computer_id, pc_name, status, parent=None):
        super().__init__(parent)
        self.computer_id = computer_id
        self.pc_name = pc_name
        self.status = status
        self.setFixedSize(140, 100)
        self.update_display()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

    def update_display(self):
        color = STATUS_COLORS.get(self.status, "#7f8c8d")
        self.setText(f"{self.pc_name}\n\n{self.status}")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border: 2px solid #2c3e50;
            }}
        """)

    def show_menu(self, pos):
        menu = QMenu(self)
        lock_action = QAction("Lock", self)
        unlock_action = QAction("Unlock", self)
        logoff_action = QAction("Log Off", self)
        restart_action = QAction("Restart", self)
        shutdown_action = QAction("Shutdown", self)

        lock_action.triggered.connect(lambda: self.send_command("lock"))
        unlock_action.triggered.connect(lambda: self.send_command("unlock"))
        logoff_action.triggered.connect(lambda: self.send_command("logoff"))
        restart_action.triggered.connect(lambda: self.send_command("restart"))
        shutdown_action.triggered.connect(lambda: self.send_command("shutdown"))

        menu.addAction(lock_action)
        menu.addAction(unlock_action)
        menu.addAction(logoff_action)
        menu.addSeparator()
        menu.addAction(restart_action)
        menu.addAction(shutdown_action)
        menu.exec(self.mapToGlobal(pos))

    def send_command(self, action):
        success, message = ws_server.send_command_sync(self.computer_id, action)
        if not success:
            QMessageBox.warning(self, "Command Failed", message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyber Café Admin — PC Management Grid")
        self.resize(800, 500)

        self.signal_bridge = SignalBridge()
        self.signal_bridge.status_changed.connect(self.refresh_grid)
        ws_server.set_status_change_callback(
            lambda: self.signal_bridge.status_changed.emit()
        )

        central = QWidget()
        self.layout = QGridLayout()
        central.setLayout(self.layout)
        self.setCentralWidget(central)

        self.tiles = {}
        self.refresh_grid()

        # Fallback polling every 5s in case a signal is missed
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_grid)
        self.timer.start(5000)

    def refresh_grid(self):
        db = SessionLocal()
        try:
            computers = db.query(Computer).order_by(Computer.ComputerID).all()
        finally:
            db.close()

        # Clear existing tiles
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.tiles.clear()

        columns = 5
        for index, computer in enumerate(computers):
            row, col = divmod(index, columns)
            tile = PCTile(computer.ComputerID, computer.PC_Name, computer.CurrentStatus)
            self.layout.addWidget(tile, row, col)
            self.tiles[computer.ComputerID] = tile


def main():
    # Start the WebSocket server in a background thread
    server_thread = threading.Thread(target=ws_server.run_server_in_thread, daemon=True)
    server_thread.start()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()