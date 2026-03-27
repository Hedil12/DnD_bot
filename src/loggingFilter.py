import logging
import os

class RedactTokenFilter(logging.Filter):
    def __init__(self, token):
        super().__init__()
        self.token = token

    def filter(self, record):
        if self.token and isinstance(record.msg, str):
            # Replace the actual token with asterisks in the logs
            record.msg = record.msg.replace(self.token, "[REDACTED_TELEGRAM_TOKEN]")
        return True