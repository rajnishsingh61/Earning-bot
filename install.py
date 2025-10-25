#!/usr/bin/env python3
"""
Earning Bot - Automatic Installation Script
"""

import os
import sys
import subprocess
import platform

def run_command(command):
    """Run system command and return success status"""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {command}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running: {command}")
        print(f"Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Python 3.7 or higher required!")
        print(f"Current version: {platform.python_version()}")
        return False
    print(f"✅ Python {platform.python_version()} detected")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing dependencies...")
    
    packages = [
        "python-telegram-bot==20.7",
        "apscheduler==3.10.1"
    ]
    
    for package in packages:
        if not run_command(f"pip install {package}"):
            return False
    
    return True

def create_env_file():
    """Create .env file with template"""
    env_content = """# Earning Bot Configuration
# Get BOT_TOKEN from @BotFather on Telegram
BOT_TOKEN=your_bot_token_here

# Your Telegram User ID (get from @userinfobot)
ADMIN_IDS=7013309955

# Bot Settings (Optional)
REFER_BONUS=15
MIN_WITHDRAWAL=200
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    print("✅ Created .env template file")

def setup_database():
    """Initialize database"""
    try:
        from bot import init_db
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def main():
    print("🤖 Earning Bot - Installation Script")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Dependency installation failed!")
        sys.exit(1)
    
    # Create environment file
    create_env_file()
    
    # Setup database
    if not setup_database():
        print("\n❌ Database setup failed!")
        sys.exit(1)
    
    print("\n🎉 Installation completed successfully!")
    print("\n📝 Next steps:")
    print("1. Edit .env file and add your BOT_TOKEN")
    print("2. Run: python bot.py")
    print("3. Or run: python run.py")
    print("\n💡 Get BOT_TOKEN from @BotFather on Telegram")
    print("💡 Get your USER_ID from @userinfobot")

if __name__ == "__main__":
    main()