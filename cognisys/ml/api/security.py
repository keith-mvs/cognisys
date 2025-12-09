"""
Security Middleware for CogniSys ML API
Implements rate limiting and CORS controls
"""

from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter for API endpoints.
    Tracks requests per IP address with configurable limits.
    """

    def __init__(self, requests_per_minute=60, requests_per_hour=1000):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests allowed per minute per IP
            requests_per_hour: Max requests allowed per hour per IP
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Track requests: {ip: [(timestamp, count), ...]}
        self.minute_requests = defaultdict(list)
        self.hour_requests = defaultdict(list)

        logger.info(f"Rate limiter initialized: {requests_per_minute}/min, {requests_per_hour}/hour")

    def _cleanup_old_requests(self, request_dict, window_seconds):
        """Remove requests older than the time window"""
        cutoff = datetime.now() - timedelta(seconds=window_seconds)

        for ip in list(request_dict.keys()):
            request_dict[ip] = [
                (ts, count) for ts, count in request_dict[ip]
                if ts > cutoff
            ]
            if not request_dict[ip]:
                del request_dict[ip]

    def is_rate_limited(self, ip_address):
        """
        Check if IP address has exceeded rate limits.

        Args:
            ip_address: Client IP address

        Returns:
            (is_limited: bool, retry_after: int or None)
        """
        now = datetime.now()

        # Clean up old requests
        self._cleanup_old_requests(self.minute_requests, 60)
        self._cleanup_old_requests(self.hour_requests, 3600)

        # Count requests in last minute
        minute_count = sum(
            count for ts, count in self.minute_requests[ip_address]
        )

        # Count requests in last hour
        hour_count = sum(
            count for ts, count in self.hour_requests[ip_address]
        )

        # Check minute limit
        if minute_count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute): {ip_address} ({minute_count} requests)")
            return True, 60  # Retry after 60 seconds

        # Check hour limit
        if hour_count >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour): {ip_address} ({hour_count} requests)")
            return True, 3600  # Retry after 1 hour

        return False, None

    def record_request(self, ip_address):
        """Record a request from an IP address"""
        now = datetime.now()
        self.minute_requests[ip_address].append((now, 1))
        self.hour_requests[ip_address].append((now, 1))


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter():
    """Get or create the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=60,  # 60 requests per minute
            requests_per_hour=1000   # 1000 requests per hour
        )
    return _rate_limiter


def rate_limit(f):
    """
    Decorator to apply rate limiting to Flask routes.

    Usage:
        @app.route('/endpoint')
        @rate_limit
        def my_endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        limiter = get_rate_limiter()
        ip = request.remote_addr

        is_limited, retry_after = limiter.is_rate_limited(ip)

        if is_limited:
            response = jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Too many requests. Please try again later.',
                'retry_after': retry_after
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(retry_after)
            return response

        # Record this request
        limiter.record_request(ip)

        return f(*args, **kwargs)

    return decorated_function


def configure_cors(app, allowed_origins=None):
    """
    Configure CORS (Cross-Origin Resource Sharing) for the Flask app.

    Args:
        app: Flask application instance
        allowed_origins: List of allowed origin URLs (default: localhost only)
    """
    if allowed_origins is None:
        # Default: Only allow localhost
        allowed_origins = [
            'http://localhost:*',
            'http://127.0.0.1:*',
            'http://[::1]:*'
        ]

    @app.after_request
    def add_cors_headers(response):
        """Add CORS headers to all responses"""
        origin = request.headers.get('Origin')

        # Check if origin is allowed
        if origin:
            # For localhost, allow any port
            if any(
                origin.startswith('http://localhost:') or
                origin.startswith('http://127.0.0.1:') or
                origin.startswith('http://[::1]:')
                for _ in allowed_origins
            ):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                response.headers['Access-Control-Max-Age'] = '3600'
        else:
            # No origin header - local request
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:*'

        return response

    logger.info(f"CORS configured for origins: {allowed_origins}")
    return app


def apply_security_headers(app):
    """
    Apply security headers to all responses.

    Implements OWASP recommended security headers.
    """
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Strict Transport Security (HTTPS only - commented for local dev)
        # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy
        response.headers['Content-Security-Policy'] = "default-src 'self'"

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (formerly Feature Policy)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response

    logger.info("Security headers configured")
    return app
