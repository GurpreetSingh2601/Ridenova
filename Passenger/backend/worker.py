"""Idempotent scheduler. Uses the same database request gate as the API."""
import json
import logging
import signal
import threading
from database import request_lock
from migrate import check
from operations import heartbeat
from server import Service
from settings import Settings


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    settings = Settings.load()
    if settings.environment != 'staging':
        raise SystemExit('Use server.py for the development scheduler')
    check(settings.database)
    service = Service(settings.database)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            with request_lock(settings.database):
                service.activate_due()
                heartbeat(settings.database)
            logging.info(json.dumps({'event': 'scheduler_tick', 'status': 'ok'}))
        except Exception as exc:
            logging.error(json.dumps({'event': 'scheduler_tick', 'status': 'failed', 'exception': type(exc).__name__}))
        stop.wait(5)


if __name__ == '__main__': main()
