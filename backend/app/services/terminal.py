from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import struct
import subprocess
import termios
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TerminalSession:
    challenge_id: str
    container_name: str
    master_fd: int
    process: subprocess.Popen[bytes]
    output_queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=400))
    output_tail: bytearray = field(default_factory=bytearray)
    subscribers: int = 0
    pump_started: bool = False
    closed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    loop: asyncio.AbstractEventLoop | None = None

    def write(self, data: str) -> None:
        payload = data.encode("utf-8", "replace")
        if self.closed:
            return
        try:
            os.write(self.master_fd, payload)
        except OSError:
            self.closed = True

    def resize(self, rows: int, cols: int) -> None:
        rows = max(5, min(100, int(rows)))
        cols = max(20, min(300, int(cols)))
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    async def pump(self) -> None:
        self.loop = asyncio.get_running_loop()
        while not self.closed:
            try:
                data = await asyncio.to_thread(os.read, self.master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            with self.lock:
                self.output_tail.extend(data)
                if len(self.output_tail) > 30000:
                    del self.output_tail[:-30000]
                active = self.subscribers > 0
            if active:
                try:
                    self.output_queue.put_nowait(data)
                except asyncio.QueueFull:
                    # Drop the oldest queued chunk rather than allowing runaway memory use.
                    try:
                        self.output_queue.get_nowait()
                        self.output_queue.put_nowait(data)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        pass
        self.closed = True

    def tail(self) -> bytes:
        with self.lock:
            return bytes(self.output_tail)


class TerminalManager:
    """Persistent logical Bash sessions backed by the Docker CLI's PTY attachment.

    The command is fixed and the target is an application-owned container name. Browser
    text is written to the PTY; it is never interpolated into a host command.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}
        self._guard = asyncio.Lock()

    async def get_or_start(self, challenge_id: str, container_name: str) -> tuple[TerminalSession, bool]:
        async with self._guard:
            existing = self._sessions.get(challenge_id)
            if existing and existing.process.poll() is None and not existing.closed:
                return existing, False
            master_fd, slave_fd = pty.openpty()
            rows, cols = 28, 100
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
            prompt = f"redpanda@lab-{challenge_id[-2:]}:/workspace$ "
            argv = [
                "docker", "exec", "-it", "--user", "redpanda", "--workdir", "/workspace",
                "-e", "HISTFILE=/workspace/.bash_history", "-e", f"PS1={prompt}",
                "-e", "TERM=xterm-256color", container_name,
                # tmux keeps the Bash session alive when the native API process restarts.
                # This fixed command never includes user-supplied terminal input.
                "tmux", "new-session", "-A", "-s", "redpanda-shell",
                "/bin/bash --noprofile --norc -i",
            ]
            try:
                process = subprocess.Popen(
                    argv, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                    start_new_session=True, close_fds=True,
                    env={**os.environ, "TERM": "xterm-256color", "LANG": "C.UTF-8"},
                )
            except OSError as exc:
                os.close(master_fd); os.close(slave_fd)
                raise RuntimeError("Could not start the Docker terminal attachment. Check that the Docker CLI is installed.") from exc
            finally:
                try: os.close(slave_fd)
                except OSError: pass
            session = TerminalSession(challenge_id, container_name, master_fd, process)
            self._sessions[challenge_id] = session
            session.pump_started = True
            asyncio.create_task(session.pump(), name=f"redpanda-terminal-pump-{challenge_id}")
            return session, True

    async def close(self, challenge_id: str) -> None:
        async with self._guard:
            session = self._sessions.pop(challenge_id, None)
        if session is not None:
            session.closed = True
            try:
                session.process.terminate()
                await asyncio.to_thread(session.process.wait, timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try: session.process.kill()
                except OSError: pass
            try: os.close(session.master_fd)
            except OSError: pass

    async def close_all(self) -> None:
        for key in list(self._sessions):
            await self.close(key)
