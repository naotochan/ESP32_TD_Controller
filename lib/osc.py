"""Minimal OSC 1.0 UDP sender/receiver for MicroPython."""
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


def _read_osc_string(data, offset):
    end = data.find(b'\x00', offset)
    if end < 0:
        return None, offset
    s = data[offset:end]
    next_off = (end + 4) & ~3
    try:
        return s.decode(), next_off
    except Exception:
        return None, offset


def parse_message(data):
    """Parse a single OSC message. Returns (address, [args]) or None."""
    if not data or data[0:1] == b'#':
        return None
    address, offset = _read_osc_string(data, 0)
    if not address or not address.startswith('/'):
        return None
    if offset >= len(data):
        return address, []
    tags, offset = _read_osc_string(data, offset)
    if tags is None or not tags.startswith(','):
        return address, []
    args = []
    for tag in tags[1:]:
        if tag == 'i':
            if offset + 4 > len(data):
                break
            args.append(struct.unpack('>i', data[offset:offset + 4])[0])
            offset += 4
        elif tag == 'f':
            if offset + 4 > len(data):
                break
            args.append(struct.unpack('>f', data[offset:offset + 4])[0])
            offset += 4
        elif tag == 's':
            s, offset = _read_osc_string(data, offset)
            if s is None:
                break
            args.append(s)
        elif tag == 'T':
            args.append(True)
        elif tag == 'F':
            args.append(False)
        else:
            break
    return address, args


def _parse_bundle(data):
    """Unpack OSC bundle → list of (address, [args]). TD OSC Out often sends bundles."""
    # "#bundle\0" (8) + timetag (8)
    if len(data) < 16:
        return []
    offset = 16
    out = []
    while offset + 4 <= len(data):
        size = struct.unpack('>i', data[offset:offset + 4])[0]
        offset += 4
        if size <= 0 or offset + size > len(data):
            break
        chunk = data[offset:offset + size]
        offset += size
        if chunk.startswith(b'#bundle'):
            out.extend(_parse_bundle(chunk))
        else:
            msg = parse_message(chunk)
            if msg:
                out.append(msg)
    return out


def parse_packet(data):
    """Parse OSC message or bundle. Returns list of (address, [args])."""
    if not data:
        return []
    if data.startswith(b'#bundle'):
        return _parse_bundle(data)
    msg = parse_message(data)
    return [msg] if msg else []


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


class OSCReceiver:
    """Non-blocking UDP OSC listener. poll() returns list of (addr, args)."""

    def __init__(self, port, bufsize=1024):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(('0.0.0.0', port))
        self._sock.settimeout(0)
        self._bufsize = bufsize

    def poll(self, max_msgs=8):
        messages = []
        for _ in range(max_msgs):
            try:
                data, _addr = self._sock.recvfrom(self._bufsize)
            except OSError:
                break
            messages.extend(parse_packet(data))
        return messages

    def close(self):
        self._sock.close()
