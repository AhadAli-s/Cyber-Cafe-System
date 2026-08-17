from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt

import reporting_manager


class FinancialReportTab(QWidget):
    def __init__(self):
        super().__init__()

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Today", "This Week", "This Month"])

        run_btn = QPushButton("Run Report")
        run_btn.clicked.connect(self.run_report)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Period:"))
        controls.addWidget(self.preset_combo)
        controls.addWidget(run_btn)
        controls.addStretch()

        self.table = QTableWidget(4, 2)
        self.table.setHorizontalHeaderLabels(["Category", "Amount (Rs.)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.run_report()

    def run_report(self):
        preset = self.preset_combo.currentText()
        start, end = reporting_manager.get_date_range_for_preset(preset)
        summary = reporting_manager.get_revenue_summary(start, end)

        rows = [
            ("Session Time", summary["SessionTime"]),
            ("Printing", summary["Print"]),
            ("Inventory (POS)", summary["POS"]),
            ("TOTAL", summary["Total"]),
        ]
        for row_index, (label, amount) in enumerate(rows):
            self.table.setItem(row_index, 0, QTableWidgetItem(label))
            self.table.setItem(row_index, 1, QTableWidgetItem(f"Rs. {amount:.2f}"))


class AuditLogTab(QWidget):
    def __init__(self):
        super().__init__()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_logs)

        controls = QHBoxLayout()
        controls.addWidget(refresh_btn)
        controls.addStretch()

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Employee", "Action"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.load_logs()

    def load_logs(self):
        logs = reporting_manager.get_audit_logs()
        self.table.setRowCount(len(logs))
        for row_index, log in enumerate(logs):
            timestamp_str = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row_index, 0, QTableWidgetItem(timestamp_str))
            self.table.setItem(row_index, 1, QTableWidgetItem(log["employee_name"]))
            self.table.setItem(row_index, 2, QTableWidgetItem(log["action"]))


class ReportsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reports & Audit Trail")
        self.resize(600, 450)

        tabs = QTabWidget()
        tabs.addTab(FinancialReportTab(), "Financial Report")
        tabs.addTab(AuditLogTab(), "Audit Log")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)