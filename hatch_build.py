import os
import runpy

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# The oldest platforms the prebuilds run on: they are linked against glibc 2.34
# and target macOS 13.
TAGS = {
    "darwin-arm64": "macosx_13_0_arm64",
    "darwin-x64": "macosx_13_0_x86_64",
    "linux-arm64": "manylinux_2_34_aarch64",
    "linux-x64": "manylinux_2_34_x86_64",
    "win32-arm64": "win_arm64",
    "win32-x64": "win_amd64",
}


class CustomBuildHook(BuildHookInterface):
    """Include the prebuild for one host in the wheel and tag it for that host.

    The host is taken from ``BARE_KIT_HOST`` and defaults to the platform the
    wheel is built on.
    """

    def initialize(self, version, build_data):
        if self.target_name != "wheel" or version == "editable":
            return

        helpers = runpy.run_path(os.path.join(self.root, "src/bare_kit/_host.py"))

        requested = os.environ.get("BARE_KIT_HOST")
        host = requested or helpers["host"]()

        if host not in TAGS:
            raise ValueError(f"Unknown host '{host}'")

        prebuild = f"src/bare_kit/prebuilds/{host}/{helpers['library_name'](host)}"

        if not os.path.isfile(os.path.join(self.root, prebuild)):
            # Built without prebuilds, such as from the sdist, the wheel is left
            # pure and fails to load the library at runtime instead.
            if requested is None:
                return

            raise FileNotFoundError(f"No prebuild at '{prebuild}'")

        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{TAGS[host]}"
        build_data["force_include"][prebuild] = prebuild.removeprefix("src/")
