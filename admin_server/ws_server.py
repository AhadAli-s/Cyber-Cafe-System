import asyncio
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import websockets
from database.database import SessionLocal
from database.models import Computer, PricingPlan
import session_manager

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


def reset_all_computers_offline():
    """
    Called once when the Admin server starts. At startup we know for certain
    no clients are connected yet, so any stale 'Available' status left over
    from a previous crash or force-quit is corrected here.

    Computers with a genuinely active (unended) session are left alone —
    their status reflects real billing state, not just connection state, and
    should only change via normal session/lock flows, not a blind reset.
    """
    db = SessionLocal()
    try:
        computers = db.query(Computer).all()
        for computer in computers:
            if computer.CurrentStatus in ("Locked", "Maintenance"):
                continue  # operator-set states, leave untouched

            active_session = session_manager.get_active_session_for_computer(computer.ComputerID)
            if active_session is None:
                computer.CurrentStatus = "Offline"
            # else: leave as-is (e.g. Occupied) — a real session justifies it
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[STARTUP] Failed to reset computer statuses: {e}")
    finally:
        db.close()


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


async def push_session_update(websocket, computer_id: int):
    """Sends the client its current session state (elapsed time, cost) so the
    Session HUD can display it. Sends session: null if no active session."""
    session = session_manager.get_active_session_for_computer(computer_id)

    if session is None:
        payload = {"type": "session_update", "session": None}
    else:
        db = SessionLocal()
        try:
            plan = None
            if session.PlanID:
                plan = db.query(PricingPlan).filter_by(PlanID=session.PlanID).first()
            elapsed_minutes = session_manager.get_elapsed_minutes(session)
            cost = session_manager.calculate_cost(session, plan)
            payload = {
                "type": "session_update",
                "session": {
                    "session_id": session.SessionID,
                    "session_type": session.SessionType,
                    "plan_name": plan.PlanName if plan else "Standard",
                    "elapsed_minutes": round(elapsed_minutes, 1),
                    "cost": cost,
                }
            }
        finally:
            db.close()

    try:
        await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosed:
        pass


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
                # First message a client sends after connecting: identifies itself.
                # Don't blindly reset status — a computer may still have an active
                # session (Occupied) or be Locked/Maintenance even if the client
                # briefly disconnected and reconnected.
                computer_id = message.get("computer_id")
                connected_clients[computer_id] = websocket
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
                    await push_session_update(websocket, computer_id)

            elif msg_type == "end_session_request":
                # Client's HUD "Logout" button was clicked
                computer_id = message.get("computer_id")
                if computer_id is not None:
                    session = session_manager.get_active_session_for_computer(computer_id)
                    if session:
                        session_manager.end_session(session.SessionID)
                        update_computer_status(computer_id, "Available")
                        await push_session_update(websocket, computer_id)

            elif msg_type == "extra_time_request":
                # Client's HUD "Request Extra Time" button was clicked.
                # TODO: surface this as a Live Notification in the Admin UI (Section 3.2)
                computer_id = message.get("computer_id")
                print(f"[EXTRA TIME REQUESTED] Computer {computer_id}")

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
    reset_all_computers_offline()
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"Admin server listening on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever


def run_server_in_thread():
    """Runs the asyncio event loop in a background thread, called from the GUI"""
    asyncio.run(start_server())


def push_session_update_sync(computer_id: int):
    """Call from the PyQt (main) thread after starting/ending a session via
    session_manager, so the client's HUD updates immediately instead of
    waiting for the next heartbeat cycle."""
    if server_loop is None:
        return
    websocket = connected_clients.get(computer_id)
    if websocket is None:
        return
    asyncio.run_coroutine_threadsafe(
        push_session_update(websocket, computer_id), server_loop
    )


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