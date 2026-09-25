"""Fail-closed deployment settings; values are never logged."""
import json
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    environment: str
    database: str
    origin: str = ''
    tester_codes: dict = field(default_factory=dict, repr=False)
    driver_phones: tuple = ()
    rate_secret: str = field(default='', repr=False)

    @classmethod
    def load(cls, env=None):
        env = os.environ if env is None else env
        name = env.get('RIDENOVA_ENVIRONMENT', 'development')
        if name not in ('development', 'staging', 'production'):
            raise ValueError('Unknown RIDENOVA_ENVIRONMENT')
        if name == 'production':
            raise ValueError('Public production is not enabled in Build 41; payment, phone verification and launch gates remain')
        database = env.get('DATABASE_URL', '')
        if name == 'development':
            return cls(name, database or env.get('RIDENOVA_DATABASE', 'ridenova-dev.sqlite3'))
        if not database.startswith(('postgres://', 'postgresql://')):
            raise ValueError('Staging requires PostgreSQL DATABASE_URL')
        origin = env.get('RIDENOVA_PUBLIC_ORIGIN', '').rstrip('/')
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError('RIDENOVA_PUBLIC_ORIGIN must be a plain HTTPS origin')
        codes = json.loads(env.get('RIDENOVA_STAGING_TESTERS', '{}'))
        if not isinstance(codes, dict) or not codes or any(
            not re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}', phone) or
            not isinstance(code, str) or not re.fullmatch(r'\d{6}', code) or code == '246810'
            for phone, code in codes.items()):
            raise ValueError('Configure invited passenger phones with individually assigned six-digit staging codes')
        phones = tuple(p.strip() for p in env.get('RIDENOVA_STAGING_DRIVER_PHONES', '').split(',') if p.strip())
        if not phones or any(not re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}', p) for p in phones):
            raise ValueError('Configure invited driver phone numbers')
        secret = env.get('RIDENOVA_RATE_SECRET', '')
        if len(secret) < 32:
            raise ValueError('RIDENOVA_RATE_SECRET must be at least 32 characters')
        if env.get('RIDENOVA_DEV_ADMIN_TOKEN') or env.get('RIDENOVA_DEV_DRIVER_TOKEN'):
            raise ValueError('Development shared tokens are forbidden in staging')
        return cls(name, database, origin, codes, phones, secret)
