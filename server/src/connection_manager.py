import logging
import socket
import time
from typing import Callable, Tuple

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(
        self,
        host: str,
        port: int,
        handler: Callable[[socket.socket, Tuple[str, int]], None],
        backlog: int = 5,
        accept_backoff: float = 1.0,
    ):
        self.host = host
        self.port = port
        self.handler = handler
        self.backlog = backlog
        self.accept_backoff = accept_backoff
        self.server_socket = None

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(self.backlog)
        self.server_socket = srv
        log.info("Server listening on %s:%s", self.host, self.port)
        return srv

    def accept_loop(self):
        if self.server_socket is None:
            self.start()

        while True:
            log.info("Ready for next connection...")
            try:
                conn, addr = self.server_socket.accept()
            except KeyboardInterrupt:
                break
            except Exception as exc:
                log.error("Accept failed: %s", exc)
                time.sleep(self.accept_backoff)
                continue

            try:
                self.handler(conn, addr)
            except Exception as exc:
                log.exception("Connection handler error: %s", exc)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                log.info("Disconnected: %s", addr)
                time.sleep(0.1)
