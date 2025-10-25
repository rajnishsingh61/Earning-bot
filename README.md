# 🤖 Earning Bot - Telegram Coin Earning Bot

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

A feature-rich Telegram bot for earning coins through redeem codes, referrals, and withdrawals.

## 🚀 Features

- 💰 **Coin System** - Earn coins through redeem codes
- 👥 **Referral Program** - Earn 15 coins for each referral
- 💸 **Withdrawal System** - Withdraw coins via UPI (200 coins minimum)
- 🔑 **Redeem Codes** - Add and manage redeem codes
- 📢 **Channel Verification** - Force users to join channels
- 🌐 **Multi-language** - English & Hindi support
- 🛠️ **Admin Panel** - Complete bot management

## 🚀 Render Deployment

1. **Click the "Deploy to Render" button above**
2. **Set environment variables:**
   - `BOT_TOKEN`: Your Telegram bot token from @BotFather
   - `ADMIN_IDS`: Your Telegram user ID (get from @userinfobot)
3. **Deploy** - Automatic deployment starts

## 🛠️ Local Development

```bash
# Clone repository
git clone https://github.com/rajnishsingh61/Earning-bot.git
cd Earning-bot

# Install dependencies
pip install -r requirements.txt

# Run bot
python bot.py