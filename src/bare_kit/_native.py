import ctypes
from functools import cache
from pathlib import Path

from ._host import host, library_name

READABLE = 0x1
WRITABLE = 0x2

WOULD_BLOCK = -1
ERROR = -2

READ_BUFFER_SIZE = 64 * 1024

ExitCallback = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p)
PollCallback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)


class WorkletOptions(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_int),
        ("memory_limit", ctypes.c_size_t),
        ("platform", ctypes.c_void_p * 8),
    ]


SIGNATURES = {
    "bare_worklet_optimize_for_memory": (ctypes.c_int, [ctypes.c_bool]),
    "bare_worklet_teardown": (ctypes.c_int, []),
    "bare_worklet_create": (
        ctypes.c_int,
        [ctypes.POINTER(WorkletOptions), ctypes.POINTER(ctypes.c_void_p)],
    ),
    "bare_worklet_destroy": (None, [ctypes.c_void_p]),
    "bare_worklet_on_exit": (
        ctypes.c_int,
        [ctypes.c_void_p, ExitCallback, ctypes.c_void_p],
    ),
    "bare_worklet_start": (
        ctypes.c_int,
        [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
        ],
    ),
    "bare_worklet_suspend": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
    "bare_worklet_resume": (ctypes.c_int, [ctypes.c_void_p]),
    "bare_worklet_wakeup": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
    "bare_worklet_terminate": (ctypes.c_int, [ctypes.c_void_p]),
    "bare_ipc_create": (
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
    ),
    "bare_ipc_close": (None, [ctypes.c_void_p]),
    "bare_ipc_end": (None, [ctypes.c_void_p]),
    "bare_ipc_destroy": (None, [ctypes.c_void_p]),
    "bare_ipc_read": (
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t],
    ),
    "bare_ipc_write": (
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t],
    ),
    "bare_ipc_poll_create": (
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
    ),
    "bare_ipc_poll_destroy": (None, [ctypes.c_void_p]),
    "bare_ipc_poll_get_data": (ctypes.c_void_p, [ctypes.c_void_p]),
    "bare_ipc_poll_set_data": (None, [ctypes.c_void_p, ctypes.c_void_p]),
    "bare_ipc_poll_start": (
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.c_int, PollCallback],
    ),
    "bare_ipc_poll_stop": (ctypes.c_int, [ctypes.c_void_p]),
}


def path():
    """The path of the Bare Kit library shipped for the running platform."""
    current = host()
    path = Path(__file__).parent / "prebuilds" / current / library_name(current)

    if not path.is_file():
        raise FileNotFoundError(f"No Bare Kit prebuild for {current}")

    return path


@cache
def library():
    lib = ctypes.CDLL(str(path()))

    for name, (restype, argtypes) in SIGNATURES.items():
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = argtypes

    return lib
