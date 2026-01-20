import socket
import struct
import time

from src.protocol import PTYPE_AUDIO, PTYPE_END, PTYPE_PING, PTYPE_START


class MockESP32:
    def __init__(self, host="127.0.0.1", port=5001):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send_packet(self, ptype, payload=b""):
        header = struct.pack("<BH", ptype & 0xFF, len(payload))
        self.sock.sendall(header + payload)

    def send_ping(self):
        self._send_packet(PTYPE_PING, b"")

    def send_audio_session(self, pcm_bytes: bytes, chunk_size=640):
        self._send_packet(PTYPE_START, b"")
        for i in range(0, len(pcm_bytes), chunk_size):
            self._send_packet(PTYPE_AUDIO, pcm_bytes[i : i + chunk_size])
            time.sleep(0.01)
        self._send_packet(PTYPE_END, b"")
