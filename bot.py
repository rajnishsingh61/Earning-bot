import logging
import sqlite3
import asyncio
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8234462578:AAE1cjdopd-1O6HZLT-DQhpstBEb-4Ixs34')
ADMIN_IDS = [int(id.strip()) for id in os.environ.get('ADMIN_IDS', '7013309955').split(',')]
REFER_BONUS = 15
MIN_WITHDRAWAL = 200
WITHDRAWAL_OPTIONS = [200, 500, 1000, 2000]

# Database setup
def init_db():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code_id INTEGER,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, balance FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def create_user(user_id, username, first_name, referrer_id=None):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)', 
                  (user_id, username, first_name, referrer_id))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_redeem_code(code, coins, free_code_link=""):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
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
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes WHERE code = ? AND is_active = 1', (code,))
    redeem_code = cursor.fetchone()
    conn.close()
    return redeem_code

def get_redeem_code_by_text(code_text):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes WHERE code = ?', (code_text,))
    redeem_code = cursor.fetchone()
    conn.close()
    return redeem_code

def get_all_redeem_codes():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes ORDER BY created_at DESC')
    codes = cursor.fetchall()
    conn.close()
    return codes

def get_active_redeem_codes():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM redeem_codes WHERE is_active = 1 ORDER BY created_at DESC')
    codes = cursor.fetchall()
    conn.close()
    return codes

def redeem_code(user_id, code):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM user_redemptions 
        WHERE user_id = ? AND code_id IN (SELECT code_id FROM redeem_codes WHERE code = ?)
    ''', (user_id, code))
    if cursor.fetchone():
        conn.close()
        return False, "already_used"
    
    cursor.execute('SELECT * FROM redeem_codes WHERE code = ? AND is_active = 1', (code,))
    redeem_code_data = cursor.fetchone()
    
    if not redeem_code_data:
        conn.close()
        return False, "not_found"
    
    code_id, code_text, coins, is_active, free_code_link, created_at = redeem_code_data
    
    cursor.execute('INSERT INTO user_redemptions (user_id, code_id) VALUES (?, ?)', (user_id, code_id))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (coins, user_id))
    
    conn.commit()
    conn.close()
    return True, coins

def create_withdrawal(user_id, amount, method, upi_id=None):
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO withdrawals (user_id, amount, method, upi_id) VALUES (?, ?, ?, ?)', 
                  (user_id, amount, method, upi_id))
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return withdrawal_id

def get_main_keyboard(user_id):
    if user_id in ADMIN_IDS:
        keyboard = [
            ["🔑 Add Code", "💰 Balance"],
            ["📥 GET FREE CODE", "👥 Refer & Earn"],
            ["💸 Withdraw", "📊 Admin Panel"]
        ]
    else:
        keyboard = [
            ["🔑 Add Code", "💰 Balance"],
            ["📥 GET FREE CODE", "👥 Refer & Earn"],
            ["💸 Withdraw"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        ["📢 Broadcast", "👥 All Users"],
        ["🔑 Add Redeem Code", "📋 All Codes"],
        ["🔙 Main Menu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                create_user(user_id, username, first_name, referrer_id)
                update_balance(referrer_id, REFER_BONUS)
        except:
            create_user(user_id, username, first_name)
    else:
        create_user(user_id, username, first_name)
    
    await show_main_menu(update, context, user_id)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = get_user(user_id)
    balance = user_data[3] if user_data else 0
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    welcome_text = (
        f"🤖 **Welcome to Earn Bot!**\n\n"
        f"💳 **Balance:** {balance} coins\n"
        f"📱 **Your Referral Link:**\n`{referral_link}`\n\n"
        f"Add redeem codes to earn coins! 💰"
    )
    
    keyboard = get_main_keyboard(user_id)
    
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🔑 Add Code":
        await update.message.reply_text("🔑 **Add Code**\n\nPlease enter your redeem code:")
        context.user_data['awaiting_redeem_code'] = True
        
    elif text == "💰 Balance":
        user = get_user(user_id)
        if user:
            balance = user[3]
            await update.message.reply_text(f"💰 **Balance:** {balance} coins")
        
    elif text == "📥 GET FREE CODE":
        # Show all active codes with inline keyboard buttons
        codes = get_active_redeem_codes()
        if codes:
            # Create inline keyboard with all free code links
            keyboard = []
            for code in codes:
                code_id, code_text, coins, is_active, free_code_link, created_at = code
                if free_code_link:
                    keyboard.append([InlineKeyboardButton("📥 GET FREE CODE", url=free_code_link)])
            
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "📥 **Click below to get free codes:**",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ No free codes available at the moment!")
        else:
            await update.message.reply_text("❌ No free codes available at the moment!")
        
    elif text == "👥 Refer & Earn":
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        await update.message.reply_text(
            f"👥 **Refer & Earn**\n\n"
            f"📱 **Your Referral Link:**\n`{referral_link}`\n\n"
            f"💡 Share this link and earn **{REFER_BONUS} coins** for each referral!",
            parse_mode='Markdown'
        )
        
    elif text == "💸 Withdraw":
        user = get_user(user_id)
        if not user:
            return
            
        user_balance = user[3]
        if user_balance >= MIN_WITHDRAWAL:
            keyboard = []
            for amount in WITHDRAWAL_OPTIONS:
                if user_balance >= amount:
                    keyboard.append([InlineKeyboardButton(f"💳 {amount} coins", callback_data=f"withdraw_{amount}")])
            
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"💸 **Withdrawal**\n\nCurrent Balance: **{user_balance} coins**\nSelect amount:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ Minimum withdrawal is {MIN_WITHDRAWAL} coins!")
        else:
            await update.message.reply_text(f"❌ Minimum withdrawal is {MIN_WITHDRAWAL} coins!\nYour balance: {user_balance} coins")
    
    elif text == "📊 Admin Panel":
        if user_id in ADMIN_IDS:
            reply_markup = get_admin_keyboard()
            await update.message.reply_text("🛠️ **Admin Panel**\n\nSelect an option:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("🚫 Access Denied!")
    
    elif text == "🔑 Add Redeem Code":
        if user_id in ADMIN_IDS:
            await update.message.reply_text(
                "🔑 **Add New Redeem Code**\n\n"
                "Send in this format:\n"
                "CODE\n"
                "COINS\n"
                "FREE_CODE_LINK\n\n"
                "Example:\n"
                "FREE100\n"
                "50\n"
                "https://t.me/example"
            )
            context.user_data['awaiting_code'] = True
    
    elif text == "📢 Broadcast":
        if user_id in ADMIN_IDS:
            await update.message.reply_text("📢 **Broadcast Message**\n\nSend the message to broadcast:")
            context.user_data['awaiting_broadcast'] = True
    
    elif text == "👥 All Users":
        if user_id in ADMIN_IDS:
            users = get_all_users()
            if users:
                user_list = "👥 **All Users:**\n\n"
                for i, user in enumerate(users[:20], 1):
                    user_id, username, first_name, balance = user
                    user_list += f"{i}. {first_name} (@{username}) - {balance} coins\n"
                await update.message.reply_text(user_list, parse_mode='Markdown')
            else:
                await update.message.reply_text("No users found!")
    
    elif text == "📋 All Codes":
        if user_id in ADMIN_IDS:
            codes = get_all_redeem_codes()
            if codes:
                codes_text = "📋 **All Codes (Admin View):**\n\n"
                for code in codes:
                    code_id, code_text, coins, is_active, free_code_link, created_at = code
                    status = "✅ Active" if is_active else "❌ Inactive"
                    codes_text += f"🔑 {code_text} - {coins} coins\n"
                    codes_text += f"🔗 {free_code_link}\n"
                    codes_text += f"📊 {status}\n\n"
                await update.message.reply_text(codes_text, parse_mode='Markdown')
            else:
                await update.message.reply_text("No codes found!")
    
    elif text == "🔙 Main Menu":
        await show_main_menu(update, context, user_id)
    
    elif 'awaiting_redeem_code' in context.user_data:
        code = update.message.text.strip().upper()
        success, result = redeem_code(user_id, code)
        
        if success:
            coins = result
            await update.message.reply_text(
                f"🎉 **Code Added Successfully!**\n\n💰 You earned **{coins} coins**!",
                parse_mode='Markdown'
            )
        else:
            # Get the first active code's link for the GET FREE CODE button
            codes = get_active_redeem_codes()
            if codes and codes[0][4]:  # Check if free_code_link exists
                free_code_link = codes[0][4]
                # Create inline keyboard with GET FREE CODE button
                keyboard = [[InlineKeyboardButton("📥 GET FREE CODE", url=free_code_link)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if result == "already_used":
                    await update.message.reply_text(
                        "❌ You have already used this code!",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(
                        "❌ Invalid code!",
                        reply_markup=reply_markup
                    )
            else:
                if result == "already_used":
                    await update.message.reply_text("❌ You have already used this code!")
                else:
                    await update.message.reply_text("❌ Invalid code!")
        
        context.user_data.pop('awaiting_redeem_code', None)
    
    elif 'awaiting_code' in context.user_data:
        text = update.message.text
        try:
            lines = text.split('\n')
            if len(lines) >= 3:
                code = lines[0].strip().upper()
                coins = int(lines[1].strip())
                free_code_link = lines[2].strip()
                
                code_id = add_redeem_code(code, coins, free_code_link)
                if code_id:
                    await update.message.reply_text(
                        f"✅ **Code Added Successfully!**\n\n"
                        f"🔑 Code: {code}\n"
                        f"💰 Coins: {coins}\n"
                        f"🔗 Link: {free_code_link}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("❌ Code already exists!")
            else:
                await update.message.reply_text("❌ Invalid format! Send:\nCODE\nCOINS\nLINK")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data.pop('awaiting_code', None)
    
    elif 'awaiting_broadcast' in context.user_data:
        message = update.message.text
        users = get_all_users()
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=message)
                success += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        
        await update.message.reply_text(
            f"📢 **Broadcast Complete!**\n\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}"
        )
        
        context.user_data.pop('awaiting_broadcast', None)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data.startswith("withdraw_"):
        amount = int(data.split("_")[1])
        context.user_data['withdraw_amount'] = amount
        await query.edit_message_text(
            f"💸 **Withdraw {amount} coins**\n\n"
            f"Please send your UPI ID:\n\n"
            f"Example: 1234567890@ybl\n"
            f"Or: example@paytm"
        )

async def handle_withdraw_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        return
    
    text = update.message.text
    
    if 'withdraw_amount' in context.user_data:
        amount = context.user_data['withdraw_amount']
        user_balance = user[3]
        
        if user_balance < amount:
            await update.message.reply_text("❌ Insufficient balance!")
            return
        
        if '@' not in text:
            await update.message.reply_text("❌ Invalid UPI ID! Example: 1234567890@ybl")
            return
        
        # Create withdrawal
        withdrawal_id = create_withdrawal(user_id, amount, 'upi', upi_id=text)
        update_balance(user_id, -amount)
        
        await update.message.reply_text(
            f"✅ **Withdrawal Request Sent!**\n\n"
            f"💰 Amount: {amount} coins\n"
            f"📱 UPI ID: {text}\n\n"
            f"Your request has been sent to admin for approval."
        )
        
        # Notify admin
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🆕 **New Withdrawal Request!**\n\n"
                         f"👤 User: {user[2]} (@{user[1]})\n"
                         f"💰 Amount: {amount} coins\n"
                         f"📱 UPI: {text}\n"
                         f"🆔 User ID: {user_id}",
                    parse_mode='Markdown'
                )
            except:
                continue
        
        context.user_data.pop('withdraw_amount', None)

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot started successfully!")
    print(f"📍 Minimum Withdrawal: {MIN_WITHDRAWAL} coins")
    print(f"💰 Refer Bonus: {REFER_BONUS} coins")
    print("🚀 Bot is running...")
    
    application.run_polling()

if __name__ == '__main__':
    main()