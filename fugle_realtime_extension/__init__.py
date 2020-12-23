import time
import functools

from .core import (
    FugleData,
    fugle_dispatcher,
    default_min_max_observer,
    default_lower_bound_observer,
    default_upper_bound_observer,
    default_redis_observer,
    default_mongo_observer,
)

from .base import (
    FugleWebSocketManger,
    fugle_realtime_manager,
)

from .utils import FugleExtensionUtils

FugleExtensionUtils.iife(
    lambda: (
        FugleExtensionUtils.exit(
            functools.partial(
                lambda x: print(
                    "\x1b[34m{}\x1b[0m".format(round(time.time() - x, 4))
                ),
                time.time(),
            )
        ),
    )
)

__all__ = [
    FugleData.__name__,
    FugleWebSocketManger.__name__,
    FugleExtensionUtils.__name__,
]
