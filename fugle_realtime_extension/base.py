import threading
import time
from functools import partial

import numpy as np
import websocket
import json
from fugle_realtime import intraday

from .settings import env

if __import__("typing").TYPE_CHECKING:
    from .core import FugleData, FugleSubjectMixin, FuglePrototypeMixin


def borg_injection(cls):
    cls._sst = {}

    def _init(self, *args, **kwargs):
        self.__dict__ = cls._sst
        cls.__init__(self, *args, **kwargs)

    cls.__init__ = _init

    return cls


def alias_injection(cls, method, alias):
    _method = getattr(cls, method, None)
    _alias = getattr(cls, alias, None)

    if _method is None:
        raise Exception("...")
    elif _alias is not None:
        raise Exception("prevented")
    else:
        setattr(cls, alias, _method)

    return


class FugleGeneralMeta(type):
    """
    FugleGeneralMeta
    """

    def __new__(cls, name, base, d):
        setattr(cls, "cluster", getattr(cls, "cluster", set()))
        cls.cluster.add(name)
        args = (cls, name, base, d)
        return super().__new__(*args)

    def __init__(cls, name, base, d):
        return


class FugleGeneralBase(object):
    """
    FugleGeneralBase
    """

    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop("name", time.time().__str__())
        self.__class__._sibling.append(
            {"name": self.name, "ptr": hex(id(self))}
        )

    def __new__(cls, *args, **kwargs):
        setattr(cls, "_counter", getattr(cls, "_counter", 0))
        setattr(cls, "_sibling", getattr(cls, "_sibling", list()))
        cls._counter += 1
        return super(FugleGeneralBase, cls).__new__(cls)

    def __repr__(self, *args, **kwargs):
        return f"<{self.__class__.__name__}>"


class BorgMixin(object):
    """
    BorgMixin
    """

    _private_sst = {}

    def __init__(self, *args, **kwargs):
        self.__dict__ = self._private_sst


class SingleUpdater(threading.Thread, metaclass=FugleGeneralMeta):
    """
    SingleUpdater
    """

    def __init__(self, target, *args, **kwargs):
        super(SingleUpdater, self).__init__(
            *args, **kwargs
        )  # threading.Thread.__init__(self)
        self.daemon = True
        self._target = target
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        while not self._stopped:
            self._target()

    def start(self):
        super(SingleUpdater, self).start()
        return self


class FugleDispatcher(FugleGeneralBase, metaclass=FugleGeneralMeta):
    """
    FugleDispatcher
    """

    def __init__(self):
        self._objects = {}
        self._threads = {}
        self._threads_ws = {}

    def __repr__(self):
        return f"{super().__repr__()}({self.objects})"

    @property
    def objects(self):
        return self._objects

    def get_objects(self):
        return self._objects

    def register(self, name, obj):
        self._objects[name] = obj

    def unregister(self, name):
        try:
            self._threads[name].stop()
        except:
            pass
        try:
            del self._objects[name]
            print("\x1b[34m {} \x1b[0m".format(f"unregister {name}"))
        except Exception as e:
            print("""e:\x1b[31m {} \x1b[0m""".format(e))
            raise e

    def start(self, create_new_blocker=True):
        _fugle_data: "FugleData"
        for _fugle_data in self._objects.values():
            self._threads.update(
                {
                    _fugle_data.symbol_id: SingleUpdater(
                        target=partial(self.update, _fugle_data)
                    ).start()
                }
            )
        if create_new_blocker:
            self.run_forever()

    def start_ws(self):
        for key in self._threads_ws:
            self._threads_ws[key].start()

    def run_forever(self):
        while 1:
            time.sleep(1e-2)

    def update(self, fugle_data):
        fugle_data.update_quote()
        time.sleep(5)

    def get(self, symbol_id) -> "FugleData":
        return self._objects.get(symbol_id)

    run = execute = start


class FugleRealtimeManager(BorgMixin, metaclass=FugleGeneralMeta):
    """
    FugleRealtimeManager
    """

    def __init__(self, api_token="demo", borg=False):
        if borg:
            super(FugleRealtimeManager, self).__init__(self)
        self._api_token = api_token

    @property
    def api_token(self):
        return self._api_token

    @api_token.setter
    def api_token(self, new_token):
        self._api_token = new_token

    def quote(self, fugle_data: "FugleData"):
        if fugle_data._mode in {"ws", "websocket"}:
            FugleWebSocketManger(
                fugle_data.symbol_id, self.api_token, fugle_data
            ).connect()
        else:
            df_quote = intraday.quote(
                apiToken=self.api_token, symbolId=fugle_data.symbol_id
            )

            error_code = df_quote.get("error.code")
            if error_code is not None and error_code.item().__str__() == "403":
                raise Exception("請確認您的 `api_token` 是否正確、 以及是否超過最大允許連線數！！")

            if fugle_data.debug or fugle_data._option.get("debug", None):
                df_quote["trade.price"] *= np.random.uniform(0.5, 1.605)

            return {
                _column: df_quote.get(_column).item()
                for _column in [
                    column
                    for column in df_quote.columns
                    if any([column.startswith(kw) for kw in {"trade"}])
                ]
            }


fugle_dispatcher = FugleDispatcher()
fugle_realtime_manager = FugleRealtimeManager(
    api_token=env.str("api_token", "demo"), borg=False
)


class FugleWebSocketManger(
    FugleGeneralBase, object, metaclass=FugleGeneralMeta
):
    def __init__(
        self,
        symbol_id,
        uri=None,
        api_token=None,
        auto_reconnect=True,
        fugle_data: "FugleData" = None,
        fugle_dispatcher=fugle_dispatcher,
    ):
        self.symbol_id = symbol_id
        self.api_token = api_token or env.str("api_token", "demo")
        self.auto_reconnect = auto_reconnect
        self.uri = (
            uri
            or f"wss://api.fugle.tw/realtime/v0/intraday/quote?symbolId={self.symbol_id}&apiToken={self.api_token}"
        )
        self.ws = None
        self.fugle_data = fugle_data
        self.fugle_dispatcher = fugle_dispatcher

    def rp(self, f, *args):
        return lambda *a: f(*(a + (self,)))  # return lambda *a: f(*(a + args))

    @staticmethod
    def on_open(ws):
        print("[on_open]")

    @staticmethod
    def on_message(ws, message):
        print("""message:\x1b[32m {} \x1b[0m""".format(message))
        _data = json.loads(message)["data"]
        print(
            "\x1b[34m {} \x1b[0m {}".format(
                _data["info"]["symbolId"], _data["quote"]
            )
        )

    @staticmethod
    def on_close(ws, self):
        print("[on_close]")
        for i in range(5)[::-1]:
            print(f"{i}...", end="\r")
            time.sleep(1)
        if self.auto_reconnect:
            self.connect()
            self.fugle_dispatcher.start_ws()

    def connect(self, imme=False):
        self.ws = websocket.WebSocketApp(
            self.uri,
            on_open=FugleWebSocketManger.on_open,
            on_close=self.rp(FugleWebSocketManger.on_close),
            on_message=FugleWebSocketManger.on_message,
        )

        def _():
            self.ws.run_forever()
            while 1:
                time.sleep(1e-2)

        key = f"ws-{self.symbol_id}"
        self.fugle_dispatcher.register(key, self.ws)
        self.fugle_dispatcher._threads_ws[key] = threading.Thread(
            target=_, daemon=False
        )

    register = prepare = connect
