"""
Lightweight kiosk-mode keyboard blocking for the lock screen.

DELIBERATELY DOES NOT BLOCK:
- Ctrl+Alt+Del  (impossible anyway — Windows reserves this at the OS level,
                 it never reaches any application, by design as a safety net)
- Ctrl+Shift+Esc (Task Manager) — left open on purpose as an admin escape hatch

This uses a low-level keyboard hook (WH_KEYBOARD_LL) via ctypes. It only
affects this process while active, is fully reversible, and does NOT touch
the Windows Registry — unlike a full "DisableTaskMgr" policy approach, which
is riskier to test on a personal dev machine and is not implemented here.

For a real production kiosk deployment on a dedicated/disposable PC, stronger
measures (Group Policy restrictions, a proper kiosk shell) would be the next
step — see README for notes on this.
"""

import ctypes
from ctypes import wintypes

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

VK_TAB = 0x09
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_MENU = 0x12  # Alt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_hook_handle = None
_hook_proc_ref = None  # keep a reference alive so it isn't garbage collected


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


def _low_level_keyboard_proc(nCode, wParam, lParam):
    if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode

        alt_pressed = user32.GetAsyncKeyState(VK_MENU) & 0x8000

        if vk == VK_TAB and alt_pressed:
            return 1  # block Alt+Tab
        if vk == VK_F4 and alt_pressed:
            return 1  # block Alt+F4
        if vk in (VK_LWIN, VK_RWIN):
            return 1  # block Windows key

    return user32.CallNextHookEx(_hook_handle, nCode, wParam, lParam)


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


def install_hook():
    """Installs the keyboard hook. Safe to call multiple times (no-op if already active)."""
    global _hook_handle, _hook_proc_ref
    if _hook_handle is not None:
        return  # already installed

    _hook_proc_ref = HOOKPROC(_low_level_keyboard_proc)
    module_handle = kernel32.GetModuleHandleW(None)
    _hook_handle = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, _hook_proc_ref, module_handle, 0
    )
    if not _hook_handle:
        print(f"[LOCKDOWN] Failed to install keyboard hook (error {ctypes.get_last_error()})")


def uninstall_hook():
    """Removes the keyboard hook. Always call this on unlock and on app exit."""
    global _hook_handle
    if _hook_handle is not None:
        user32.UnhookWindowsHookEx(_hook_handle)
        _hook_handle = None