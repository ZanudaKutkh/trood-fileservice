import uuid
import threading
import logging

# Thread-local storage for request ID
_thread_locals = threading.local()

def get_current_request_id():
    return getattr(_thread_locals, 'request_id', None)

class GatekeeperLoggingMiddleware:
    """
    Middleware that stands at the very gates of Django.
    Logs every request before any auth or validation happens.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('file_service.gatekeeper')

    def __call__(self, request):
        # Log incoming request details immediately
        # We use INFO level to ensure it shows up in most configurations
        self.logger.info(
            f"GATEKEEPER: {request.method} {request.path}",
            extra={
                "ip": request.META.get('REMOTE_ADDR'),
                "user_agent": request.META.get('HTTP_USER_AGENT'),
                "content_length": request.META.get('CONTENT_LENGTH'),
                "content_type": request.META.get('CONTENT_TYPE'),
                "request_id": request.META.get('HTTP_X_REQUEST_ID', 'no-id-yet')
            }
        )
        
        return self.get_response(request)

class RequestIDMiddleware:
    """
    Middleware to handle X-Request-ID.
    It takes the ID from the incoming request headers or generates a new one,
    stores it in thread-local storage, and adds it to the response headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Extract from header or generate
        request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        _thread_locals.request_id = request_id
        
        # Attach to request object for convenience
        request.request_id = request_id
        
        response = self.get_response(request)
        
        # 2. Add to response header
        response['X-Request-ID'] = request_id
        
        # Cleanup to avoid memory leaks or ID leakage between requests in the same thread
        _thread_locals.request_id = None
        
        return response
