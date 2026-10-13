"""屏幕层：把 maafw 的「识别 / 动作」原语包成同步的、好用的 Python 接口。

这是新架构的核心。**整条流水线不再由 pipeline JSON 驱动**，
而是用普通 Python 控制流调用这里的方法：

    if box := screen.text("签到", roi=(0, 0, 1280, 100)):
        screen.click(box, delay=2000)

关于坐标系（已在真机实测两次独立确认，这是全项目的基石）：
    ``Controller.post_click/post_swipe`` 接收的是**截图坐标系**里的坐标，
    即资源包基准分辨率（本项目为 1280x720）下的坐标，与识别返回的 box 同一套。
    框架内部会自己换算到设备真实分辨率，调用方**不需要**做任何缩放。

    实验一（点击，判别力最强）：物理 2560x1374 / 截图 1341x720，缩放比 1.9090。
    Android 13 设置是横屏双栏，左栏底部「显示」的 OCR 框在截图坐标 (82, 655)。
    直接用它当坐标点击——
      · 若按截图坐标解读 → 命中「显示」（y=655 仍在左栏列表内）；
      · 若按原始坐标解读 → 落点相当于截图 y=343，会命中「通知」。
    结果是打开了「显示」页（页面上出现 深色主题 / 字体大小 / 亮度）。
    ⇒ 点击吃截图坐标。

    实验二（滑动，两个幅度都远离列表 clamp 边界）：以「提示音和振动」的
    OCR 框为标尺，在**截图坐标系**里下发位移，实测位移（同为截图坐标）：
      下发 100 → 位移 97；下发 150 → 位移 148；下发 200 → 位移 204。
    比值恒为 1.0。若它吃的是原始坐标，同样的下发量只应产生 52 / 79 / 105。
    ⇒ 滑动也吃截图坐标。
"""

from __future__ import annotations

import subprocess
import time as _time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

import numpy as np

from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch
from maa.tasker import Tasker

from .MWALogging import Events, events, get_logger

__all__ = ["Match", "Screen", "RectLike", "TargetLike"]

logger = get_logger("屏幕")

RectLike = Union["Match", tuple, list, Any]
TargetLike = Union[None, "Match", tuple, list, Any]

#: 资源包基准分辨率（由 pipeline 里的 roi 取值范围反推：x+w 最大 1280，y+h 最大 725）
BASE_SIZE = (1280, 720)

_DEFAULT_INTERVAL_MS = 200


@dataclass
class Match:
    """一次识别的结果。未命中时 ``hit`` 为 False，其余字段无意义。"""

    hit: bool = False
    box: tuple[int, int, int, int] = (0, 0, 0, 0)
    score: float = 0.0
    text: str = ""
    algorithm: str = ""
    raw: Any = None

    @property
    def x(self) -> int:
        return self.box[0]

    @property
    def y(self) -> int:
        return self.box[1]

    @property
    def w(self) -> int:
        return self.box[2]

    @property
    def h(self) -> int:
        return self.box[3]

    @property
    def center(self) -> tuple[int, int]:
        """中心点。maafw 的 ``Rect`` 没有 center，这里补上。"""
        return (self.box[0] + self.box[2] // 2, self.box[1] + self.box[3] // 2)

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.box

    def offset(self, dx: int = 0, dy: int = 0) -> tuple[int, int, int, int]:
        return (self.box[0] + dx, self.box[1] + dy, self.box[2], self.box[3])

    def __bool__(self) -> bool:
        return self.hit

    def __repr__(self) -> str:
        if not self.hit:
            return "Match(未命中)"
        label = f" {self.text!r}" if self.text else ""
        return f"Match({self.box}{label} score={self.score:.3f})"


def _as_box(target: Any) -> Optional[tuple[int, int, int, int]]:
    """把各种形状的目标归一成 (x, y, w, h)。"""
    if target is None:
        return None
    if isinstance(target, Match):
        return target.box
    if hasattr(target, "x") and hasattr(target, "w"):  # maa.Rect
        return (int(target.x), int(target.y), int(target.w), int(target.h))
    if isinstance(target, (tuple, list)):
        if len(target) == 4:
            return (int(target[0]), int(target[1]), int(target[2]), int(target[3]))
        if len(target) == 2:
            return (int(target[0]), int(target[1]), 0, 0)
    raise TypeError(f"无法解析的坐标目标: {target!r}")


class Screen:
    """同步的「眼睛与手」。

    所有 ``post_*`` 都会立刻 ``wait()``，因此调用方看到的是阻塞式语义，
    但**绝不能在 maafw 的通知回调 / 自定义动作线程里调用本类**（会死锁）。
    """

    def __init__(
        self,
        tasker: Tasker,
        controller: Any,
        *,
        adb: Optional[tuple[Any, str]] = None,
        emit_screen: bool = True,
        interval_ms: int = _DEFAULT_INTERVAL_MS,
    ) -> None:
        self._tasker = tasker
        self._controller = controller
        #: (adb 可执行文件路径, 设备地址)，仅 ADB 目标有；给 shell() 当退路
        self.adb = adb
        self._image: Optional[np.ndarray] = None
        self._emit_screen = emit_screen
        self.interval_ms = interval_ms

    # ------------------------------------------------------------------ 截图

    def capture(self, refresh: bool = False) -> np.ndarray:
        """取当前画面（BGR ndarray）。

        默认走缓存——一次动作后缓存失效，同一屏上的多次识别共用一张图，
        既快又能保证「看到的是同一帧」。
        """
        if self._image is None or refresh:
            image = self._controller.post_screencap().wait().get()
            if image is None:
                raise RuntimeError("截图失败：控制器返回空画面")
            self._image = image
            if self._emit_screen:
                events.emit(Events.SCREEN, image)
        return self._image

    def invalidate(self) -> None:
        """丢弃缓存，下次识别重新截图。"""
        self._image = None

    @property
    def cache(self) -> Optional[np.ndarray]:
        return self._image

    # ------------------------------------------------------------------ 识别

    def _recognize(self, reco_type: JRecognitionType, param: Any, refresh: bool) -> Match:
        image = self.capture(refresh=refresh)
        job = self._tasker.post_recognition(reco_type, param, image)
        detail = job.wait().get()
        if detail is None or not detail.nodes:
            return Match()
        nd = detail.nodes[0].recognition
        if nd is None or not nd.hit or nd.box is None:
            return Match(raw=nd)
        box = (int(nd.box.x), int(nd.box.y), int(nd.box.w), int(nd.box.h))
        score = 0.0
        text = ""
        best = nd.best_result
        if best is not None:
            score = float(getattr(best, "score", 0.0) or 0.0)
            text = str(getattr(best, "text", "") or "")
        return Match(
            hit=True, box=box, score=score, text=text,
            algorithm=str(nd.algorithm or ""), raw=nd,
        )

    def find(
        self,
        template: Union[str, list[str]],
        *,
        roi: Optional[tuple[int, int, int, int]] = None,
        threshold: float = 0.7,
        green_mask: bool = False,
        order_by: str = "Horizontal",
        index: int = 0,
        method: int = 5,
        refresh: bool = True,
    ) -> Match:
        """模板匹配。

        ``template`` 是**相对资源包 ``image/`` 目录**的路径，
        例如 ``"Startup/12.png"``，与旧 pipeline 的 ``template`` 字段语义一致。
        """
        names = [template] if isinstance(template, str) else list(template)
        param = JTemplateMatch(
            template=names,
            roi=roi or (0, 0, 0, 0),
            threshold=[threshold] * len(names),
            order_by=order_by,
            index=index,
            method=method,
            green_mask=green_mask,
        )
        return self._recognize(JRecognitionType.TemplateMatch, param, refresh)

    def text(
        self,
        expected: Union[str, list[str]],
        *,
        roi: Optional[tuple[int, int, int, int]] = None,
        threshold: float = 0.3,
        replace: Optional[list[list[str]]] = None,
        order_by: str = "Horizontal",
        index: int = 0,
        only_rec: bool = False,
        refresh: bool = True,
    ) -> Match:
        """OCR。``expected`` 里任意一项命中即算命中（支持正则）。"""
        exp = [expected] if isinstance(expected, str) else list(expected)
        param = JOCR(
            expected=exp,
            roi=roi or (0, 0, 0, 0),
            threshold=threshold,
            replace=replace or [],
            order_by=order_by,
            index=index,
            only_rec=only_rec,
        )
        return self._recognize(JRecognitionType.OCR, param, refresh)

    def texts(
        self,
        *,
        roi: Optional[tuple[int, int, int, int]] = None,
        threshold: float = 0.3,
        refresh: bool = True,
    ) -> list[Match]:
        """把区域内所有文字都识别出来（``expected=[".*"]``）。"""
        match = self.text([".*"], roi=roi, threshold=threshold, refresh=refresh)
        raw = match.raw
        if raw is None:
            return []
        out: list[Match] = []
        for item in (raw.filtered_results or []):
            box = getattr(item, "box", None)
            if box is None:
                continue
            out.append(
                Match(
                    hit=True,
                    box=(int(box.x), int(box.y), int(box.w), int(box.h)),
                    score=float(getattr(item, "score", 0.0) or 0.0),
                    text=str(getattr(item, "text", "") or ""),
                    algorithm="OCR",
                    raw=item,
                )
            )
        return out

    def exists(self, template: Union[str, list[str]], **kwargs: Any) -> bool:
        return self.find(template, **kwargs).hit

    # ------------------------------------------------------------------ 动作

    @staticmethod
    def _point(target: Any, offset: Optional[tuple[int, int, int, int]]) -> tuple[int, int]:
        box = _as_box(target)
        if box is None:
            raise ValueError("click 需要一个坐标目标（Match / (x,y) / (x,y,w,h)）")
        x, y, w, h = box
        if offset:
            x += int(offset[0])
            y += int(offset[1])
        return (x + w // 2, y + h // 2)

    def click(
        self,
        target: TargetLike = None,
        *,
        offset: Optional[tuple[int, int, int, int]] = None,
        delay: int = 0,
        wait_freezes: Optional[int] = None,
        contact: int = 0,
        desc: str = "",
    ) -> bool:
        """点击。

        ``target``：
          * ``Match`` / ``(x, y, w, h)`` —— 点该矩形中心（对应旧 pipeline 的 ``target: true``）
          * ``(x, y)`` / 长度为 4 但 w=h=0 —— 点绝对坐标（对应 ``target: [x, y, 0, 0]``）
          * ``None`` —— 点屏幕中心

        ``offset`` 对应旧 pipeline 的 ``target_offset``，叠加在矩形上。
        """
        x, y = self._point(target, offset) if target is not None else (BASE_SIZE[0] // 2, BASE_SIZE[1] // 2)
        logger.debug("点击 (%d, %d) %s", x, y, desc)
        self._controller.post_click(x, y, contact=contact).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        if wait_freezes:
            self.wait_freezes(time=wait_freezes)
        return True

    def long_press(self, target: TargetLike, *, duration: int = 1000, delay: int = 0) -> bool:
        x, y = self._point(target, None)
        if hasattr(self._controller, "post_touch_down"):
            self._controller.post_touch_down(x, y).wait()
            self.sleep(duration)
            self._controller.post_touch_up().wait()
        else:  # 退化为滑动到原地
            self._controller.post_swipe(x, y, x, y, duration).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        return True

    def swipe(
        self,
        begin: TargetLike,
        end: TargetLike,
        *,
        duration: int = 300,
        delay: int = 0,
        wait_freezes: Optional[int] = None,
        desc: str = "",
    ) -> bool:
        x1, y1 = self._point(begin, None)
        x2, y2 = self._point(end, None)
        logger.debug("滑动 (%d,%d) -> (%d,%d) %s", x1, y1, x2, y2, desc)
        self._controller.post_swipe(x1, y1, x2, y2, duration).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        if wait_freezes:
            self.wait_freezes(time=wait_freezes)
        return True

    def press_key(self, keycode: int, *, delay: int = 0) -> bool:
        self._controller.post_click_key(keycode).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        return True

    def input_text(self, content: str, *, delay: int = 0) -> bool:
        self._controller.post_input_text(content).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        return True

    def start_app(self, intent: str, *, delay: int = 0, wait_freezes: Optional[int] = None) -> bool:
        """启动应用。``intent`` 形如 ``包名/Activity`` 或 ``包名``。"""
        logger.info("启动应用 %s", intent)
        self._controller.post_start_app(intent).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        if wait_freezes:
            self.wait_freezes(time=wait_freezes)
        return True

    def stop_app(self, intent: str, *, delay: int = 0) -> bool:
        logger.info("关闭应用 %s", intent)
        self._controller.post_stop_app(intent).wait()
        self.invalidate()
        if delay:
            self.sleep(delay)
        return True

    def shell(self, command: str, *, timeout: int = 20000) -> str:
        """在设备上执行 shell 命令（主要给调试和取设备信息用）。

        注意：maafw 5.14.3 的 ``AdbController`` 并**不支持** ``post_shell``
        （原生会打 ``Shell is not supported for this controller type``），
        所以这里在拿到空结果时退回直接调用 adb。ADB 目标才有这条退路。
        """
        try:
            result = self._controller.post_shell(command, timeout=timeout).wait().get()
            if result:
                return result
        except Exception as exc:  # 不支持时不该炸掉调用方
            logger.debug("post_shell 不可用：%s", exc)

        if self.adb:
            adb_path, address = self.adb
            try:
                proc = subprocess.run(
                    [str(adb_path), "-s", str(address), "shell", command],
                    capture_output=True,
                    text=True,
                    timeout=max(timeout / 1000.0, 5.0),
                )
                return proc.stdout or ""
            except Exception as exc:
                logger.warning("adb shell 失败：%s", exc)
        return ""

    # ------------------------------------------------------------------ 等待

    @staticmethod
    def sleep(ms: int) -> None:
        if ms > 0:
            _time.sleep(ms / 1000.0)

    def wait_freezes(
        self,
        *,
        time: int = 1000,
        timeout: int = 20000,
        threshold: float = 0.95,
        interval: int = 300,
    ) -> bool:
        """等待画面静止。

        对应旧 pipeline 的 ``post_wait_freezes``。maafw 只在 ``Context`` 上提供该能力，
        而我们走的是纯 Python 控制流，所以这里用逐帧比对自己实现：
        相邻两帧的相似度连续 ``time`` 毫秒都不低于 ``threshold`` 即认为静止。
        """
        deadline = _time.monotonic() + timeout / 1000.0
        stable_since: Optional[float] = None
        previous = self.capture(refresh=True)

        while _time.monotonic() < deadline:
            _time.sleep(interval / 1000.0)
            current = self.capture(refresh=True)
            similar = _similarity(previous, current) >= threshold
            previous = current
            now = _time.monotonic()
            if not similar:
                stable_since = None
                continue
            if stable_since is None:
                stable_since = now
            elif (now - stable_since) * 1000.0 >= time:
                return True
        return False

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout: int = 20000,
        interval: int = _DEFAULT_INTERVAL_MS,
    ) -> bool:
        """反复调用 ``predicate``（每次都会重新截图）直到为真或超时。"""
        deadline = _time.monotonic() + timeout / 1000.0
        while True:
            self.invalidate()
            if predicate():
                return True
            if _time.monotonic() >= deadline:
                return False
            _time.sleep(interval / 1000.0)


def _similarity(a: np.ndarray, b: np.ndarray) -> float:
    """两帧相似度，1.0 表示完全一致。

    与 maafw 的 ``threshold`` 语义对齐：平均每通道差 12.75 以内算 0.95 相似。
    """
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float(1.0 - diff.mean() / 255.0)
