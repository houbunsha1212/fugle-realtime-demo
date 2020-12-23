from environs import Env
from fugle_realtime_extension import fugle_dispatcher, FugleWebSocketManger

env = Env()
env.read_env()

if __name__ == "__main__":
    FugleWebSocketManger("2330", auto_reconnect=True).register()
    FugleWebSocketManger("2331", auto_reconnect=False).register()
    FugleWebSocketManger("2884", auto_reconnect=True).register()
    fugle_dispatcher.start_ws()
