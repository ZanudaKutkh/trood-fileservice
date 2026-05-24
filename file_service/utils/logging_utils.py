import logging
from .middleware import get_current_request_id

class RequestIDFilter(logging.Filter):
    """
    Logging filter that adds request_id to the log record.
    """
    def filter(self, record):
        record.request_id = get_current_request_id() or "no-request-id"
        return True
