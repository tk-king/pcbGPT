from __future__ import annotations

import os
import socket
import threading
import time

import webview

from backend.runtime_paths import prepare_packaged_runtime


HOST = "127.0.0.1"


class DesktopApi:
    def __init__(self) -> None:
        self.window = None



def _reserve_local_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _wait_for_port(host: str, port: int, timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


class ServerThread(threading.Thread):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = None
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            import uvicorn
            from backend.agent.tools.fastapi_runner import app

            config = uvicorn.Config(
                app,
                host=self.host,
                port=self.port,
                reload=False,
                ws_ping_interval=60.0,
                ws_ping_timeout=300.0,
                log_level="info",
            )
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as exc:  # noqa: BLE001
            self.error = exc

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


def _start_server() -> tuple[ServerThread, str]:
    runtime_dir = prepare_packaged_runtime()
    os.chdir(runtime_dir)
    port = _reserve_local_port(HOST)

    server_thread = ServerThread(HOST, port)
    server_thread.start()

    url = f"http://{HOST}:{port}"
    if _wait_for_port(HOST, port, timeout_s=30.0):
        return server_thread, url

    if server_thread.error is not None:
        raise RuntimeError(f"Failed to start local server: {server_thread.error}")
    raise RuntimeError("Timed out while starting the local PCBGPT server.")


def main() -> None:
    server_thread, url = _start_server()
    api = DesktopApi()

    window = webview.create_window(
        "pcbGPT",
        url,
        width=1440,
        height=960,
        min_size=(1024, 720),
        text_select=True,
        js_api=api,
    )
    api.window = window

    def on_closing() -> bool:
        server_thread.stop()
        return True

    window.events.closing += on_closing
    webview.start(debug=False)


if __name__ == "__main__":
    main()
