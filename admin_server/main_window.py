import sys
import os
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QLabel,
    QPushButton, QVBoxLayout, QMenu, QMessageBox, QDialog,
    QComboBox, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction

from database.database import SessionLocal
from database.models import Computer, PricingPlan
import ws_server
import session_manager
import billing_manager
import auth_manager
from login_dialog import LoginDialog
from reports_window import ReportsWindow

STATUS_COLORS = {
    "Available": "#2ecc71",
    "Occupied": "#e74c3c",
    "Locked": "#f39c12",
    "Offline": "#7f8c8d",
    "Maintenance": "#9b59b6",
}


class StartSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Start Session")

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Postpaid", "Prepaid"])

        self.plan_combo = QComboBox()
        db = SessionLocal()
        try:
            self.plans = db.query(PricingPlan).all()
        finally:
            db.close()
        for plan in self.plans:
            label = f"{plan.PlanName} (Rs.{plan.HourlyRate}/hr)"
            self.plan_combo.addItem(label, userData=plan.PlanID)

        form = QFormLayout()
        form.addRow("Session Type:", self.type_combo)
        form.addRow("Pricing Plan:", self.plan_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_selection(self):
        return self.type_combo.currentText(), self.plan_combo.currentData()


class PrintJobDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Print Job")

        self.pages_input = QComboBox()
        self.pages_input.setEditable(True)
        self.pages_input.addItems(["1", "2", "5", "10", "20"])

        self.color_combo = QComboBox()
        self.color_combo.addItems(["Black & White", "Color"])

        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A3"])

        form = QFormLayout()
        form.addRow("Pages:", self.pages_input)
        form.addRow("Type:", self.color_combo)
        form.addRow("Paper Size:", self.size_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_values(self):
        try:
            pages = int(self.pages_input.currentText())
        except ValueError:
            pages = 0
        is_color = self.color_combo.currentText() == "Color"
        paper_size = self.size_combo.currentText()
        return pages, is_color, paper_size


class POSSaleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sell Item")

        self.item_combo = QComboBox()
        self.items = billing_manager.get_inventory_items()
        for item in self.items:
            label = f"{item.ItemName} — Rs.{item.SalePrice} (Stock: {item.StockQuantity})"
            self.item_combo.addItem(label, userData=item.ItemID)

        self.qty_input = QComboBox()
        self.qty_input.setEditable(True)
        self.qty_input.addItems(["1", "2", "3", "5"])

        form = QFormLayout()
        form.addRow("Item:", self.item_combo)
        form.addRow("Quantity:", self.qty_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_values(self):
        item_id = self.item_combo.currentData()
        try:
            qty = int(self.qty_input.currentText())
        except ValueError:
            qty = 0
        return item_id, qty


class SignalBridge(QObject):
    """Lets the background asyncio thread safely trigger a GUI refresh"""
    status_changed = pyqtSignal()


class PCTile(QPushButton):
    def __init__(self, computer_id, pc_name, status, refresh_callback, parent=None):
        super().__init__(parent)
        self.computer_id = computer_id
        self.pc_name = pc_name
        self.status = status
        self.refresh_callback = refresh_callback
        self.setFixedSize(140, 100)
        self.update_display()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)
        self.clicked.connect(self.handle_left_click)

    def handle_left_click(self):
        if self.status == "Available":
            self.start_session_flow()
        elif self.status == "Occupied":
            self.checkout_flow()
        else:
            QMessageBox.information(
                self, "Not Available",
                f"{self.pc_name} is currently {self.status}. "
                "Sessions can only be started when a PC is Available."
            )

    def start_session_flow(self):
        dialog = StartSessionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            session_type, plan_id = dialog.get_selection()
            success, message, session_id = session_manager.start_session(
                self.computer_id, session_type=session_type, plan_id=plan_id
            )
            if success:
                ws_server.push_session_update_sync(self.computer_id)
                QTimer.singleShot(0, self.refresh_callback)
            else:
                QMessageBox.warning(self, "Could Not Start Session", message)

    def checkout_flow(self):
        session = session_manager.get_active_session_for_computer(self.computer_id)
        if session is None:
            QMessageBox.warning(self, "No Active Session", "No session found for this PC.")
            return

        db = SessionLocal()
        try:
            plan = db.query(PricingPlan).filter_by(PlanID=session.PlanID).first() if session.PlanID else None
        finally:
            db.close()

        elapsed = session_manager.get_elapsed_minutes(session)
        estimated_cost = session_manager.calculate_cost(session, plan)

        reply = QMessageBox.question(
            self, "Checkout",
            f"{self.pc_name}\n\nElapsed: {elapsed:.1f} minutes\n"
            f"Estimated cost: Rs.{estimated_cost:.2f}\n\nEnd this session and check out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, message, total_cost = session_manager.end_session(session.SessionID)
            if success:
                ws_server.push_session_update_sync(self.computer_id)
                QMessageBox.information(self, "Checked Out", f"Total charged: Rs.{total_cost:.2f}")
                QTimer.singleShot(0, self.refresh_callback)
            else:
                QMessageBox.warning(self, "Checkout Failed", message)

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
        print_action = QAction("Log Print Job", self)
        pos_action = QAction("Sell Item (POS)", self)

        lock_action.triggered.connect(lambda: self.send_command("lock"))
        unlock_action.triggered.connect(lambda: self.send_command("unlock"))
        logoff_action.triggered.connect(lambda: self.send_command("logoff"))
        restart_action.triggered.connect(lambda: self.send_command("restart"))
        shutdown_action.triggered.connect(lambda: self.send_command("shutdown"))
        print_action.triggered.connect(self.log_print_job)
        pos_action.triggered.connect(self.sell_item)

        menu.addAction(lock_action)
        menu.addAction(unlock_action)
        menu.addAction(logoff_action)
        menu.addSeparator()
        menu.addAction(restart_action)
        menu.addAction(shutdown_action)
        menu.addSeparator()
        menu.addAction(print_action)
        menu.addAction(pos_action)
        menu.exec(self.mapToGlobal(pos))

    def _get_active_session_id(self):
        session = session_manager.get_active_session_for_computer(self.computer_id)
        if session is None:
            QMessageBox.warning(
                self, "No Active Session",
                "This PC has no active session. Start a session before adding charges."
            )
            return None
        return session.SessionID

    def log_print_job(self):
        session_id = self._get_active_session_id()
        if session_id is None:
            return
        dialog = PrintJobDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pages, is_color, paper_size = dialog.get_values()
            success, message, charge = billing_manager.record_print_job(
                session_id, pages, is_color, paper_size
            )
            if success:
                QMessageBox.information(self, "Print Job Logged", f"Charged: Rs.{charge:.2f}")
            else:
                QMessageBox.warning(self, "Failed", message)

    def sell_item(self):
        session_id = self._get_active_session_id()
        if session_id is None:
            return
        dialog = POSSaleDialog(self)
        if not dialog.items:
            QMessageBox.information(self, "No Inventory", "No inventory items found.")
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            item_id, qty = dialog.get_values()
            success, message, charge = billing_manager.record_pos_sale(session_id, item_id, qty)
            if success:
                QMessageBox.information(self, "Sale Recorded", f"{message}\nCharged: Rs.{charge:.2f}")
            else:
                QMessageBox.warning(self, "Failed", message)

    def send_command(self, action):
        success, message = ws_server.send_command_sync(self.computer_id, action)
        if not success:
            QMessageBox.warning(self, "Command Failed", message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"Cyber Café Admin — {auth_manager.current_employee['FullName']} "
            f"({auth_manager.current_employee['Role']})"
        )
        self.resize(800, 500)

        self._build_menu_bar()

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

    def _build_menu_bar(self):
        menu_bar = self.menuBar()
        admin_menu = menu_bar.addMenu("Admin")

        reports_action = QAction("Reports && Audit Trail", self)
        reports_action.triggered.connect(self.open_reports)
        if not auth_manager.has_permission("view_reports"):
            reports_action.setEnabled(False)
            reports_action.setToolTip("Your role does not have access to reports")
        admin_menu.addAction(reports_action)

        logout_action = QAction("Log Out", self)
        logout_action.triggered.connect(self.handle_logout)
        admin_menu.addAction(logout_action)

    def open_reports(self):
        dialog = ReportsWindow(self)
        dialog.exec()

    def handle_logout(self):
        auth_manager.logout()
        QMessageBox.information(self, "Logged Out", "You have been logged out. Please restart the app to log in again.")
        self.close()

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
            tile = PCTile(computer.ComputerID, computer.PC_Name, computer.CurrentStatus, self.refresh_grid)
            self.layout.addWidget(tile, row, col)
            self.tiles[computer.ComputerID] = tile


def main():
    # Start the WebSocket server in a background thread
    server_thread = threading.Thread(target=ws_server.run_server_in_thread, daemon=True)
    server_thread.start()

    app = QApplication(sys.argv)

    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)  # login cancelled/closed

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")