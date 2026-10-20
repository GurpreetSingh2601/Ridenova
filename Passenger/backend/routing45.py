"""Server-owned, bounded traffic-aware pickup routes. No credentials in responses."""
import json
import math
import os
import threading
import urllib.request


class PickupRoutes:
    def __init__(self, service):
        self.s = service
        self.cache = {}
        self.lock = threading.RLock()
        self.provider = self.google
        self.calls = []

    def google(self, origin, destination):
        key = os.environ.get('RIDENOVA_ROUTES_SERVER_KEY', '')
        if not key:
            raise ValueError('Routing is not configured')
        def waypoint(p):
            return {'location': {'latLng': {k: p[k] for k in ('latitude', 'longitude')}}}
        body = {'origin': waypoint(origin), 'destination': waypoint(destination),
                'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE',
                'polylineQuality': 'OVERVIEW'}
        request = urllib.request.Request('https://routes.googleapis.com/directions/v2:computeRoutes',
            json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key,
            'X-Goog-FieldMask': 'routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline'})
        with urllib.request.urlopen(request, timeout=3) as response:
            route = json.loads(response.read(1000000))['routes'][0]
        distance = route['distanceMeters']
        seconds = float(route['duration'].removesuffix('s'))
        if type(distance) is not int or not 0 <= distance <= 1000000 or not math.isfinite(seconds) or not 0 <= seconds <= 86400:
            raise ValueError('Invalid route')
        return dict(distanceMeters=distance, durationSeconds=math.ceil(seconds),
                    encodedPolyline=route['polyline']['encodedPolyline'])

    def get(self, driver_id, origin, destination):
        now = self.s.clock()
        key = (driver_id, destination['latitude'], destination['longitude'])
        with self.lock:
            previous = self.cache.get(key)
            if previous and now - previous['estimatedAtEpochMs'] < 30000 and self.s.distance_km(
                    origin['latitude'], origin['longitude'], previous['origin']['latitude'], previous['origin']['longitude']) < .1:
                return dict(previous)
            # Per-process hard cap and failure caching prevent a two-second poll from becoming an unbounded paid API loop.
            self.calls = [t for t in self.calls if now-t < 60000]
            cap = int(os.environ.get('RIDENOVA_ROUTE_CALLS_PER_MINUTE', '30'))
            try:
                if len(self.calls) >= cap:
                    raise ValueError('Route budget reached')
                self.calls.append(now)
                result = {**self.provider(origin, destination), 'source': 'GOOGLE_ROADS', 'trafficAware': True}
            except Exception:
                distance = self.s.distance_km(origin['latitude'], origin['longitude'], destination['latitude'], destination['longitude'])
                result = dict(distanceMeters=round(distance*1000), durationSeconds=math.ceil(distance/28*3600+60),
                              encodedPolyline='', source='STRAIGHT_LINE_FALLBACK', trafficAware=False)
            result.update(estimatedAtEpochMs=now, origin={k: origin[k] for k in ('latitude','longitude')})
            self.cache = {k:v for k,v in self.cache.items() if now-v['estimatedAtEpochMs'] < 60000}
            if len(self.cache) >= 500:
                self.cache.clear()
            self.cache[key] = result
            return dict(result)

    def allowed(self, route):
        strict = getattr(getattr(self.s, 'settings', None), 'environment', 'development') != 'development'
        if strict and route['source'] != 'GOOGLE_ROADS':
            return False
        return (route['distanceMeters'] <= float(os.environ.get('RIDENOVA_MAX_PICKUP_KM', '15' if strict else '50'))*1000
                and route['durationSeconds'] <= float(os.environ.get('RIDENOVA_MAX_PICKUP_MINUTES', '30' if strict else '60'))*60)
