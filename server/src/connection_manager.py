"""
TCP 서버 연결 관리 모듈
- ESP32 클라이언트와의 TCP 소켓 연결을 관리
- 연결 수락, 핸들러 호출, 에러 처리 담당
"""
import logging
import socket
import time
from typing import Callable, Tuple

log = logging.getLogger(__name__)


class ConnectionManager:
    """TCP 서버 연결 관리자 클래스"""
    
    def __init__(
        self,
        host: str,
        port: int,
        handler: Callable[[socket.socket, Tuple[str, int]], None],
        backlog: int = 5,
        accept_backoff: float = 1.0,
    ):
        # 서버 설정 초기화
        self.host = host
        self.port = port
        self.handler = handler
        self.backlog = backlog
        self.accept_backoff = accept_backoff
        self.server_socket = None

    def start(self):
        # TCP 서버 소켓 생성 및 바인딩
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(self.backlog)
        self.server_socket = srv
        log.info("Server listening on %s:%s", self.host, self.port)
        return srv

    def accept_loop(self):
        # 클라이언트 연결 수락 루프
        if self.server_socket is None:
            self.start()

        while True:
            log.info("Ready for next connection...")
            try:
                # 클라이언트 연결 대기 및 수락
                conn, addr = self.server_socket.accept()
            except KeyboardInterrupt:
                break
            except Exception as exc:
                log.error("Accept failed: %s", exc)
                time.sleep(self.accept_backoff)
                continue

            try:
                # 연결 핸들러 호출
                self.handler(conn, addr)
            except Exception as exc:
                log.exception("Connection handler error: %s", exc)
            finally:
                # 연결 정리
                try:
                    conn.close()
                except Exception:
                    pass
                log.info("Disconnected: %s", addr)
                time.sleep(0.1)