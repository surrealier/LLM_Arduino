import socket

from src.connection_manager import ConnectionManager


def test_connection_manager_start():
    def handler(conn, addr):
        conn.close()

    manager = ConnectionManager("127.0.0.1", 0, handler)
    srv = manager.start()
    host, port = srv.getsockname()
    assert host in ("127.0.0.1", "0.0.0.0")
    assert port > 0
    srv.close()
