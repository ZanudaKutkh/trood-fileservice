import uuid
import threading
import logging
import time

# Thread-local storage for request ID
_thread_locals = threading.local()

def get_current_request_id():
    return getattr(_thread_locals, 'request_id', None)

class GatekeeperLoggingMiddleware:
    """
    Middleware that stands at the very gates of Django.
    Logs every request before any auth or validation happens.
    Now also logs the response and processing time.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('file_service.gatekeeper')

    def __call__(self, request):
        start_time = time.time()
        
        # Log incoming request details immediately
        self.logger.info(
            f"GATEKEEPER IN: {request.method} {request.path}",
            extra={
                "ip": request.META.get('REMOTE_ADDR'),
                "user_agent": request.META.get('HTTP_USER_AGENT'),
                "content_length": request.META.get('CONTENT_LENGTH'),
                "content_type": request.META.get('CONTENT_TYPE'),
                "request_id": request.META.get('HTTP_X_REQUEST_ID', 'no-id-yet')
            }
        )
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        
        # Log outgoing response details
        self.logger.info(
            f"GATEKEEPER OUT: {request.method} {request.path} -> {response.status_code} ({duration:.3f}s)",
            extra={
                "status_code": response.status_code,
                "duration": duration,
                "request_id": getattr(request, 'request_id', 'no-id-yet')
            }
        )
        
        return response

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
