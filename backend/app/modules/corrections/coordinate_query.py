"""Conservative spherical bounds; the final eligibility test is exact Haversine."""

import math

from sqlalchemy import and_, false, or_

from app.models.master_sisa import CorrectionMasterObservation as Observation


def observation_window(lat: float, lon: float, radius: float):
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return false()
    angular = radius / 6371000.0
    delta = math.degrees(angular) + 1e-9
    latitude = Observation.latitude.between(max(-90, lat - delta), min(90, lat + delta))
    if abs(lat) + delta >= 90:
        return latitude
    longitude_delta = math.degrees(math.asin(min(1, math.sin(angular) / math.cos(math.radians(lat))))) + 1e-9
    lower, upper = lon - longitude_delta, lon + longitude_delta
    if lower < -180:
        longitude = or_(Observation.longitude >= lower + 360, Observation.longitude <= upper)
    elif upper > 180:
        longitude = or_(Observation.longitude >= lower, Observation.longitude <= upper - 360)
    else:
        longitude = Observation.longitude.between(lower, upper)
    return and_(latitude, longitude)
