import logging
from logging.handlers import RotatingFileHandler
import os

class LoggerManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        log_file: str = "PYMWA.log",
        log_level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        date_format: str = '%Y-%m-%d %H:%M:%S'
    ):
        if hasattr(self, 'logger'):
            return
        
        self.log_file = log_file
        self.log_level = log_level
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.log_level)
        
        self._setup_handlers(log_format, date_format, max_bytes, backup_count)
    
    def _setup_handlers(self, log_format, date_format, max_bytes, backup_count):
        if self.logger.handlers:
            return
        
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            filename=self.log_file,
            encoding="utf-8",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(self.log_level)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        
        formatter = logging.Formatter(
            fmt=log_format,
            datefmt=date_format
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def get_logger(self):
        return self.logger

logger = LoggerManager().get_logger()