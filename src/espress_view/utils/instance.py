"""Windows single-instance guard."""

import ctypes
import sys

SINGLE_INSTANCE_MUTEX = "Local\\EspressViewSingleInstance"
ERROR_ALREADY_EXISTS = 183
_MUTEX_HANDLE: list[int | None] = [None]


def acquire_single_instance() -> bool:
    """Acquire the process-wide Windows mutex used to prevent duplicate launches."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex_handle = kernel32.CreateMutexW(None, True, SINGLE_INSTANCE_MUTEX)
    if not mutex_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex_handle)
        return False
    _MUTEX_HANDLE[0] = int(mutex_handle)
    return True


def release_single_instance() -> None:
    """Release the Windows mutex held by this application process."""
    mutex_handle = _MUTEX_HANDLE[0]
    if mutex_handle is None or sys.platform != "win32":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(ctypes.c_void_p(mutex_handle))
    _MUTEX_HANDLE[0] = None
