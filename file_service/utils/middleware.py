import uuid
import threading

# Thread-local storage for request ID
_thread_locals = threading.local()

def get_current_request_id():
    return getattr(_thread_locals, 'request_id', None)

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
