from environs import Env

from fugle_realtime_extension import (
    FugleData,
    default_lower_bound_observer,
    default_min_max_observer,
    default_redis_observer,
    default_upper_bound_observer,
    fugle_dispatcher,
)

env = Env()
env.read_env()

fugle_data_2330 = (
    FugleData("2330")
    .set_option(verbose=True, debug=False)
    .attach(
        {
            default_lower_bound_observer.clone(500),
            default_upper_bound_observer.clone(530),
            default_redis_observer,
            default_min_max_observer.clone(),
        }
    )
)

fugle_data_2884 = (
    FugleData("2884")
    .set_option(verbose=True)
    .attach(
        {
            default_lower_bound_observer.clone(20),
            default_upper_bound_observer.clone(30),
            default_min_max_observer.clone(),
        }
    )
)

if __name__ == "__main__":
    fugle_dispatcher.start()
