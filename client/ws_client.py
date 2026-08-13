import asyncio
import json
import websockets

import config

# Callback set by the GUI layer to react to incoming commands.
# Signature: on_command(action: str, extra: dict)
on_command = None


def set_command_callback(callback):
    global on_command
    on_command = callback


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


async def connect_and_run():
    """Connects to the server, registers, then runs heartbeat + listen loops concurrently.
    Reconnects automatically if the connection is lost."""
    uri = f"ws://{config.SERVER_HOST}:{config.SERVER_PORT}"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
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
            await asyncio.sleep(config.RECONNECT_INTERVAL)


def run_client_in_thread():
    """Entry point for running this in a background thread from the GUI"""
    asyncio.run(connect_and_run())