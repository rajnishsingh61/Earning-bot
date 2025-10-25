#!/usr/bin/env python3
"""
Earning Bot - Easy Run Script
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Check if required environment variables are set"""
    load_dotenv()  # Load .env file
    
    bot_token = os.getenv('BOT_TOKEN')
    admin_ids = os.getenv('ADMIN_IDS')
    
    if not bot_token or bot_token == 'your_bot_token_here':
        print("❌ BOT_TOKEN not set!")
        print("📝 Please edit .env file and add your bot token")
        print("💡 Get token from @BotFather on Telegram")
        return False
    
    if not admin_ids or admin_ids == '7013309955':
        print("⚠️  Warning: Using default ADMIN_IDS")
        print("💡 Edit .env file to set your user ID")
    
    return True

def main():
    print("🤖 Starting Earning Bot...")
    print("=" * 30)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Import and run bot
    try:
        from bot import main as bot_main
        print("✅ All checks passed!")
        print("🚀 Starting bot...")
        print("💡 Press Ctrl+C to stop the bot")
        bot_main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()