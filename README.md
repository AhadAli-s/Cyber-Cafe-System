# Cyber Café Management & Operations System

A dual-application desktop system for managing cyber café operations: a central
**Admin/Server** app for the café operator, and a lightweight **Client** app for
each customer workstation, communicating over the local network.

---

## 1. System Overview

- **Admin/Server App** — runs on the café operator's PC. Shows a live grid of all
  workstations, manages sessions and billing, handles printing/POS charges, staff
  login (role-based access), and financial/audit reporting.
- **Client App** — runs on each customer PC. Connects to the Admin app over the
  LAN, shows a session HUD (time/cost), enforces session locking, and responds to
  remote commands (lock, unlock, restart, shutdown, message).
- **Database** — PostgreSQL, shared by the Admin app (the Client never talks to
  the database directly — only to the Admin app, over WebSockets).

---

## 2. Prerequisites

- **Windows 10/11** (both apps are built and tested for Windows)
- **Python 3.11+** (avoid the free-threaded "3.13t" build — several dependencies
  don't yet ship prebuilt wheels for it)
- **PostgreSQL 14+** — [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
- All machines (Admin PC + Client PCs) must be on the **same LAN**

---

## 3. Setup (Development / Running from Source)

### 3.1 Clone/copy the project

```
CyberCafeSystem/
├── database/
├── admin_server/
├── client/
├── requirements.txt
└── .env
```

### 3.2 Create a virtual environment and install dependencies

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3.3 Configure the database connection

Edit `.env` in the project root:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cybercafe_db
DB_USER=cybercafe_admin
DB_PASSWORD=changeme123
```

### 3.4 Create the PostgreSQL database and user

Open **psql** (or SQL Shell) and run:

```sql
CREATE USER cybercafe_admin WITH PASSWORD 'changeme123';
CREATE DATABASE cybercafe_db OWNER cybercafe_admin;
```

### 3.5 Seed the database

Creates all tables plus a default admin login, 3 sample workstations, and base
pricing plans.

```cmd
cd database
python seed.py
```

Default login created by the seed script:
- **Username:** `admin`
- **Password:** `Admin@123`

Verify it worked:
```cmd
psql -U cybercafe_admin -d cybercafe_db -c "\dt"
```
You should see 9 tables.

---

## 4. LAN Network Configuration Guide

The Admin app runs a WebSocket server on **port 8765**. Client PCs connect to it
using the Admin PC's LAN IP address.

### 4.1 Find the Admin PC's IP address

On the Admin PC, run:
```cmd
ipconfig
```
Note the **IPv4 Address** under your active network adapter (e.g. `192.168.1.100`).

### 4.2 Configure each Client PC

Edit `client/config.py` on every client workstation:

```python
SERVER_HOST = "192.168.1.100"  # <-- the Admin PC's IP from step 4.1
SERVER_PORT = 8765
```

### 4.3 Allow the connection through Windows Firewall

On the **Admin PC**, when you first run the Admin app, Windows may prompt to
allow network access — click **Allow**. If it doesn't prompt, or you're testing
across machines and connections fail, add a manual rule:

```cmd
netsh advfirewall firewall add rule name="CyberCafe Admin" dir=in action=allow protocol=TCP localport=8765
```

### 4.4 Test the connection

Start the Admin app first, then the Client app. Within a few seconds the
corresponding PC tile in the Admin grid should turn green ("Available"). If it
stays offline, double-check `SERVER_HOST` matches the Admin PC's current IP
(this can change if using DHCP — consider setting a static IP or DHCP
reservation for the Admin PC in your router).

---

## 5. Running from Source

**Terminal 1 — Admin app:**
```cmd
cd admin_server
python main_window.py
```

**Terminal 2 (on each Client PC) — Client app:**
```cmd
cd client
python main.py
```

---

## 6. Building Windows Executables (.exe)

Both apps are packaged separately using **PyInstaller**.

### 6.1 Install PyInstaller

```cmd
pip install pyinstaller
```

### 6.2 Build the Admin/Server executable

Run this from the project root (`CyberCafeSystem/`):

```cmd
pyinstaller --onefile --name CyberCafeAdmin --paths database admin_server\main_window.py
```

This produces `dist\CyberCafeAdmin.exe`.

**Important:** copy your `.env` file into the `dist` folder next to
`CyberCafeAdmin.exe` — database credentials are read from there at runtime and
are **not** baked into the executable (this is intentional, for security).

```cmd
copy .env dist\.env
```

### 6.3 Build the Client executable

```cmd
pyinstaller --onefile --name CyberCafeClient client\main.py
```

This produces `dist\CyberCafeClient.exe`. Before building, make sure
`client/config.py` has the correct `SERVER_HOST` for the Admin PC it will
connect to (each client PC may need its own build, or edit `config.py` to read
from an external file if deploying to many machines).

### 6.4 Distribute

- Copy `CyberCafeAdmin.exe` + `.env` to the café operator's PC
- Copy `CyberCafeClient.exe` to each customer workstation
- Run the Admin app first, then start Client apps

### 6.5 Troubleshooting the build

- **"No module named 'database'" at runtime** — the `--paths database` flag
  wasn't picked up. Re-run the build command from the project root, not from
  inside `admin_server/`.
- **App exits instantly with no window** — run the exe from a terminal
  (`CyberCafeAdmin.exe` in cmd, not double-click) to see the printed traceback.
- **"qt.qpa.plugin: could not find the Qt platform plugin"** — rebuild with:
  ```cmd
  pyinstaller --onefile --name CyberCafeAdmin --paths database --collect-all PyQt6 admin_server\main_window.py
  ```
- **Client can't reach the server** — see Section 4 (LAN Network Configuration).

---

## 7. Known Limitations

- **System Lockdown** blocks Alt+Tab, Alt+F4, and the Windows key while a
  client is locked, but does **not** block Ctrl+Alt+Del (impossible — Windows
  reserves this at the OS level) or Ctrl+Shift+Esc (Task Manager). Task Manager
  can currently open behind the lock screen but may be visually hidden by the
  always-on-top overlay. A staff override (**Escape key**) is always available
  on the client to clear a stuck lock.
- Full Task Manager blocking (registry-level `DisableTaskMgr` policy) is not
  implemented — this would be a stronger measure for a dedicated production
  kiosk PC, but is riskier to test on a general-purpose development machine.
- Restart/Shutdown/Log Off system commands are present but intentionally
  commented out in `client/main.py` (`execute_system_command`) to prevent
  accidental reboots during development. Uncomment before deploying to a real
  kiosk PC.

---

## 8. Project Structure

```
CyberCafeSystem/
├── database/
│   ├── models.py          # SQLAlchemy models (all 9 tables)
│   ├── database.py        # DB connection/session setup
│   └── seed.py             # Creates tables + seed data
├── admin_server/
│   ├── main_window.py      # PyQt6 main window, PC grid, login gate
│   ├── ws_server.py        # WebSocket server, heartbeats, remote commands
│   ├── session_manager.py  # Session lifecycle + tariff/billing engine
│   ├── billing_manager.py  # Print job + POS/inventory billing
│   ├── auth_manager.py     # Login, roles, audit logging
│   ├── login_dialog.py     # Staff login screen
│   ├── reporting_manager.py# Revenue + audit log queries
│   └── reports_window.py   # Reports UI
├── client/
│   ├── main.py              # Client entry point
│   ├── ws_client.py         # WebSocket client, heartbeats
│   ├── lock_screen.py       # Fullscreen lock overlay
│   ├── hud.py                # Floating session time/cost widget
│   ├── lockdown.py           # Keyboard blocking while locked
│   └── config.py             # Server IP/port, this computer's ID
├── requirements.txt
└── .env
```
