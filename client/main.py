import sys
import os
import threading
import subprocess

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

import ws_client
from lock_screen import LockScreen


class CommandBridge(QObject):
    """Lets the background asyncio thread safely trigger GUI actions"""
    lock_signal = pyqtSignal()
    unlock_signal = pyqtSignal()
    message_signal = pyqtSignal(str)
    restart_signal = pyqtSignal()
    shutdown_signal = pyqtSignal()
    logoff_signal = pyqtSignal()


def execute_system_command(action: str):
    """Runs the actual Windows system command for restart/shutdown/logoff.
    NOTE: shutdown/restart/logoff are commented out by default during development
    so you don't accidentally reboot your dev machine. Uncomment when ready to test on
    a real client PC."""
    if action == "restart":
        print("[SYSTEM] Restart requested")
        # subprocess.run(["shutdown", "/r", "/t", "5"])
    elif action == "shutdown":
        print("[SYSTEM] Shutdown requested")
        # subprocess.run(["shutdown", "/s", "/t", "5"])
    elif action == "logoff":
        print("[SYSTEM] Log off requested")
        # subprocess.run(["shutdown", "/l"])


def main():
    print("Starting Cyber Cafe Client...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running even with no visible window

    lock_screen = LockScreen()
    bridge = CommandBridge()

    bridge.lock_signal.connect(lambda: lock_screen.show_locked())
    bridge.unlock_signal.connect(lock_screen.unlock)
    bridge.message_signal.connect(lock_screen.show_message_only)
    bridge.restart_signal.connect(lambda: execute_system_command("restart"))
    bridge.shutdown_signal.connect(lambda: execute_system_command("shutdown"))
    bridge.logoff_signal.connect(lambda: execute_system_command("logoff"))

    def handle_command(action: str, extra: dict):
        print(f"[COMMAND RECEIVED] {action}")
        if action == "lock":
            bridge.lock_signal.emit()
        elif action == "unlock":
            bridge.unlock_signal.emit()
        elif action == "message":
            bridge.message_signal.emit(extra.get("text", ""))
        elif action == "restart":
            bridge.restart_signal.emit()
        elif action == "shutdown":
            bridge.shutdown_signal.emit()
        elif action == "logoff":
            bridge.logoff_signal.emit()

    ws_client.set_command_callback(handle_command)

    # Run the WebSocket client in a background thread so it doesn't block the GUI
    client_thread = threading.Thread(target=ws_client.run_client_in_thread, daemon=True)
    client_thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")