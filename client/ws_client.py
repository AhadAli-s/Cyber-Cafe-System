import asyncio
import json
import websockets

import config

# Set once the client's event loop starts, so the GUI thread can schedule
# coroutines on it safely from outside asyncio.
client_loop = None
active_websocket = None

# Callback set by the GUI layer to react to incoming commands.
# Signature: on_command(action: str, extra: dict)
on_command = None

# Callback for session_update messages (drives the HUD).
# Signature: on_session_update(session_data: dict | None)
on_session_update = None


def set_command_callback(callback):
    global on_command
    on_command = callback


def set_session_update_callback(callback):
    global on_session_update
    on_session_update = callback


async def heartbeat_loop(websocket):
    """Sends a heartbeat every HEARTBEAT_INTERVAL seconds until the connection drops"""
    while True:
        try:
            await websocket.send(json.dumps({
                "type": "heartbeat",
                "computer_id": config.COMPUTER_ID
            }))
            await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        except websockets.exceptions.ConnectionClosed:
            break


async def listen_loop(websocket):
    """Listens for incoming commands from the Admin server"""
    async for raw_message in websocket:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            continue

        if message.get("type") == "command" and on_command:
            action = message.get("action")
            on_command(action, message)
        elif message.get("type") == "session_update" and on_session_update:
            on_session_update(message.get("session"))


async def connect_and_run():
    """Connects to the server, registers, then runs heartbeat + listen loops concurrently.
    Reconnects automatically if the connection is lost."""
    global client_loop, active_websocket
    client_loop = asyncio.get_running_loop()
    uri = f"ws://{config.SERVER_HOST}:{config.SERVER_PORT}"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                active_websocket = websocket
                print(f"Connected to server at {uri}")

                await websocket.send(json.dumps({
                    "type": "register",
                    "computer_id": config.COMPUTER_ID
                }))

                await asyncio.gather(
                    heartbeat_loop(websocket),
                    listen_loop(websocket)
                )
        except (ConnectionRefusedError, websockets.exceptions.ConnectionClosed, OSError) as e:
            print(f"Connection lost or unavailable ({e}). Retrying in {config.RECONNECT_INTERVAL}s...")
            active_websocket = None
            await asyncio.sleep(config.RECONNECT_INTERVAL)


def run_client_in_thread():
    """Entry point for running this in a background thread from the GUI"""
    asyncio.run(connect_and_run())


def send_request_sync(request_type: str):
    """Thread-safe: call from the PyQt (main) thread, e.g. HUD button clicks.
    Sends a simple {"type": ..., "computer_id": ...} message to the server."""
    if client_loop is None or active_websocket is None:
        print("Not connected to server yet.")
        return

    async def _send():
        await active_websocket.send(json.dumps({
            "type": request_type,
            "computer_id": config.COMPUTER_ID
        }))

    asyncio.run_coroutine_threadsafe(_send(), client_loop)