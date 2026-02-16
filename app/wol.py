import socket



def normalize_mac(mac: str) -> bytes:
    clean = mac.replace(":", "").replace("-", "")
    return bytes.fromhex(clean)



def send_magic_packet(mac: str, broadcast: str, port: int = 9) -> None:
    mac_bytes = normalize_mac(mac)
    packet = b"\xff" * 6 + mac_bytes * 16

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.sendto(packet, (broadcast, port))
    finally:
        sock.close()
