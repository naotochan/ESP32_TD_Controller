"""Minimal OSC 1.0 UDP sender for MicroPython."""
import socket
import struct


def _pad(s):
    n = len(s)
    pad = (4 - (n + 1) % 4) % 4  # extra padding after null terminator
    return s + b'\x00' * (1 + pad)

def _pack_args(args):
    tags = b','
    data = b''
    for a in args:
        if isinstance(a, int):
            tags += b'i'
            data += struct.pack('>i', a)
        elif isinstance(a, float):
            tags += b'f'
            data += struct.pack('>f', a)
        elif isinstance(a, str):
            tags += b's'
            data += _pad(a.encode())
        elif isinstance(a, bool):
            tags += b'T' if a else b'F'
    return _pad(tags), data

def build_message(address, *args):
    addr_bytes = _pad(address.encode())
    tags, data = _pack_args(args)
    return addr_bytes + tags + data


class OSCSender:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, address, *args):
        msg = build_message(address, *args)
        self._sock.sendto(msg, (self.host, self.port))

    def close(self):
        self._sock.close()
