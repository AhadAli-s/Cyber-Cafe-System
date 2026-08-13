# This machine's identity — must match a ComputerID already seeded in the database
COMPUTER_ID = 1

# Admin server's LAN IP and port (matches ws_server.py PORT)
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765

# How often to send a heartbeat, in seconds
HEARTBEAT_INTERVAL = 5

# How often to try reconnecting if the server connection drops, in seconds
RECONNECT_INTERVAL = 5