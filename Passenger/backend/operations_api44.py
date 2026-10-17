from urllib.parse import parse_qs,urlsplit
from fleet28 import reject

def dispatch(service,authorize,handler,path,body):
    o=service.operations44;method=handler.command;header=handler.headers.get('Authorization','');parts=path.removeprefix('/v3/operations/').split('/')
    if parts==['public-share'] and method=='POST':return o.public_share(body.get('token'))
    if parts[0]=='admin':
        action=parts[-1]
        permission='documents.write' if action=='document-policy' and method=='POST' else 'documents.read' if action=='document-policy' or parts[1:2]==['documents'] else 'tracking.write' if action=='reassign' else 'evidence.hold' if action=='hold' else 'tracking.read'
        actor=authorize(header,permission)['id']
        if parts==['admin','live'] and method=='GET':return o.live(actor)
        if parts==['admin','document-policy'] and method in ('GET','POST'):return service.fleet.document_policy(actor,body if method=='POST' else None)
        if len(parts)==4 and parts[1]=='rides':
            rid=parts[2]
            if action=='evidence' and method=='GET':
                try:cursor=int(parse_qs(urlsplit(handler.path).query).get('cursor',['0'])[0])
                except ValueError:reject(400,'INVALID_CURSOR','Invalid cursor')
                if not 0<=cursor<=1000000:reject(400,'INVALID_CURSOR','Invalid cursor')
                return o.detail(actor,rid,cursor)
            if action=='reassign' and method=='POST':return o.reassign(actor,rid,body)
            if action=='hold' and method=='POST':return o.hold(actor,rid,body)
        if len(parts)==5 and parts[1]=='documents' and method=='GET':
            with service.connect() as db:o.audit(db,actor,'DOCUMENT_HISTORY_VIEW',parts[2]+':'+parts[3])
            if action=='versions':return service.fleet.document_versions(parts[2],parts[3])
            try:rev=int(action)
            except ValueError:reject(400,'INVALID_REVISION','Invalid revision')
            return service.fleet.document_versions(parts[2],parts[3],rev)
    elif parts[0]=='driver':
        with service.fleet.auth_lock:
            driver=service.fleet.authenticate(header);settings=getattr(service,'settings',None)
            if settings and settings.environment=='staging':
                with service.connect() as db:row=db.execute('SELECT phone FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone()
                if not row or row[0] not in settings.driver_phones:reject(403,'STAGING_INVITE_REQUIRED','Staging invitation no longer active')
            if len(parts)==3 and parts[1]=='documents' and method=='GET':
                with service.connect() as db:o.audit(db,driver,'DRIVER_DOCUMENT_VIEW',parts[2])
                return service.fleet.document_content(driver,parts[2])
            if parts==['driver','inbox'] and method in ('GET','POST'):
                service.fleet.document_reminders();return o.inbox(driver,body if method=='POST' else None)
            if len(parts)==4 and parts[1]=='rides':
                if parts[3]=='check-in' and method in ('GET','POST'):return o.checkin(driver,parts[2],body if method=='POST' else None)
                if parts[3]=='route' and method=='POST':return o.route(driver,parts[2],body)
    elif parts[0]=='passenger':
        owner=service.authenticate(header)
        if len(parts)==4 and parts[1]=='rides':
            rid,action=parts[2:]
            if action=='consent' and method in ('GET','POST'):return o.consent(owner,rid,body if method=='POST' else None)
            if action=='location' and method=='POST':return o.passenger_point(owner,rid,body)
            if action=='share' and method=='POST':return o.share(owner,rid,body)
    reject(404,'NOT_FOUND','Endpoint not found')
