import copy
import json
import random
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import suppress
from typing import List, Optional, Union

import fugle_realtime
import intervaltree
import numpy as np
import pandas as pd
import redis
from six import with_metaclass

from .settings import env
from .base import (
    FugleDispatcher,
    FugleGeneralBase,
    FugleGeneralMeta,
    FugleRealtimeManager,
    FugleWebSocketManger,
    alias_injection,
    borg_injection,
    fugle_dispatcher,
    fugle_realtime_manager,
)

REDIS_HOST = env.str("redis_host", "localhost")


class FuglePrototypeMixin(object):
    """
    FuglePrototypeMixin
    """

    __type__ = "fugle_prototype"

    def clone(self, *args, **attrs):
        if self.__class__ in {LowerBoundObserver, UpperBoundObserver} and args:
            attrs.update({"threshold": args[0]})

        obj = self.__class__(**attrs)
        obj.__dict__ = {**obj.__dict__, **{**self.__dict__, **attrs}}

        if attrs.pop("deep", True):
            return copy.deepcopy(obj)
        else:
            return obj


class IObserver(ABC, FugleGeneralBase, object):
    """
    IObserver
    """

    __metaclass__ = FugleGeneralMeta

    @abstractmethod
    def update(self, subject) -> None:
        return NotImplemented

    def expose(self):
        pass


class FugleSubjectMixin(object, with_metaclass(FugleGeneralMeta)):
    """
    FugleSubjectMixin
    """

    def __init__(self) -> None:
        self._option: dict = {}
        self._observers: List[IObserver] = []

    def update_option(self, **kwargs):
        self._option.update(kwargs)
        return self

    def expose_option(self):
        print(self, "->", self._option)
        return self._option

    @property
    def observers(self):
        return self._observers

    def attach(self, observer: IObserver):
        if isinstance(
            observer,
            (
                list,
                dict,
                tuple,
                set,
            ),
        ):
            if len(observer) == 0:
                self.attach(default_basic_observer)
            for _observer in observer:
                self.attach(_observer)
        elif observer not in self._observers:
            if self._option.get("verbose", None):
                print(f"attach {observer} -> {self}")
            self._observers.append(observer)
        return self

    def detach(self, observer: Union[IObserver, str]):
        with suppress(ValueError):
            if isinstance(observer, (IObserver,)):
                self._observers.remove(observer)
            elif isinstance(observer, (str,)):
                pass
        return self

    def detach_all(self):
        self._observers = []
        return self

    def notify(self, modifier: Optional[IObserver] = None) -> None:
        for _observer in self._observers:
            if modifier != _observer:
                _observer.update(self)

    def find_observer_by_name(self):
        for observer in self._observers:
            print("""observer:\x1b[32m {} \x1b[0m""".format(observer))

    register = attach
    unregister = detach
    set_option = update_option
    get_option = expose_option


class FugleData(FugleSubjectMixin):
    def __init__(
        self,
        symbol_id="",
        name="",
        mode="api",
        verbose=False,
        debug=False,
        fugle_realtime_manager: FugleRealtimeManager = fugle_realtime_manager,
        dispatcher: FugleDispatcher = fugle_dispatcher,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.d = {
            "2330": "台積電",
            "2884": "玉山金",
        }  # todo: mock mapping -> api mapping
        self.fugle_realtime_manager = fugle_realtime_manager
        self.symbol_id = symbol_id
        self.name = name or self.d.get(symbol_id, symbol_id)
        self._verbose = verbose
        self._debug = debug
        self._data = None
        self._mode = mode
        dispatcher.register(symbol_id, self)

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, new_flag):
        self._verbose = new_flag

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, new_flag):
        self._debug = new_flag

    @property
    def data(self) -> int:
        return self._data

    @data.setter
    def data(self, new_data: int) -> None:
        if not isinstance(
            new_data,
            (int, float, dict),
        ):
            raise Exception("WrongType")
        self._data = new_data
        self.notify()

    def set_data(self, new_data):
        self.data = new_data

    def update_quote(self):
        if self.verbose or self._option.get("verbose", None):
            print(self)
        self.data = self.fugle_realtime_manager.quote(self)

    def __repr__(self):
        return f"<{self.name}({self.symbol_id})>"


class RedisObserver(IObserver):
    def __init__(self, *args, **kwargs):
        super(RedisObserver, self).__init__(*args, **kwargs)
        self._r = redis.Redis(REDIS_HOST, decode_responses=1)
        self._p = redis.Redis(REDIS_HOST, decode_responses=1)
        self._s = redis.Redis(REDIS_HOST, decode_responses=1).pubsub()

    def update(self, subject: FugleData):
        self._r.set(subject.symbol_id, json.dumps(subject.data))


class MongoObserver(IObserver):
    def __init__(self, *args, **kwargs):
        super(MongoObserver, self).__init__(*args, **kwargs)

    def update(self, subject):
        pass


class UpperBoundObserver(IObserver, FuglePrototypeMixin):
    def __init__(self, threshold, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold
        self.last_price = None
        self.tracker = list()

    def update(self, subject):
        trade_price = subject.data.get("trade.price")
        self.last_price = trade_price
        self.tracker.append(self.last_price)
        if trade_price > self.threshold:
            print(f"{trade_price} > {self.threshold}")


class LowerBoundObserver(IObserver, FuglePrototypeMixin):
    def __init__(self, threshold, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold
        self.last_price = None
        self.tracker = list()

    def update(self, subject):
        trade_price = subject.data.get("trade.price")
        self.last_price = trade_price
        self.tracker.append(self.last_price)
        if trade_price < self.threshold:
            print(f"{trade_price} < {self.threshold}")


class MinMaxObserver(IObserver, FuglePrototypeMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracker = list()

    def update(self, subject):
        trade_price = subject.data.get("trade.price")
        if len(self.tracker) == 0:
            self.tracker.append(trade_price)
            return
        if trade_price < min(self.tracker):
            print(f"{subject.name} new min -> {trade_price}")
        elif trade_price > max(self.tracker):
            print(f"{subject.name} new max -> {trade_price}")
        self.tracker.append(trade_price)
        print(f"{subject.name}: {self.tracker}")


class BasicObserver(IObserver, FuglePrototypeMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self, subject):
        pass


default_redis_observer = RedisObserver()
default_mongo_observer = MongoObserver()
default_upper_bound_observer = UpperBoundObserver(threshold=1e2)
default_lower_bound_observer = LowerBoundObserver(threshold=1e2)
default_basic_observer = BasicObserver()
default_min_max_observer = MinMaxObserver()

default_observer_group = {
    default_lower_bound_observer,
    default_mongo_observer,
    default_redis_observer,
    default_upper_bound_observer,
    default_min_max_observer,
}
