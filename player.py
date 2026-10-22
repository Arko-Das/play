import json
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

SOCKET = (
    "/data/data/com.termux/files/usr/tmp/"
    "spoiderman-player.sock"
)

RESET = "\033[0m"
BOLD = "\033[1m"
COLORS = [
    "\033[38;5;196m",
    "\033[38;5;202m",
    "\033[38;5;226m",
    "\033[38;5;46m",
    "\033[38;5;51m",
    "\033[38;5;93m",
    "\033[38;5;201m",
]
stop_animation = threading.Event()


def get_title(url):
    result = subprocess.run(
        [
            "yt-dlp", "--no-warnings", "--skip-download",
            "--print", "%(title)s", url
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Could not get the YouTube title.")
    return result.stdout.strip().splitlines()[0]


def get_song_length(sock):
    try:
        sock.sendall((
            json.dumps({
                "command": ["get_property", "duration"],
                "request_id": 10
            }) + "\n"
        ).encode())
        sock.settimeout(0.2)
        buffer = ""
        deadline = time.monotonic() + 0.3

        while time.monotonic() < deadline:
            try:
                buffer += sock.recv(4096).decode(
                    "utf-8", "replace"
                )
            except socket.timeout:
                break

            for line in buffer.splitlines():
                try:
                    reply = json.loads(line)
                    if reply.get("request_id") == 10:
                        return reply.get("data")
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    return None


def send_command(sock, command, request_id):
    try:
        sock.sendall((
            json.dumps({
                "command": command,
                "request_id": request_id
            }) + "\n"
        ).encode())
    except OSError:
        pass


def animate(sock, title):
    random.seed()
    position = 0.0
    duration = None
    last_duration_check = 0.0
    last_position_request = 0.0
    pending_position = None
    request_id = 20
    buffer = ""
    paused = False
    sock.settimeout(0.03)

    while not stop_animation.is_set():
        now = time.monotonic()

        if now - last_duration_check > 5:
            duration = get_song_length(sock)
            last_duration_check = now
            # Restore the normal socket timeout.
            sock.settimeout(0.03)

        if pending_position is None and now - last_position_request > 0.2:
            request_id += 1
            pending_position = request_id
            send_command(
                sock, ["get_property", "playback-time"], request_id
            )
            last_position_request = now

        try:
            data = sock.recv(8192).decode("utf-8", "replace")
            buffer += data
        except socket.timeout:
            pass
        except OSError:
            break

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue

            rid = reply.get("request_id")

            if rid == pending_position:
                pending_position = None
                if isinstance(reply.get("data"), (int, float)):
                    position = reply["data"]

            if reply.get("event") == "property-change":
                if reply.get("name") == "pause":
                    paused = bool(reply.get("data"))

        width = shutil.get_terminal_size((80, 24)).columns
        width = max(35, min(width, 100))
        bar_count = min(36, max(15, width - 10))
        levels = []

        for i in range(bar_count):
            wave = (
                abs(math.sin(now * 3.4 + i * 0.57))
                + abs(math.sin(now * 2.1 - i * 0.31))
            ) / 2
            height = int(1 + wave * 7 + random.random() * 3)
            levels.append(max(1, min(10, height)))

        output = [
            "\033[H\033[2J",
            f"{COLORS[4]}{BOLD}"
            "╔══════════════════════════════════════╗\n",
            "║       🕷 BUTTERFLY PLAYER 🦋               ║\n",
            "╚══════════════════════════════════════╝"
            f"{RESET}\n",
            f"{COLORS[3]}♪ NOW PLAYING{RESET}\n",
            f"{title[:width - 2]}\n\n",
        ]

        max_height = 10
        for row in range(max_height, 0, -1):
            line = "  "
            for i, height in enumerate(levels):
                color = COLORS[(i + int(now * 8)) % len(COLORS)]
                line += (
                    f"{color}█{RESET} "
                    if height >= row else "  "
                )
            output.append(line + "\n")

        output.append("\n")
        if duration and duration > 0:
            fraction = min(1.0, max(0.0, position / durat
