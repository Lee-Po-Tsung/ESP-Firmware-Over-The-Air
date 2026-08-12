"""Fleet state the server works out instead of storing.

A device only ever reports facts about itself: when it last spoke, what
version it runs, how long it means to wait before speaking again. Whether
that adds up to "online" is a reading of those facts at the moment someone
asks, and it changes with no write happening anywhere, so there is no column
for it and no job that keeps one current.

The reading lives here rather than in the dashboard because the server is the
only place holding both halves of it. Handing the raw numbers to a frontend
that divides them itself puts a second copy of the rule one refactor away from
disagreeing with this one.
"""

from __future__ import annotations

from datetime import datetime

# A single late check-in means a slow TLS handshake more often than it means a
# dead device, so allow a few before saying anything.
MISSED_CHECKINS_BEFORE_OFFLINE = 3

# Floor under the derived threshold. A device polling every second would
# otherwise be called offline over one retry.
MIN_OFFLINE_SECONDS = 15


def is_online(
    last_seen: datetime | None,
    poll_interval_seconds: int | None,
    now: datetime,
) -> bool | None:
    """Whether a device is still checking in on schedule.

    None means unknowable, not offline: a device that has never checked in, or
    one running firmware from before it reported its interval. Calling those
    offline would file a device that answered a second ago next to one that has
    been dark for a week.
    """
    if last_seen is None or poll_interval_seconds is None or poll_interval_seconds <= 0:
        return None

    offline_interval = (now - last_seen).total_seconds()
    if (
        offline_interval >= poll_interval_seconds * MISSED_CHECKINS_BEFORE_OFFLINE
        and offline_interval >= MIN_OFFLINE_SECONDS
    ):
        return False

    return True
