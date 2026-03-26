# utils/logger.py - Enhanced logging
import logging
import logging.handlers
import os

def setup_logging(log_level: str = "INFO", log_file: str = "trading_agent.log"):
    """Setup logging with rotation"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    return logger
    