import socket

from src import protocol


def read_packet(sock):
    ptype = sock.recv(1)
    if not ptype:
        return None, None
    length = sock.recv(2)
    plen = int.from_bytes(length, "little")
    payload = sock.recv(plen) if plen else b""
    return ptype[0], payload


def test_send_packet_basic():
    s1, s2 = socket.socketpair()
    try:
        payload = b"abc"
        ok = protocol.send_packet(s1, protocol.PTYPE_CMD, payload)
        assert ok
        ptype, recv_payload = read_packet(s2)
        assert ptype == protocol.PTYPE_CMD
        assert recv_payload == payload
    finally:
        s1.close()
        s2.close()


def test_send_packet_audio_even_bytes():
    s1, s2 = socket.socketpair()
    try:
        payload = b"\x01\x02\x03"  # odd length, last byte should be dropped
        ok = protocol.send_packet(s1, protocol.PTYPE_AUDIO_OUT, payload, audio_chunk=4, audio_sleep_s=0)
        assert ok
        ptype, recv_payload = read_packet(s2)
        assert ptype == protocol.PTYPE_AUDIO_OUT
        assert len(recv_payload) == 2
    finally:
        s1.close()
        s2.close()
