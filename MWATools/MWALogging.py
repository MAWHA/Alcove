"""日志与事件推送。

比旧版多两件事：
1. 除了写文件，还能把日志推给订阅者（GUI 实时显示）。
2. 提供一个线程安全的事件总线，让跑在后台线程的自动化流程把
   进度／截图／状态推给 UI 线程。
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from typing import Any

from .MWAPaths import LOG_DIR

__all__ = [
    "logger",
    "setup_logging",
    "get_logger",
    "LoggerManager",
    "Events",
    "events",
    "install_gui_handler",
]

logger = logging.getLogger("MWA")

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_configured = False


def setup_logging(
    level: int = logging.INFO,
    to_file: bool = True,
    console: bool = True,
) -> logging.Logger:
    """配置根 logger。重复调用是幂等的。"""
    global _configured
    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    if console:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if to_file:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            # 每次启动一个新文件，避免旧版那样无限追加
            log_file = LOG_DIR / f"mwa_{time.strftime('%Y%m%d_%H%M%S')}.log"
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except OSError as exc:  # 只读环境等
            logger.warning("无法创建日志文件：%s", exc)

    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """取子 logger，例如 ``get_logger("运行")``。"""
    return logger.getChild(name) if name else logger


class LoggerManager:
    """上游 ``LoggerManager`` 的兼容壳（单例，写 ``PYMWA.log``）。

    新代码用 :func:`setup_logging` —— 它会把日志按启动时间写进
    ``logs/mwa_时间戳.log``，并额外支持 GUI 实时订阅。这个类保留下来，
    是因为上游的 ``MWATools/adbcs.py``、``MWATools/cs.py`` 仍然
    ``from MWATools.MWALogging import logger``，以及有人可能直接构造它。
    """

    _instance: "LoggerManager | None" = None
    _configured = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        log_file: str = "PYMWA.log",
        log_level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        log_format: str = _LOG_FORMAT,
        date_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        if LoggerManager._configured:
            return

        self.log_file = log_file
        self.log_level = log_level
        self.logger = logger
        self.logger.setLevel(log_level)

        formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
        try:
            file_handler = RotatingFileHandler(
                filename=log_file,
                encoding="utf-8",
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except OSError as exc:  # 只读环境等
            self.logger.warning("无法创建日志文件 %s：%s", log_file, exc)

        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        LoggerManager._configured = True

    def get_logger(self) -> logging.Logger:
        return self.logger


class Events:
    """极简线程安全事件总线。

    GUI 订阅自己关心的事件；自动化流程在后台线程里 emit。
    订阅者自己负责把回调切回 UI 线程。
    """

    #: 常见事件名
    LOG = "log"                  # (levelname, message)
    TASK_START = "task_start"    # (task_name,)
    TASK_END = "task_end"        # (task_name, success, elapsed)
    STEP = "step"                # (text,)
    SCREEN = "screen"            # (numpy.ndarray)  当前截图
    STATE = "state"              # (kind, payload)  控制器/资源/任务状态
    FINISHED = "finished"        # (整体结束)

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subs: dict[str, list[Callable[..., None]]] = {}
        self._history: deque[tuple[str, tuple, float]] = deque(maxlen=500)

    def subscribe(self, event: str, callback: Callable[..., None]) -> Callable[[], None]:
        with self._lock:
            self._subs.setdefault(event, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._subs[event].remove(callback)
                except (KeyError, ValueError):
                    pass

        return unsubscribe

    def emit(self, event: str, *args: Any) -> None:
        with self._lock:
            self._history.append((event, args, time.time()))
            callbacks = list(self._subs.get(event, ()))
            if event != "*":
                callbacks += list(self._subs.get("*", ()))
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:  # 订阅者出错不能拖垮自动化流程
                logger.exception("事件订阅者 %r 处理 %s 时抛异常", callback, event)

    def history(self) -> list[tuple[str, tuple, float]]:
        with self._lock:
            return list(self._history)


events = Events()


class _GuiHandler(logging.Handler):
    """把 logging 记录转发到事件总线。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            events.emit(Events.LOG, record.levelname, self.format(record))
        except Exception:
            pass


def install_gui_handler() -> None:
    """把日志接到事件总线上（GUI 用）。幂等。"""
    for handler in logger.handlers:
        if isinstance(handler, _GuiHandler):
            return
    handler = _GuiHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
