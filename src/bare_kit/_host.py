import platform
import sys

SYSTEMS = {"darwin", "linux", "win32"}
ARCHS = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}


def host():
    """The host triple of the running platform, named as by Bare."""
    arch = ARCHS.get(platform.machine().lower())

    if sys.platform not in SYSTEMS or arch is None:
        raise OSError(f"Unsupported platform {sys.platform}-{platform.machine()}")

    return f"{sys.platform}-{arch}"


def library_name(host):
    if host.startswith("win32"):
        return "bare-kit.dll"

    if host.startswith("darwin"):
        return "libbare-kit.dylib"

    return "libbare-kit.so"
