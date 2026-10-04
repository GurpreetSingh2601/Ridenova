"""Server-authoritative no-show flow. Payload additions require no schema change.
No passenger fee, financial award, or automated contact claim is created.
"""
from fleet28 import reject

WAIT_MS = 300_000
RADIUS_KM = 0.25
REASONS = {'RIDER_NOT_AT_PICKUP', 'CANNOT_FIND_RIDER'}


def near_pickup(fleet, db, driver_id, ride):
    row = db.execute('SELECT lat,lng,located_ms FROM fleet_drivers WHERE id=?', (driver_id,)).fetchone()
    point = ride['draft']['pickup']
    return bool(row and row[0] is not None and row[1] is not None and row[2] is not None
        and 0 <= fleet.service.clock() - row[2] <= 30_000
        and fleet.service.distance_km(row[0], row[1], point['latitude'], point['longitude']) <= RADIUS_KM)


def begin_wait(fleet, db, driver_id, ride):
    # Preserve legacy arrival semantics, but never qualify an unverified arrival
    # for no-show cancellation. A dedicated refresh can start a valid timer later.
    now = fleet.service.clock()
    ride['waiting'] = {'arrivedAtEpochMs': now, 'eligibleAtEpochMs': now + WAIT_MS,
                       'verifiedArrival': near_pickup(fleet, db, driver_id, ride), 'feeCents': 0}


def waiting_status(fleet, db, driver_id, ride):
    wait = ride.get('waiting', {})
    now = fleet.service.clock()
    verified = bool(wait.get('verifiedArrival'))
    remaining = max(0, (wait.get('eligibleAtEpochMs', now + WAIT_MS) - now + 999) // 1000)
    near = near_pickup(fleet, db, driver_id, ride)
    return {**wait, 'serverTimeEpochMs': now, 'remainingSeconds': remaining,
            'canCancel': ride['status'] == 'DRIVER_ARRIVED' and verified and remaining == 0 and near,
            'locationReady': near, 'status': ride['status'], 'feeCents': 0,
            'message': 'No fee will be charged. This is a staging no-show cancellation.'}


def cancel_no_show(fleet, db, driver_id, ride, body):
    if ride['status'] != 'DRIVER_ARRIVED':
        reject(409, 'INVALID_TRANSITION', 'No-show cancellation is available only before the trip starts')
    if not isinstance(body.get('reason'), str) or body['reason'] not in REASONS:
        reject(400, 'NO_SHOW_REASON_REQUIRED', 'Choose why the rider could not be picked up')
    if body.get('confirmedPickupChecked') is not True:
        reject(400, 'PICKUP_CHECK_REQUIRED', 'Confirm you checked the pickup point and instructions')
    if not waiting_status(fleet, db, driver_id, ride)['canCancel']:
        reject(409, 'WAIT_NOT_COMPLETE', 'Wait five minutes after verified arrival and remain near pickup with fresh GPS')
    now = fleet.service.clock()
    ride.update(status='CANCELLED_NO_SHOW', updatedAtEpochMs=now, cancellationFeeCad=0,
                cancellationReason=body['reason'])
    ride.setdefault('payment', {}).update(status='VOIDED', amountCents=0)
    ride['waiting']['cancelledAtEpochMs'] = now
    db.execute('DELETE FROM fleet_offers WHERE ride_id=?', (ride['id'],))
    db.execute('DELETE FROM fleet_radar_candidates WHERE ride_id=?', (ride['id'],))
