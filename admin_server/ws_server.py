import asyncio
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "database"))

import websockets
from database import SessionLocal
from models import Computer

HOST = "0.0.0.0"
PORT = 8765

# Maps computer_id -> websocket connection, so the Admin app can send commands
connected_clients = {}

# Callback set by the GUI to refresh the PC grid whenever status changes
on_status_change = None


def set_status_change_callback(callback):
    """Called by the GUI layer to receive live status updates"""
    global on_status_change
    on_status_change = callback


def update_computer_status(computer_id: int, status: str):
    db = SessionLocal()
    try:
        computer = db.query(Computer).filter_by(ComputerID=computer_id).first()
        if computer:
            computer.CurrentStatus = status
            db.commit()
            if on_status_change:
                on_status_change()
    finally:
        db.close()


async def handle_client(websocket):
    computer_id = None
    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")

            if msg_type == "register":
                # First message a client sends after connecting: identifies itself
                computer_id = message.get("computer_id")
                connected_clients[computer_id] = websocket
                update_computer_status(computer_id, "Available")
                print(f"[CONNECTED] Computer {computer_id}")

            elif msg_type == "heartbeat":
                computer_id = message.get("computer_id")
                if computer_id is not None:
                    connected_clients[computer_id] = websocket
                    # Only bump to Available if it wasn't Locked/Occupied/Maintenance
                    db = SessionLocal()
                    try:
                        computer = db.query(Computer).filter_by(ComputerID=computer_id).first()
                        if computer and computer.CurrentStatus == "Offline":
                            computer.CurrentStatus = "Available"
                            db.commit()
                            if on_status_change:
                                on_status_change()
                    finally:
                        db.close()

            elif msg_type == "status_update":
                # Client reporting a state change, e.g. session started/ended
                computer_id = message.get("computer_id")
                status = message.get("status")
                if computer_id is not None and status:
                    update_computer_status(computer_id, status)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if computer_id is not None:
            connected_clients.pop(computer_id, None)
            update_computer_status(computer_id, "Offline")
            print(f"[DISCONNECTED] Computer {computer_id}")


async def send_command(computer_id: int, action: str, extra: dict = None):
    """
    Send a remote command to a specific client.
    action: 'lock', 'unlock', 'logoff', 'restart', 'shutdown', 'message'
    extra: optional dict for extra data, e.g. {"text": "Time is up"} for 'message'
    """
    websocket = connected_clients.get(computer_id)
    if websocket is None:
        return False, "Computer is not connected"

    payload = {"type": "command", "action": action}
    if extra:
        payload.update(extra)

    try:
        await websocket.send(json.dumps(payload))
        return True, "Command sent"
    except websockets.exceptions.ConnectionClosed:
        connected_clients.pop(computer_id, None)
        return False, "Connection lost"


# Reference to the running event loop, set once the server starts.
# The GUI thread needs this to safely schedule coroutines from outside asyncio.
server_loop = None


async def start_server():
    global server_loop
    server_loop = asyncio.get_running_loop()
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"Admin server listening on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever


def run_server_in_thread():
    """Runs the asyncio event loop in a background thread, called from the GUI"""
    asyncio.run(start_server())


def send_command_sync(computer_id: int, action: str, extra: dict = None):
    """
    Thread-safe wrapper: call this from the PyQt (main) thread.
    Schedules send_command() on the server's asyncio loop and waits for the result.
    """
    if server_loop is None:
        return False, "Server not running yet"

    future = asyncio.run_coroutine_threadsafe(
        send_command(computer_id, action, extra), server_loop
    )
    try:
        return future.result(timeout=5)
    except Exception as e:
        return False, str(e)