"""Stripe test-mode REST boundary. Never accepts/stores PAN, CVC or live keys."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    pass


class StripeTest:
    def __init__(self, secret=None):
        self.secret = secret if secret is not None else os.environ.get('RIDENOVA_STRIPE_TEST_SECRET', '')
        if self.secret and not self.secret.startswith('sk_test_'):
            raise ValueError('Only Stripe test-mode secret keys are accepted')

    @property
    def enabled(self):
        return bool(self.secret)

    def call(self, method, endpoint, fields=None, idempotency=None):
        if not self.enabled:
            raise ProviderError('Stripe test-mode integration is not configured')
        if not endpoint.startswith('/v1/') or '//' in endpoint:
            raise ValueError('Invalid Stripe endpoint')
        data = urllib.parse.urlencode(fields or {}).encode() if method == 'POST' else None
        req = urllib.request.Request('https://api.stripe.com' + endpoint, data=data, method=method,
                                     headers={'Authorization': 'Bearer ' + self.secret,
                                              'Content-Type': 'application/x-www-form-urlencoded'})
        if idempotency:
            req.add_header('Idempotency-Key', idempotency)
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                result = json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            # Never include a provider response, request URL, or credentials in logs or client errors.
            raise ProviderError('Stripe test request failed; check provider dashboard test logs') from None
        if result.get('livemode') is not False:
            raise ProviderError('Provider did not confirm test mode')
        return result
