"""Render terminates TLS. Never expose this HTTP listener directly to the internet."""
import os
bind = '0.0.0.0:' + os.environ.get('PORT', '10000')
workers = 2
worker_class = 'sync'
timeout = 45
graceful_timeout = 30
max_requests = 2000
max_requests_jitter = 200
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
accesslog = None  # app logs omit personal information and secrets
errorlog = '-'
loglevel = 'info'
# Render's dynamic edge proxies are the only public path to this listener.
# When moving to AWS, set this to the actual load-balancer proxy ranges.
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1')
secure_scheme_headers = {'X-FORWARDED-PROTO': 'https'}
logconfig_dict = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'plain': {'format': '%(message)s'}},
    'handlers': {'stdout': {'class': 'logging.StreamHandler', 'stream': 'ext://sys.stdout', 'formatter': 'plain'}},
    'root': {'handlers': ['stdout'], 'level': 'INFO'},
    'loggers': {
        'ridenova': {'handlers': ['stdout'], 'level': 'INFO', 'propagate': False},
        'gunicorn.error': {'handlers': ['stdout'], 'level': 'INFO', 'propagate': False},
        'gunicorn.access': {'handlers': [], 'level': 'INFO', 'propagate': False},
    },
}
