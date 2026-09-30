"""Production HTTP transport for controlled staging, retaining the shared API.

Gunicorn parses HTTP; this adapter reuses the existing route dispatcher without
running BaseHTTPRequestHandler's socket parser or its development server.
"""
import io
import json
import logging
import os
import secrets
import time
from email.message import Message
from http import HTTPStatus
from urllib.parse import urlsplit
from database import request_lock
from settings import Settings
from server import Service, make_handler

log = logging.getLogger('ridenova')


def create_app(settings=None):
    settings = settings or Settings.load()
    if settings.environment == 'staging':
        from migrate import check
        check(settings.database)
    service = Service(settings.database)
    service.settings = settings
    Handler = make_handler(service)

    class Dispatch(Handler):
        def __init__(self, environ):
            self.command = environ['REQUEST_METHOD']
            self.path = environ.get('PATH_INFO', '/')
            if environ.get('QUERY_STRING'):
                self.path += '?' + environ['QUERY_STRING']
            self.headers = Message()
            for key, value in environ.items():
                if key.startswith('HTTP_'):
                    self.headers[key[5:].replace('_', '-')] = str(value)
            for key in ('CONTENT_LENGTH', 'CONTENT_TYPE'):
                if environ.get(key): self.headers[key.replace('_', '-')] = environ[key]
            self.rfile = environ['wsgi.input']
            self.wfile = io.BytesIO()
            self.connection = self
            self.status = 500
            self.response_headers = []
        def settimeout(self, _): pass
        def send_response(self, status, message=None): self.status = status
        def send_header(self, key, value): self.response_headers.append((key, value))
        def end_headers(self): pass

    def app(environ, start_response):
        started = time.monotonic()
        request_id = secrets.token_hex(12)
        path = environ.get('PATH_INFO', '/').rstrip('/')
        method = environ.get('REQUEST_METHOD', '')
        status, payload, headers = 200, None, []
        timings = {}
        try:
            if method not in ('GET', 'POST', 'PATCH'):
                status, payload = 405, {'code': 'METHOD_NOT_ALLOWED', 'message': 'Unsupported method'}
            elif path in ('/health', '/ready') and method != 'GET':
                status, payload = 405, {'code': 'METHOD_NOT_ALLOWED', 'message': 'Use GET'}
            elif settings.environment == 'staging' and path not in ('/health', '/ready') and (
                environ.get('HTTP_HOST', '').lower() != urlsplit(settings.origin).netloc.lower() or
                environ.get('HTTP_ORIGIN', settings.origin) != settings.origin):
                status, payload = 403, {'code': 'ORIGIN_REJECTED', 'message': 'Use the configured staging origin'}
            elif settings.environment == 'staging' and path not in ('/health', '/ready') and environ.get('wsgi.url_scheme') != 'https':
                status, payload = 400, {'code': 'HTTPS_REQUIRED', 'message': 'HTTPS is required'}
            elif path == '/health':
                payload = {'status': 'ok', 'build': 42, 'version': '42.0', 'environment': settings.environment,
                           'payments': 'stripe-test-optional', 'publicLaunch': False,
                           'revision': os.environ.get('RENDER_GIT_COMMIT', 'local')}
            elif path == '/ready':
                from operations import ready
                healthy = settings.environment == 'development' or ready(settings.database)
                status, payload = (200 if healthy else 503), {'status': 'ready' if healthy else 'not-ready'}
            else:
                allowed = True
                if settings.environment == 'staging':
                    from operations import allow_requests
                    # No untrusted X-Forwarded-For. Bound all unauthenticated traffic
                    # globally, then rate-limit authenticated traffic by token hash.
                    subject = environ.get('HTTP_AUTHORIZATION', '') or 'anonymous'
                    if len(subject) > 300:
                        allowed = False
                    else:
                        rules = [('api:global', 600, 60), ('api:' + subject, 300, 60)]
                        if path in ('/v1/staff/login', '/v2/fleet/auth/login', '/v1/auth/request-otp', '/v1/auth/verify-otp', '/v2/fleet/auth/register'):
                            rules.append(('auth:' + path, 30, 60))
                        rate_started = time.monotonic()
                        allowed = allow_requests(settings.database, settings.rate_secret, rules)
                        timings['rateMs'] = round((time.monotonic()-rate_started)*1000)
                if not allowed:
                    status, payload = 429, {'code': 'RATE_LIMITED', 'message': 'Too many requests; wait and try again'}
                    headers.append(('Retry-After', '60'))
                else:
                    lock_started = time.monotonic()
                    with request_lock(settings.database):
                        timings['lockWaitMs'] = round((time.monotonic()-lock_started)*1000)
                        response = Dispatch(environ)
                        response.dispatch()
                    timings['handlerMs'] = round((time.monotonic()-lock_started)*1000) - timings['lockWaitMs']
                    status = response.status
                    headers.extend((k, v) for k, v in response.response_headers if k.lower() != 'x-request-id')
                    data = response.wfile.getvalue()
        except Exception as exc:
            # Exception class only: database exceptions can contain user data/DSNs.
            log.error(json.dumps({'event': 'request_failed', 'requestId': request_id, 'exception': type(exc).__name__}))
            status, payload = 503, {'code': 'SERVICE_UNAVAILABLE', 'message': 'Temporarily unavailable; retry the same operation safely'}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers.extend([('Content-Type', 'application/json'), ('Content-Length', str(len(data))), ('Cache-Control', 'no-store')])
        headers.extend([('X-Request-ID', request_id), ('X-Frame-Options', 'DENY'),
                        ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')])
        if settings.environment == 'staging':
            headers.append(('Strict-Transport-Security', 'max-age=31536000'))
        # No query strings, bodies, phones, coordinates, tokens or IP addresses.
        log.info(json.dumps({'event': 'request', 'requestId': request_id, 'method': method,
                             'status': status, 'durationMs': round((time.monotonic()-started)*1000), **timings}))
        start_response(f'{status} {HTTPStatus(status).phrase}', headers)
        return [data]
    return app
