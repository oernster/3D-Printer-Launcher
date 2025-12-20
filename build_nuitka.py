import os
import shutil
import subprocess
import sys


def main() -> None:
    """Build the app into a single-file Windows executable with Nuitka.

    This mirrors the options in [`build_nuitka.cmd`](build_nuitka.cmd:1) so you can simply run:

        python build_nuitka.py

    from the repository root.
    """

    repo_root = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(repo_root, "dist")

    # Clean previous build artifacts
    if os.path.isdir(dist_dir):
        print("Removing existing dist directory...")
        shutil.rmtree(dist_dir)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        # Use the filament.ico as the application icon for the Windows
        # executable so the taskbar and shortcuts show a custom icon.
        "--windows-icon-from-ico=filament.ico",
        "--follow-imports",
        "--output-dir=dist",
        "main.py",
    ]

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=repo_root)


if __name__ == "__main__":  # pragma: no cover
    main()

