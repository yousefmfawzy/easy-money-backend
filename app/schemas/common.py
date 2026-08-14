"""Shared serializers for API responses.

SQLite does not preserve tzinfo, so datetimes read back from the database are
naive even though every timestamp is written as UTC. Serializing those naively
would make the future React client interpret camp timestamps as local time, so
we reattach UTC on the way out and always emit an explicit `Z` designator.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

DecimalStr = Annotated[Decimal, PlainSerializer(lambda d: f"{d:.2f}", return_type=str)]


def _as_utc_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_as_utc_z, return_type=str)]
OptionalUtcDatetime = Annotated[
    datetime | None, PlainSerializer(_as_utc_z, return_type=str | None)
]
