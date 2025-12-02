"""
Security middleware for request size limiting and other security features.
"""
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware:
    """
    Middleware to limit the size of incoming requests to prevent DoS attacks.
    Rejects requests larger than the configured maximum size.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # 10MB default limit (configurable via settings)
        self.max_size = 10 * 1024 * 1024  # 10MB in bytes
        
    def __call__(self, request):
        # Check request size for write operations
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_length = request.META.get('CONTENT_LENGTH')
            
            if content_length:
                try:
                    content_length = int(content_length)
                    if content_length > self.max_size:
                        logger.warning(
                            f"Request size limit exceeded: {content_length} bytes from IP {request.META.get('REMOTE_ADDR')}"
                        )
                        return JsonResponse({
                            'error': 'Request too large',
                            'max_size_mb': self.max_size / (1024 * 1024),
                            'your_size_mb': round(content_length / (1024 * 1024), 2)
                        }, status=413)  # 413 Payload Too Large
                except (ValueError, TypeError):
                    # Invalid content-length header, let it pass
                    pass
        
        response = self.get_response(request)
        return response
