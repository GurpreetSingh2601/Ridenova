"""Build 45 API. Scope and staff permissions are checked for every operation."""
from urllib.parse import parse_qs, urlsplit
from fleet28 import reject

def dispatch(s, authorize, handler, path, body):
    parts=path.removeprefix('/v4/trips/').split('/');method=handler.command
    header=handler.headers.get('Authorization','');q=parse_qs(urlsplit(handler.path).query)
    period=q.get('period',[None])[0];pay=s.compensation
    if parts[0]=='driver':
        driver=s.fleet.authenticate(header)
        settings=getattr(s,'settings',None)
        if settings and settings.environment=='staging':
            with s.connect() as db:row=db.execute('SELECT phone FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone()
            if not row or row[0] not in settings.driver_phones:reject(403,'STAGING_INVITE_REQUIRED','Staging invitation no longer active')
        if parts==['driver','earnings'] and method=='GET':return pay.report(driver,period)
        if parts==['driver','zones'] and method=='GET':
            with s.connect() as db:
                categories=s.fleet.categories(db,driver)
                return {'zones':[z for z in pay.zones(db) if z['category'] in categories],
                        'serverTimeEpochMs':s.clock(),'conditions':'Pickup in zone; eligible category; accept before expiry; complete trip. Highest single bonus only. Subject to budget at acceptance.'}
    if parts[0]=='admin':
        actor=authorize(header,'finance.write' if method=='POST' else 'finance.read')['id']
        if parts==['admin','policy'] and method in ('GET','POST'):return pay.policy(actor,body if method=='POST' else None)
        if parts==['admin','earnings'] and method=='GET':
            with s.connect() as db:s.operations44.audit(db,actor,'COMPENSATION_VIEW',period or 'CURRENT')
            return pay.report(q.get('driverId',[None])[0],period,q.get('rideId',[None])[0])
        if parts==['admin','review'] and method=='POST':return pay.review(actor,body)
        if parts==['admin','finalize'] and method=='POST':
            driver=body.get('driverId')
            if not isinstance(driver,str) or not driver:reject(400,'INVALID_DRIVER','Driver ID required')
            return pay.finalize(actor,driver,body.get('period'))
    reject(404,'NOT_FOUND','Endpoint not found')
