import logging
from .middleware import get_current_request_id

logger = logging.getLogger('file_service')

class RequestIDFilter(logging.Filter):
    """
    Logging filter that adds request_id to the log record.
    """
    def filter(self, record):
        record.request_id = get_current_request_id() or "no-request-id"
        return True

def log_debug(message, extra=None):
    """
    Tiny utility to log debug messages to the file_service logger.
    """
    logger.debug(message, extra=extra)
