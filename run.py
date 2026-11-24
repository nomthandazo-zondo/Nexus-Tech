
import os
import sys
import time
import socket
import shutil
import subprocess
from pathlib import Path

# Open the correct project directory
os.chdir(Path(__file__).resolve().parent)


def port_running(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port):
    for _ in range(30):
        if port_running(port):
            return
        time.sleep(1)

    raise RuntimeError(f"Port {port} failed to start")


# Install Python dependencies
try:
    import requests
    import sklearn

except ImportError:
    subprocess.check_call([
        sys.executable, "-m", "pip",
        "install", "requests", "scikit-learn"
    ])


# Detect GitHub Codespaces
if os.environ.get("CODESPACES") == "true":

    print("Starting ShopSmart AI on Codespaces...")

    # Install missing graphical software
    packages = ["Xvfb", "x11vnc", "websockify"]

    if (
        any(not shutil.which(p) for p in packages)
        or not Path("/usr/share/novnc/vnc.html").exists()
    ):

        subprocess.check_call([
            "sudo", "apt-get", "update"
        ])

        subprocess.check_call([
            "sudo", "env",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get", "install", "-y",
            "xvfb", "x11vnc", "novnc",
            "websockify", "python3-tk",
            "x11-utils"
        ])

    # Configure virtual display
    os.environ["DISPLAY"] = ":90"

    display_check = subprocess.run(
        ["xdpyinfo", "-display", ":90"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ) if shutil.which("xdpyinfo") else None

    display_ready = (
        display_check.returncode == 0
        if display_check is not None
        else os.path.exists("/tmp/.X11-unix/X90")
    )

    if not display_ready:

        subprocess.Popen([
            "Xvfb", ":90",
            "-screen", "0", "1440x900x24",
            "-nolisten", "tcp"
        ])

        time.sleep(3)

    # Create VNC password only if missing
    password_file = Path.home() / ".vnc" / "passwd"

    if not password_file.exists():

        print("Create your VNC password:")

        subprocess.check_call([
            "x11vnc", "-storepasswd"
        ])

    # Start VNC server
    if not port_running(5907):

        subprocess.Popen([
            "x11vnc",
            "-display", ":90",
            "-localhost",
            "-rfbauth", str(password_file),
            "-forever",
            "-shared",
            "-rfbport", "5907"
        ])

    wait_for_port(5907)

    # Remove directory listing
    index_file = "/usr/share/novnc/index.html"

    subprocess.check_call([
        "sudo", "ln", "-sf",
        "/usr/share/novnc/vnc.html",
        index_file
    ])

    # Start graphical viewer
    if not port_running(6080):

        subprocess.Popen([
            "websockify",
            "--web=/usr/share/novnc",
            "6080", "localhost:5907"
        ])

    wait_for_port(6080)

    print("Graphical viewer is ready.")
    print("Open private port 6080.")

    # Display direct connection link
    name = os.environ.get("CODESPACE_NAME")
    domain = os.environ.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN",
        "app.github.dev"
    )

    if name:
        print(
            f"https://{name}-6080.{domain}"
            "/vnc.html?autoconnect=true"
        )


# Start Ollama if installed
if shutil.which("ollama"):

    if not port_running(11434):

        subprocess.Popen(["ollama", "serve"])
        time.sleep(3)


# Launch actual ShopSmart AI application
print("Launching ShopSmart AI...")

subprocess.check_call([
    sys.executable, "shopsmart.py"
])

