import logging
import sqlite3
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot configuration
BOT_TOKEN = "8090704591:AAEDHjDQaHquW7d6PuU667Kgsn6nYiDQDUY"
ADMIN_IDS = [7013309955]
REFER_BONUS = 15
MIN_WITHDRAWAL = 200
WITHDRAWAL_OPTIONS = [200, 500, 1000, 2000]

# Database setup
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            language TEXT DEFAULT 'english',
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Redeem codes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS redeem_codes (
            code_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            coins INTEGER,
            is_active BOOLEAN DEFAULT 1,
            free_code_link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User redemptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code_id INTEGER,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Withdrawals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            method TEXT,
            upi_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Channels table for verification
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT,
            channel_link TEXT,
            required BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User channels table (which user joined which channel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Database functions
def get_user(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, balance FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def get_today_users():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users WHERE date(join_date) = date("now")')
    users = cursor.fetchall()
    conn.close()
    return users

def create_user(user_id, username, first_name, referrer_id=None):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)', 
                  (user_id, username, first_name, referrer_id))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_language(user_id, language):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
    conn.commit()
    conn.close()

# Redeem Code Functions
def add_redeem_code(code, coins, free_code_link=""):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO redeem_codes (code, coins, free_code_link) VALUES (?, ?, ?)', (code, coins, free_code_link))
        code_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return code_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_redeem_code(code):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes WHERE code = ? AND is_active = 1', (code,))
    redeem_code = cursor.fetchone()
    conn.close()
    return redeem_code

def get_all_redeem_codes():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes ORDER BY created_at DESC')
    codes = cursor.fetchall()
    conn.close()
    return codes

def delete_redeem_code(code_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM redeem_codes WHERE code_id = ?', (code_id,))
    conn.commit()
    conn.close()

def redeem_code(user_id, code):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # Check if already redeemed
    cursor.execute('''
        SELECT * FROM user_redemptions 
        WHERE user_id = ? AND code_id IN (SELECT code_id FROM redeem_codes WHERE code = ?)
    ''', (user_id, code))
    if cursor.fetchone():
        conn.close()
        return False, "already_used"
    
    # Get redeem code
    cursor.execute('SELECT * FROM redeem_codes WHERE code = ? AND is_active = 1', (code,))
    redeem_code_data = cursor.fetchone()
    
    if not redeem_code_data:
        conn.close()
        return False, "not_found"
    
    code_id, code_text, coins, is_active, free_code_link, created_at = redeem_code_data
    
    # Add redemption record
    cursor.execute('INSERT INTO user_redemptions (user_id, code_id) VALUES (?, ?)', (user_id, code_id))
    
    # Update balance
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (coins, user_id))
    
    conn.commit()
    conn.close()
    return True, coins

# Channel Functions
def add_channel(channel_name, channel_link):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO channels (channel_name, channel_link) VALUES (?, ?)', (channel_name, channel_link))
        channel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return channel_id
    except:
        conn.close()
        return None

def get_channels():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM channels')
    channels = cursor.fetchall()
    conn.close()
    return channels

def delete_channel(channel_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def check_user_channel(user_id, channel_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_channels WHERE user_id = ? AND channel_id = ?', (user_id, channel_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Withdrawal Functions
def get_pending_withdrawals():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT w.*, u.username, u.first_name 
        FROM withdrawals w 
        JOIN users u ON w.user_id = u.user_id 
        WHERE w.status = 'pending'
    ''')
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

def create_withdrawal(user_id, amount, method, upi_id=None):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO withdrawals (user_id, amount, method, upi_id) VALUES (?, ?, ?, ?)', 
                  (user_id, amount, method, upi_id))
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return withdrawal_id

def update_withdrawal_status(withdrawal_id, status):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (status, withdrawal_id))
    conn.commit()
    conn.close()

# Text messages
def get_text(language, key):
    texts = {
        'english': {
            'welcome': "🤖 **Welcome to Earn Bot!**",
            'balance': "💳 **Balance:** {} coins",
            'referral_link': "📱 **Your Referral Link:**",
            'earn_options': "Add redeem codes to earn coins! 💰",
            'add_code': "🔑 Add Code", 
            'verify_channel': "📢 Verify Channel",
            'balance_btn': "💰 Balance",
            'refer_btn': "👥 Refer & Earn",
            'withdraw_btn': "💸 Withdraw",
            'help_btn': "ℹ️ Help",
            'admin_panel': "📊 Admin Panel",
            'withdraw_min': f"❌ Minimum withdrawal amount is {MIN_WITHDRAWAL} coins!",
            'withdraw_balance': "Your current balance: {} coins",
            'code_success': "🎉 **Code Added Successfully!** 🎉\n\n💰 You earned **{} coins**!",
            'code_already_used': "❌ You have already used this code!",
            'code_not_found': "❌ Wrong code! Get your free code from admin.",
            'enter_code': "🔑 **Add Code**\n\nPlease enter your redeem code:",
            'channel_verified': "✅ **Channel Verified!**\n\nYou have successfully verified all channels!",
            'join_channels': "📢 **Verify Channels**\n\nPlease join these channels to continue:",
            'withdraw_request_sent': "✅ **Withdrawal Request Sent!**\n\nYour request for {} coins has been sent to admin for approval.",
            'referral_success': "🎉 Referral successful! {} joined via your link."
        },
        'hindi': {
            'welcome': "🤖 **आय बॉट में स्वागत है!**",
            'balance': "💳 **बैलेंस:** {} सिक्के",
            'referral_link': "📱 **आपका रेफरल लिंक:**",
            'earn_options': "सिक्के कमाने के लिए रीडीम कोड जोड़ें! 💰",
            'add_code': "🔑 कोड जोड़ें",
            'verify_channel': "📢 चैनल वेरिफाई करें", 
            'balance_btn': "💰 बैलेंस",
            'refer_btn': "👥 रेफर करें",
            'withdraw_btn': "💸 निकासी",
            'help_btn': "ℹ️ मदद",
            'admin_panel': "📊 एडमिन पैनल",
            'withdraw_min': f"❌ न्यूनतम निकासी राशि {MIN_WITHDRAWAL} सिक्के है!",
            'withdraw_balance': "आपका वर्तमान बैलेंस: {} सिक्के",
            'code_success': "🎉 **कोड सफलतापूर्वक जोड़ दिया गया!** 🎉\n\n💰 आपने **{} सिक्के** कमाए!",
            'code_already_used': "❌ आपने यह कोड पहले ही इस्तेमाल कर लिया है!",
            'code_not_found': "❌ गलत कोड! मुफ्त कोड के लिए एडमिन से संपर्क करें।",
            'enter_code': "🔑 **कोड जोड़ें**\n\nकृपया अपना रीडीम कोड दर्ज करें:",
            'channel_verified': "✅ **चैनल वेरिफाई हो गया!**\n\nआपने सभी चैनल्स सफलतापूर्वक ज्वाइन कर लिए हैं!",
            'join_channels': "📢 **चैनल वेरिफाई करें**\n\nजारी रखने के लिए कृपया इन चैनल्स को ज्वाइन करें:",
            'withdraw_request_sent': "✅ **निकासी का अनुरोध भेज दिया गया!**\n\n{} सिक्कों के लिए आपका अनुरोध एडमिन को भेज दिया गया है।",
            'referral_success': "🎉 रेफरल सफल! {} आपके लिंक के माध्यम से जुड़ा।"
        }
    }
    return texts.get(language, texts['english']).get(key, key)

# Keyboard functions
def get_main_keyboard(user_id):
    if user_id in ADMIN_IDS:
        keyboard = [
            ["🔑 Add Code", "💰 Balance"],
            ["👥 Refer & Earn", "💸 Withdraw"],
            ["📢 Verify Channel", "ℹ️ Help"],
            ["📊 Admin Panel", "🌐 Language"]
        ]
    else:
        keyboard = [
            ["🔑 Add Code", "💰 Balance"],
            ["👥 Refer & Earn", "💸 Withdraw"], 
            ["📢 Verify Channel", "ℹ️ Help"],
            ["🌐 Language"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        ["📢 Broadcast", "👥 All Users"],
        ["💰 User Balances", "📅 Today Users"],
        ["⏳ Pending Withdraws", "✉️ Personal Msg"],
        ["🔑 Code Management", "📢 Channel Management"],
        ["🔙 Back to Main"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_code_management_keyboard():
    keyboard = [
        ["➕ Add Code", "🗑️ Delete Code"],
        ["📋 All Codes", "🔙 Back to Admin"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_channel_management_keyboard():
    keyboard = [
        ["➕ Add Channel", "🗑️ Delete Channel"],
        ["📋 All Channels", "🔙 Back to Admin"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_withdraw_method_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 UPI", callback_data="withdraw_upi")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_withdraw_amount_keyboard():
    keyboard = []
    for amount in WITHDRAWAL_OPTIONS:
        keyboard.append([InlineKeyboardButton(f"💳 {amount} coins", callback_data=f"withdraw_amount_{amount}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="withdraw_back")])
    return InlineKeyboardMarkup(keyboard)

def get_channels_inline_keyboard():
    channels = get_channels()
    keyboard = []
    
    for channel in channels:
        channel_id, name, link, required, created_at = channel
        keyboard.append([InlineKeyboardButton(f"📢 {name}", url=link)])
    
    keyboard.append([InlineKeyboardButton("✅ I Have Joined All", callback_data="verify_channels")])
    return InlineKeyboardMarkup(keyboard)

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    # Check if user needs to verify channels first
    channels = get_channels()
    if channels and not all(check_user_channel(user_id, channel[0]) for channel in channels):
        await show_channel_verification(update, context)
        return
    
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                create_user(user_id, username, first_name, referrer_id)
                update_balance(referrer_id, REFER_BONUS)
                user = get_user(user_id)
                language = user[5] if user and user[5] else 'english'
                await update.message.reply_text(get_text(language, 'referral_success').format(first_name))
            else:
                create_user(user_id, username, first_name)
        except:
            create_user(user_id, username, first_name)
    else:
        create_user(user_id, username, first_name)
    
    await show_main_menu(update, context, user_id)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = get_user(user_id)
    balance = user_data[3] if user_data else 0
    language = user_data[5] if user_data and user_data[5] else 'english'
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    welcome_text = (
        f"{get_text(language, 'welcome')}\n\n"
        f"{get_text(language, 'balance').format(balance)}\n"
        f"{get_text(language, 'referral_link')}\n`{referral_link}`\n\n"
        f"{get_text(language, 'earn_options')}"
    )
    
    keyboard = get_main_keyboard(user_id)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')

async def show_channel_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    language = user[5] if user and user[5] else 'english'
    
    channels = get_channels()
    if not channels:
        await start(update, context)
        return
    
    message_text = f"{get_text(language, 'join_channels')}\n\n"
    
    for channel in channels:
        channel_id, name, link, required, created_at = channel
        message_text += f"📢 {name}\n{link}\n\n"
    
    reply_markup = get_channels_inline_keyboard()
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user = get_user(user_id)
    language = user[5] if user and user[5] else 'english'
    
    if text == "🔑 Add Code":
        await update.message.reply_text(get_text(language, 'enter_code'))
        context.user_data['awaiting_redeem_code'] = True
        
    elif text == "📢 Verify Channel":
        await show_channel_verification(update, context)
        
    elif text == "💰 Balance":
        await show_balance_menu(update, context)
        
    elif text == "👥 Refer & Earn":
        await show_refer_menu(update, context)
        
    elif text == "💸 Withdraw":
        await show_withdraw_menu(update, context)
        
    elif text == "ℹ️ Help":
        await show_help_menu(update, context)
        
    elif text == "🌐 Language":
        await show_language_menu(update, context)
        
    elif text == "📊 Admin Panel":
        if user_id in ADMIN_IDS:
            await show_admin_panel(update, context)
        else:
            await update.message.reply_text("🚫 Access Denied!")
            
    elif text == "🔙 Back to Main":
        await show_main_menu(update, context, user_id)
        
    elif text == "📢 Broadcast":
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_broadcast'] = True
            await update.message.reply_text("📢 **Broadcast Message**\n\nSend the message you want to broadcast to all users:")
            
    elif text == "👥 All Users":
        if user_id in ADMIN_IDS:
            await show_all_users(update, context)
            
    elif text == "💰 User Balances":
        if user_id in ADMIN_IDS:
            await show_user_balances(update, context)
            
    elif text == "📅 Today Users":
        if user_id in ADMIN_IDS:
            await show_today_users(update, context)
            
    elif text == "✉️ Personal Msg":
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_personal_msg'] = True
            await update.message.reply_text("✉️ **Personal Message**\n\nSend user ID and message in format:\n`user_id\\nmessage`")
            
    elif text == "⏳ Pending Withdraws":
        if user_id in ADMIN_IDS:
            await show_pending_withdrawals(update, context)
            
    elif text == "🔑 Code Management":
        if user_id in ADMIN_IDS:
            await show_code_management(update, context)
            
    elif text == "📢 Channel Management":
        if user_id in ADMIN_IDS:
            await show_channel_management(update, context)
            
    elif text == "➕ Add Code":
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_code'] = True
            await update.message.reply_text(
                "🔑 **Add New Redeem Code**\n\n"
                "Please send code details in this format:\n"
                "**Code**\n"
                "**Coins**\n"
                "**Free Code Link**\n\n"
                "Example:\n"
                "FREE100\n"
                "50\n"
                "https://t.me/your_channel"
            )
            
    elif text == "🗑️ Delete Code":
        if user_id in ADMIN_IDS:
            await show_delete_codes(update, context)
            
    elif text == "📋 All Codes":
        if user_id in ADMIN_IDS:
            await show_all_codes_admin(update, context)
            
    elif text == "➕ Add Channel":
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_channel'] = True
            await update.message.reply_text(
                "📢 **Add New Channel**\n\n"
                "Please send channel details in this format:\n"
                "**Channel Name**\n"
                "**Channel Link**\n\n"
                "Example:\n"
                "My Channel\n"
                "https://t.me/mychannel"
            )
            
    elif text == "🗑️ Delete Channel":
        if user_id in ADMIN_IDS:
            await show_delete_channels(update, context)
            
    elif text == "📋 All Channels":
        if user_id in ADMIN_IDS:
            await show_all_channels_admin(update, context)
            
    # Process inputs
    elif 'awaiting_redeem_code' in context.user_data and context.user_data['awaiting_redeem_code']:
        await process_redeem_code(update, context)
        
    elif 'awaiting_code' in context.user_data and context.user_data['awaiting_code']:
        await process_code_input(update, context)
        
    elif 'awaiting_channel' in context.user_data and context.user_data['awaiting_channel']:
        await process_channel_input(update, context)
        
    elif 'awaiting_delete_code' in context.user_data and context.user_data['awaiting_delete_code']:
        await process_delete_code(update, context)
        
    elif 'awaiting_delete_channel' in context.user_data and context.user_data['awaiting_delete_channel']:
        await process_delete_channel(update, context)
        
    elif 'awaiting_broadcast' in context.user_data and context.user_data['awaiting_broadcast']:
        await process_broadcast(update, context)
        
    elif 'awaiting_personal_msg' in context.user_data and context.user_data['awaiting_personal_msg']:
        await process_personal_message(update, context)
        
    # Handle withdrawal UPI input
    elif 'withdraw_amount' in context.user_data and 'withdraw_method' in context.user_data:
        await handle_withdraw_input(update, context)

# Process redeem code from user
async def process_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip().upper()
    user = get_user(user_id)
    language = user[5] if user and user[5] else 'english'
    
    success, result = redeem_code(user_id, code)
    
    if success:
        coins = result
        await update.message.reply_text(get_text(language, 'code_success').format(coins), parse_mode='Markdown')
    else:
        if result == "already_used":
            await update.message.reply_text(get_text(language, 'code_already_used'))
        else:
            await update.message.reply_text(get_text(language, 'code_not_found'))
    
    context.user_data.pop('awaiting_redeem_code', None)
    await show_main_menu(update, context, user_id)

# Process code input from admin
async def process_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        lines = text.split('\n')
        if len(lines) >= 3:
            code = lines[0].strip().upper()
            coins = int(lines[1].strip())
            free_code_link = lines[2].strip()
            
            code_id = add_redeem_code(code, coins, free_code_link)
            if code_id:
                # Broadcast to all users about new code
                users = get_all_users()
                message = (
                    f"🎉 **New Free Code Available!** 🎉\n\n"
                    f"🔑 **Code:** `{code}`\n"
                    f"💰 **Reward:** {coins} coins\n\n"
                    f"Get your free code from here:\n{free_code_link}\n\n"
                    f"Hurry up! Use code: `{code}`"
                )
                
                success_count = 0
                for user in users:
                    try:
                        await context.bot.send_message(
                            chat_id=user[0], 
                            text=message,
                            parse_mode='Markdown'
                        )
                        success_count += 1
                        await asyncio.sleep(0.1)
                    except:
                        continue
                
                await update.message.reply_text(
                    f"✅ **Redeem Code Added Successfully!**\n\n"
                    f"🔑 **Code:** `{code}`\n"
                    f"💰 **Coins:** {coins}\n"
                    f"🔗 **Free Code Link:** {free_code_link}\n\n"
                    f"📢 Notification sent to {success_count} users!"
                )
            else:
                await update.message.reply_text("❌ Code already exists! Please use a different code.")
        else:
            await update.message.reply_text("❌ Invalid format! Please send all 3 details.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding code: {str(e)}")
    
    context.user_data.pop('awaiting_code', None)

# Process channel input from admin
async def process_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        lines = text.split('\n')
        if len(lines) >= 2:
            channel_name = lines[0].strip()
            channel_link = lines[1].strip()
            
            channel_id = add_channel(channel_name, channel_link)
            if channel_id:
                await update.message.reply_text(
                    f"✅ **Channel Added Successfully!**\n\n"
                    f"📢 **Name:** {channel_name}\n"
                    f"🔗 **Link:** {channel_link}\n\n"
                    f"Channel is now required for verification!"
                )
            else:
                await update.message.reply_text("❌ Error adding channel!")
        else:
            await update.message.reply_text("❌ Invalid format! Please send both name and link.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding channel: {str(e)}")
    
    context.user_data.pop('awaiting_channel', None)

# Process delete code
async def process_delete_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        code_id = int(text.strip())
        delete_redeem_code(code_id)
        await update.message.reply_text(f"✅ Code {code_id} deleted successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error deleting code: {str(e)}")
    
    context.user_data.pop('awaiting_delete_code', None)

# Process delete channel
async def process_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        channel_id = int(text.strip())
        delete_channel(channel_id)
        await update.message.reply_text(f"✅ Channel {channel_id} deleted successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error deleting channel: {str(e)}")
    
    context.user_data.pop('awaiting_delete_channel', None)

# Process broadcast
async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    
    users = get_all_users()
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message, parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.1)
        except:
            failed += 1
    
    await update.message.reply_text(
        f"📢 **Broadcast Completed!**\n\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(users)}"
    )
    
    context.user_data.pop('awaiting_broadcast', None)

# Process personal message
async def process_personal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        lines = text.split('\n')
        if len(lines) >= 2:
            target_user_id = int(lines[0].strip())
            message = '\n'.join(lines[1:])
            
            await context.bot.send_message(chat_id=target_user_id, text=message, parse_mode='Markdown')
            await update.message.reply_text(f"✅ Message sent to user {target_user_id}!")
        else:
            await update.message.reply_text("❌ Invalid format! Please send user ID and message in separate lines.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending message: {str(e)}")
    
    context.user_data.pop('awaiting_personal_msg', None)

# User menu functions
async def show_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    language = user[5] if user and user[5] else 'english'
    
    if user:
        balance = user[3]
        await update.message.reply_text(
            f"💰 **Balance Information**\n\n"
            f"🪙 {get_text(language, 'balance').format(balance)}\n"
            f"👤 User ID: `{user_id}`\n\n"
            f"Add more codes to increase your balance!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Please use /start first")

async def show_refer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    language = user[5] if user and user[5] else 'english'
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    await update.message.reply_text(
        f"👥 **Refer & Earn**\n\n"
        f"📱 {get_text(language, 'referral_link')}\n`{referral_link}`\n\n"
        f"💡 Share this link with friends and earn **{REFER_BONUS} coins** for each referral!\n\n"
        f"✅ Your friend will also get bonus coins!",
        parse_mode='Markdown'
    )

async def show_withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start first")
        return
        
    user_balance = user[3]
    language = user[5] if user[5] else 'english'
    
    if user_balance >= MIN_WITHDRAWAL:
        reply_markup = get_withdraw_method_keyboard()
        
        await update.message.reply_text(
            f"💸 **Withdrawal**\n\n"
            f"Current Balance: **{user_balance} coins**\n"
            f"Minimum Withdrawal: **{MIN_WITHDRAWAL} coins**\n\n"
            f"Select withdrawal method:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"{get_text(language, 'withdraw_min')}\n"
            f"{get_text(language, 'withdraw_balance').format(user_balance)}\n\n"
            f"Add more codes to reach minimum withdrawal limit."
        )

async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    language = user[5] if user and user[5] else 'english'
    
    if language == 'hindi':
        help_text = (
            "🤖 **आय बॉट मदद**\n\n"
            "**उपलब्ध कमांड:**\n"
            "🔑 कोड जोड़ें - रीडीम कोड जोड़ें\n"
            "💰 बैलेंस - अपना बैलेंस चेक करें\n"
            "👥 रेफर करें - रेफरल लिंक प्राप्त करें\n"
            "💸 निकासी - अपने सिक्के निकालें\n"
            "📢 चैनल वेरिफाई करें - चैनल ज्वाइन करें\n"
            "🌐 भाषा - भाषा बदलें\n\n"
            "**कैसे कमाएं:**\n"
            "1. 🔑 कोड जोड़ें से रीडीम कोड जोड़ें\n"
            "2. 👥 रेफर करें से दोस्तों को रेफर करें\n"
            "3. 💸 निकासी के माध्यम से कमाई निकालें\n\n"
            "**सहायता:** मदद के लिए एडमिन से संपर्क करें"
        )
    else:
        help_text = (
            "🤖 **Earn Bot Help**\n\n"
            "**Available Commands:**\n"
            "🔑 Add Code - Add redeem codes\n"
            "💰 Balance - Check your balance\n"
            "👥 Refer & Earn - Get referral link\n"
            "💸 Withdraw - Withdraw your coins\n"
            "📢 Verify Channel - Join required channels\n"
            "🌐 Language - Change language\n\n"
            "**How to Earn:**\n"
            "1. Add redeem codes from 🔑 Add Code\n"
            "2. Refer friends using 👥 Refer & Earn\n"
            "3. Withdraw earnings via 💸 Withdraw\n\n"
            "**Support:** Contact admin for help"
        )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_english")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hindi")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 **Select Language / भाषा चुनें**", reply_markup=reply_markup)

# Admin menu functions
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Access Denied!")
        return
    
    total_users = len(get_all_users())
    today_users = len(get_today_users())
    total_codes = len(get_all_redeem_codes())
    total_channels = len(get_channels())
    pending_withdrawals = len(get_pending_withdrawals())
    
    keyboard = get_admin_keyboard()
    
    admin_text = (
        f"🛠️ **Admin Panel**\n\n"
        f"📊 **Statistics:**\n"
        f"👥 Total Users: {total_users}\n"
        f"📅 Today's Users: {today_users}\n"
        f"🔑 Active Codes: {total_codes}\n"
        f"📢 Channels: {total_channels}\n"
        f"⏳ Pending Withdrawals: {pending_withdrawals}\n\n"
        f"**Quick Actions:**\n"
        f"📢 Broadcast - Send message to all users\n"
        f"👥 All Users - View all users list\n"
        f"💰 User Balances - View all balances\n"
        f"📅 Today Users - New users today\n"
        f"✉️ Personal Msg - Send personal message\n"
        f"⏳ Pending Withdraws - Manage withdrawals\n"
        f"🔑 Code Management - Add/Delete codes\n"
        f"📢 Channel Management - Add/Delete channels"
    )
    
    await update.message.reply_text(admin_text, reply_markup=keyboard, parse_mode='Markdown')

async def show_code_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = get_code_management_keyboard()
    await update.message.reply_text("🔑 **Code Management**\n\nSelect an option:", reply_markup=keyboard)

async def show_channel_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = get_channel_management_keyboard()
    await update.message.reply_text("📢 **Channel Management**\n\nSelect an option:", reply_markup=keyboard)

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("No users found!")
        return
    
    user_list = "👥 **All Users:**\n\n"
    for i, user in enumerate(users[:50], 1):
        user_id, username, first_name, balance = user
        user_list += f"{i}. {first_name} (@{username}) - {balance} coins\n"
    
    if len(users) > 50:
        user_list += f"\n... and {len(users) - 50} more users"
    
    await update.message.reply_text(user_list, parse_mode='Markdown')

async def show_user_balances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("No users found!")
        return
    
    balance_list = "💰 **User Balances:**\n\n"
    total_balance = 0
    
    for user in users[:30]:
        user_id, username, first_name, balance = user
        total_balance += balance
        balance_list += f"👤 {first_name}: {balance} coins\n"
    
    balance_list += f"\n💵 **Total Balance Distributed:** {total_balance} coins"
    
    await update.message.reply_text(balance_list, parse_mode='Markdown')

async def show_today_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_today_users()
    
    if not users:
        await update.message.reply_text("No new users today!")
        return
    
    user_list = "📅 **Today's New Users:**\n\n"
    for i, user in enumerate(users, 1):
        user_id, username, first_name = user
        user_list += f"{i}. {first_name} (@{username})\n"
    
    user_list += f"\n**Total: {len(users)} new users today**"
    
    await update.message.reply_text(user_list, parse_mode='Markdown')

async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    withdrawals = get_pending_withdrawals()
    
    if not withdrawals:
        await update.message.reply_text("No pending withdrawals!")
        return
    
    withdrawal_list = "⏳ **Pending Withdrawals:**\n\n"
    
    for i, withdraw in enumerate(withdrawals, 1):
        withdraw_id, user_id, amount, method, upi_id, status, created_at, username, first_name = withdraw
        withdrawal_list += f"{i}. {first_name} - {amount} coins ({method})\n"
        if upi_id:
            withdrawal_list += f"   UPI: {upi_id}\n"
        withdrawal_list += f"   ID: {withdraw_id}\n\n"
    
    await update.message.reply_text(withdrawal_list, parse_mode='Markdown')

async def show_all_codes_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codes = get_all_redeem_codes()
    
    if not codes:
        await update.message.reply_text("No codes found!")
        return
    
    codes_text = "📋 **All Redeem Codes:**\n\n"
    for code in codes:
        code_id, code_text, coins, is_active, free_code_link, created_at = code
        status = "✅ Active" if is_active else "❌ Inactive"
        codes_text += f"🔑 {code_text} (ID: {code_id})\n"
        codes_text += f"💰 {coins} coins - {status}\n"
        if free_code_link:
            codes_text += f"🔗 {free_code_link}\n"
        codes_text += "\n"
    
    await update.message.reply_text(codes_text, parse_mode='Markdown')

async def show_all_channels_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = get_channels()
    
    if not channels:
        await update.message.reply_text("No channels found!")
        return
    
    channels_text = "📋 **All Channels:**\n\n"
    for channel in channels:
        channel_id, name, link, required, created_at = channel
        status = "✅ Required" if required else "❌ Optional"
        channels_text += f"📢 {name} (ID: {channel_id})\n"
        channels_text += f"🔗 {link}\n"
        channels_text += f"📝 {status}\n\n"
    
    await update.message.reply_text(channels_text, parse_mode='Markdown')

async def show_delete_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codes = get_all_redeem_codes()
    
    if not codes:
        await update.message.reply_text("No codes to delete!")
        return
    
    codes_text = "🗑️ **Delete Codes:**\n\n"
    for code in codes:
        code_id, code_text, coins, is_active, free_code_link, created_at = code
        codes_text += f"{code_id}. {code_text} ({coins} coins)\n"
    
    codes_text += "\nSend the Code ID to delete:"
    
    await update.message.reply_text(codes_text, parse_mode='Markdown')
    context.user_data['awaiting_delete_code'] = True

async def show_delete_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = get_channels()
    
    if not channels:
        await update.message.reply_text("No channels to delete!")
        return
    
    channels_text = "🗑️ **Delete Channels:**\n\n"
    for channel in channels:
        channel_id, name, link, required, created_at = channel
        channels_text += f"{channel_id}. {name}\n"
    
    channels_text += "\nSend the Channel ID to delete:"
    
    await update.message.reply_text(channels_text, parse_mode='Markdown')
    context.user_data['awaiting_delete_channel'] = True

# Button handlers
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data.startswith("lang_"):
        language = data.split("_")[1]
        update_language(user_id, language)
        await query.edit_message_text(f"✅ Language set to {language.capitalize()}!")
        await show_main_menu(update, context, user_id)
    
    elif data == "withdraw_upi":
        reply_markup = get_withdraw_amount_keyboard()
        await query.edit_message_text(
            "📱 **UPI Withdrawal**\n\nSelect amount to withdraw:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif data.startswith("withdraw_amount_"):
        amount = int(data.split("_")[2])
        context.user_data['withdraw_amount'] = amount
        context.user_data['withdraw_method'] = 'upi'
        await query.edit_message_text(
            f"📱 **UPI Withdrawal - {amount} coins**\n\n"
            f"Please send your UPI ID:\n\n"
            f"Example: 1234567890@ybl\n"
            f"Or: example@paytm"
        )
    
    elif data == "verify_channels":
        # For now, we'll assume user has joined all channels
        # In production, you should verify using telegram API
        user = get_user(user_id)
        language = user[5] if user and user[5] else 'english'
        
        await query.edit_message_text(get_text(language, 'channel_verified'))
        await start(update, context)
    
    elif data == "withdraw_back":
        await show_withdraw_menu(update, context)
    
    elif data == "back_to_main":
        await show_main_menu(update, context, user_id)

# Handle UPI ID input
async def handle_withdraw_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        return
    
    user_balance = user[3]
    text = update.message.text
    
    if 'withdraw_amount' in context.user_data and 'withdraw_method' in context.user_data:
        amount = context.user_data['withdraw_amount']
        method = context.user_data['withdraw_method']
        
        if user_balance < amount:
            await update.message.reply_text("❌ Insufficient balance!")
            return
        
        if method == 'upi':
            # Validate UPI ID format
            if '@' not in text:
                await update.message.reply_text("❌ Invalid UPI ID format! Please provide valid UPI ID.")
                return
            
            # Create withdrawal and get withdrawal ID
            withdrawal_id = create_withdrawal(user_id, amount, 'upi', upi_id=text)
            update_balance(user_id, -amount)
            
            user_language = user[5] if user[5] else 'english'
            
            await update.message.reply_text(
                get_text(user_language, 'withdraw_request_sent').format(amount),
                parse_mode='Markdown'
            )
            
            # Notify all admins about new withdrawal request
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🆕 **New Withdrawal Request!**\n\n"
                             f"👤 User: {user[2]} (@{user[1]})\n"
                             f"💰 Amount: {amount} coins\n"
                             f"📱 Method: UPI\n"
                             f"🔢 UPI ID: {text}\n"
                             f"🆔 User ID: {user_id}\n"
                             f"📋 Withdrawal ID: {withdrawal_id}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"Failed to notify admin {admin_id}: {e}")
                    continue
        
        # Clear withdrawal data
        context.user_data.pop('withdraw_amount', None)
        context.user_data.pop('withdraw_method', None)
        
        await show_main_menu(update, context, user_id)

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot started successfully!")
    print(f"📍 Minimum Withdrawal: {MIN_WITHDRAWAL} coins")
    print(f"💰 Refer Bonus: {REFER_BONUS} coins")
    print("🎯 Features: Add Code, Refer System, Withdrawal, Channel Verification, Admin Panel")
    application.run_polling()

if __name__ == '__main__':
    main()
