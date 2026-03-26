# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'trading_agent.db')
    
    # Risk Management
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '100000'))
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '10000'))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))
    STOP_LOSS_DEFAULT = float(os.getenv('STOP_LOSS_DEFAULT', '0.02'))
    TAKE_PROFIT_DEFAULT = float(os.getenv('TAKE_PROFIT_DEFAULT', '0.04'))
    
    # AI Model
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama2')
    
    # Webhook
    DEFAULT_WEBHOOK_URL = os.getenv('DEFAULT_WEBHOOK_URL', '')