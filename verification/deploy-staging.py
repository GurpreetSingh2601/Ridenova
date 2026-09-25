"""Run ONLY in the authorized GitHub staging environment with protected secrets."""
import json
import os
import time
import urllib.parse
import urllib.request


def main():
    origin = os.environ['RIDENOVA_STAGING_ORIGIN'].rstrip('/')
    revision = os.environ['DEPLOY_COMMIT']
    if not origin.startswith('https://') or not revision:
        raise SystemExit('Missing staging origin or verified commit')
    def trigger(key):
        hook = os.environ[key]
        parsed = urllib.parse.urlsplit(hook)
        if parsed.scheme != 'https' or parsed.hostname != 'api.render.com':
            raise SystemExit('Expected a Render deploy hook')
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(k,v) for k,v in query if k != 'ref'] + [('ref', revision)]
        url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        # Do not print the hook, response body or exception (which can contain it).
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                if response.status != 200: raise RuntimeError()
        except Exception:
            raise SystemExit('Deploy hook failed; inspect Render privately') from None
    def await_ready(path, predicate):
        for _ in range(120):
            try:
                with urllib.request.urlopen(origin+path, timeout=10) as response:
                    if response.status == 200 and predicate(json.load(response)): return
            except Exception: pass
            time.sleep(5)
        raise SystemExit('Deployment did not become ready. Follow rollback procedure; no automatic destructive rollback was attempted.')
    trigger('RENDER_API_DEPLOY_HOOK')
    await_ready('/health', lambda result: result.get('revision') == revision)
    trigger('RENDER_WORKER_DEPLOY_HOOK')
    await_ready('/ready', lambda result: result.get('status') == 'ready')
    print('Both staging services report the verified revision as ready.')


if __name__ == '__main__': main()
