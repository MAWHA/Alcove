"""任务抽象层：任务注册表 + 运行上下文 + 执行器。

这一层是新架构「模块化、互不干扰」的落点：

* 每个游戏功能写成一个模块，放在 ``PyPipeline/Tasks/`` 下；
* 模块顶部用 ``@task(...)`` 声明自己，导入即注册；
* 模块内部只依赖 ``TaskContext``（``ctx.screen`` 等），**不 import 别的任务模块**；
* 因此任何一个任务模块坏掉，都不会影响其它模块被加载。

任务函数签名统一为 ``def 某任务(ctx: TaskContext) -> bool``，
返回 True 表示按预期走完，False 表示中途放弃（不算异常）。
"""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence, Union

from .MWALogging import Events, events, get_logger
from .MWAScreen import Match, Screen

__all__ = [
    "Choice",
    "Option",
    "TaskSpec",
    "TaskContext",
    "TaskCancelled",
    "TaskFailed",
    "TaskResult",
    "Cand",
    "OCR",
    "IMG",
    "ANY",
    "Step",
    "MAIN_PAGE",
    "QUIT",
    "LOADING_WORDS",
    "EXCEPTION_CANDS",
    "handle_exceptions",
    "task",
    "register",
    "registry",
    "get_task",
    "all_tasks",
    "register_legacy_tasks",
    "legacy_task_keys",
    "TaskRunner",
]

#: 「旧流水线任务」所在的 UI 分组名 —— 迁完之后这个分组会自然消失。
LEGACY_GROUP = "旧流水线（待迁移）"

logger = get_logger("任务")


# --------------------------------------------------------------------- 选项模型


@dataclass(frozen=True)
class Choice:
    """select/checkbox 型选项的一个可选项。"""

    value: str
    label: str = ""

    @property
    def text(self) -> str:
        return self.label or self.value


@dataclass(frozen=True)
class Option:
    """一个可配置项。对应旧 ``interface.json`` 里 option 的一条。

    旧配置把「选项 → pipeline_override 片段」写死在 JSON 里；
    新架构把它变成任务函数里的一个普通参数，取值由 GUI 传入。
    """

    key: str
    label: str = ""
    kind: str = "select"          # select | switch | checkbox | int | str | bool
    default: Any = None
    choices: tuple[Choice, ...] = ()
    description: str = ""
    minimum: Optional[int] = None
    maximum: Optional[int] = None

    @property
    def text(self) -> str:
        return self.label or self.key

    def coerce(self, value: Any) -> Any:
        """把 GUI 传来的值收敛成这个选项该有的类型。"""
        if self.kind in ("int",):
            try:
                number = int(value)
            except (TypeError, ValueError):
                number = int(self.default or 0)
            if self.minimum is not None:
                number = max(self.minimum, number)
            if self.maximum is not None:
                number = min(self.maximum, number)
            return number
        if self.kind in ("bool", "switch"):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "y", "on", "是")
            return bool(value)
        if self.kind == "checkbox":
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            return list(value)
        if value is None and self.default is not None:
            return self.default
        return value


# --------------------------------------------------------------------- 任务模型


@dataclass(frozen=True)
class TaskSpec:
    """一个任务的声明。"""

    key: str
    name: str
    func: Callable[["TaskContext"], bool]
    group: str = "其他"
    description: str = ""
    options: tuple[Option, ...] = ()
    default_enabled: bool = False
    order: int = 100

    @property
    def label(self) -> str:
        return self.name or self.key

    def option(self, key: str) -> Optional[Option]:
        for item in self.options:
            if item.key == key:
                return item
        return None


_registry: dict[str, TaskSpec] = {}
_lock = threading.RLock()


def register(spec: TaskSpec) -> TaskSpec:
    with _lock:
        if spec.key in _registry:
            logger.warning("任务 %s 被重复注册，后者覆盖前者", spec.key)
        _registry[spec.key] = spec
    return spec


def task(
    key: str,
    name: str = "",
    *,
    group: str = "其他",
    description: str = "",
    options: Sequence[Option] = (),
    default_enabled: bool = False,
    order: int = 100,
) -> Callable[[Callable[["TaskContext"], bool]], Callable[["TaskContext"], bool]]:
    """把函数注册成一个任务。"""

    def decorator(func: Callable[["TaskContext"], bool]) -> Callable[["TaskContext"], bool]:
        register(
            TaskSpec(
                key=key,
                name=name or key,
                func=func,
                group=group,
                description=description or (func.__doc__ or "").strip().splitlines()[0] if (description or func.__doc__) else "",
                options=tuple(options),
                default_enabled=default_enabled,
                order=order,
            )
        )
        return func

    return decorator


def registry() -> dict[str, TaskSpec]:
    with _lock:
        return dict(_registry)


def get_task(key: str) -> Optional[TaskSpec]:
    with _lock:
        return _registry.get(key)


def all_tasks() -> list[TaskSpec]:
    with _lock:
        return sorted(_registry.values(), key=lambda s: (s.order, s.key))


# ------------------------------------------------------- 旧流水线任务的桥
#
# 迁移是渐进的：``assets/resource_picli/base/pipeline/`` 下还有一大部分任务
# 没写成 Python 模块。为了这段时间功能不回退，把 interface.json 里**还没有
# Python 实现**的任务自动注册成「旧流水线任务」——它们复用同一套注册表，
# 于是 CLI / GUI 一行代码都不用改，就能列出并运行它们，参数照旧从
# interface.json 的 option 生成下拉框。
#
# 每个旧任务被跑起来时做三件事：
#   1. 用当前选择（``ctx.settings``）跑一遍 ``MWATaskPipelineClass``，
#      产出官方顺序合并好的 ``pipeline_override`` 数组；
#   2. ``tasker.post_task(entry, override)`` 交给 maafw 原生执行；
#   3. 等它结束，按 ``TaskDetail.status`` 判定成败。
#
# 一旦某个任务被写成了 Python 模块，同名的旧任务会让位（注册表里已存在
# 就不再注册），所以迁移完一个就少一个，可以逐个替换、随时对照。


def _legacy_options(pipeline: Any, task_name: str) -> tuple[Option, ...]:
    """按 interface.json 的 option 定义生成 GUI/CLI 用的参数声明。"""
    out: list[Option] = []
    for key in pipeline.task_options(task_name):
        kind = pipeline.option_type(key)
        cases = pipeline.get_cases(key)
        choices = tuple(
            Choice(value=str(c.get("name", "")), label=str(c.get("label") or c.get("name") or ""))
            for c in cases
            if c.get("name")
        )
        if kind == "checkbox":
            out.append(Option(key=key, label=key, kind="checkbox", default=[], choices=choices))
        elif kind == "input":
            # 旧配置里没有 input 型；GUI 也还没做对应控件，先跳过。
            logger.debug("旧任务 %r 的 option %r 是 input 型，暂不支持", task_name, key)
        else:
            out.append(
                Option(key=key, label=key, kind="select", default=pipeline.default_case(key), choices=choices)
            )
    return tuple(out)


def _make_legacy_runner(task_name: str) -> Callable[["TaskContext"], bool]:
    """造一个「跑旧流水线」的任务函数。"""

    def _run(ctx: "TaskContext") -> bool:
        from maa.define import MaaStatusEnum

        from .MWATaskPipeline import MWATaskPipelineClass

        pipeline = MWATaskPipelineClass()
        pipeline.set_options(ctx.settings)

        entry = pipeline.get_task_entry(task_name)
        if not entry:
            raise TaskFailed(f"interface.json 里没有任务 {task_name!r} 的 entry")

        override = pipeline.build_override(task_name)
        ctx.step(f"旧流水线：{entry}（override {len(override)} 段）")

        tasker = ctx.tasker
        if tasker is None:
            raise TaskFailed("tasker 还没准备好，无法执行旧流水线")

        # 关键：override 是**有序数组**，合并由 maafw 原生完成
        # （节点内字段级浅合并，后者覆盖前者；next 这类列表整体替换）。
        detail = tasker.post_task(entry, override or None).wait().get()
        if detail is None:
            logger.error("旧流水线 %s 没有返回 TaskDetail", task_name)
            return False

        status = int(getattr(detail, "status", 0))
        ok = status == int(MaaStatusEnum.succeeded)
        if not ok:
            logger.warning("旧流水线 %s 结束状态为 %s（%s）", task_name, status, getattr(detail, "status", "?"))
        return ok

    _run.__name__ = f"legacy_{task_name}"
    _run.__doc__ = f"旧流水线任务：{task_name}"
    return _run


def register_legacy_tasks(
    *,
    group: str = LEGACY_GROUP,
    order_base: int = 500,
    path: Any = None,
) -> list[str]:
    """把 interface.json 里尚未有 Python 实现的任务注册成旧流水线任务。

    返回本次新注册的任务 key 列表。已经有 Python 实现（同名已注册）的任务会被跳过，
    所以这个函数是幂等的，也可以在迁移过程中反复调用。
    """
    from .MWATaskPipeline import MWATaskPipelineClass

    pipeline = MWATaskPipelineClass(path)
    if not pipeline.tasks:
        logger.debug("interface.json 里没有任务，跳过旧流水线注册")
        return []

    added: list[str] = []
    for index, task_name in enumerate(pipeline.tasks):
        if get_task(task_name) is not None:
            continue  # 已经有 Python 实现，旧流水线让位
        entry = pipeline.get_task_entry(task_name)
        register(
            TaskSpec(
                key=task_name,
                name=pipeline.get_label(task_name),
                func=_make_legacy_runner(task_name),
                group=group,
                description=(
                    pipeline.describe_task(task_name)
                    or f"interface.json 驱动：entry={entry}（尚未迁移成 Python 模块）"
                ),
                options=_legacy_options(pipeline, task_name),
                default_enabled=False,
                order=order_base + index,
            )
        )
        added.append(task_name)

    if added:
        logger.info("注册了 %d 个旧流水线任务（待迁移）：%s", len(added), added)
    return added


def legacy_task_keys() -> list[str]:
    """当前还在走旧流水线的任务 key（用于给用户看「迁移进度 n/19」）。"""
    return [s.key for s in all_tasks() if s.group == LEGACY_GROUP]



# --------------------------------------------------------------------- 异常


class TaskCancelled(Exception):
    """任务被用户中断。"""


class TaskFailed(Exception):
    """任务遇到无法继续的状况。"""


# --------------------------------------------------------------------- 候选项
#
# 旧 pipeline 里最常出现的结构是「一个 next 列表，里面一堆识别条件，谁先命中就执行谁」。
# 搬到 Python 之后没必要再写图，用下面这个小词汇表就够了：
#
#     ctx.scan(OCR("全部"), IMG("Mainpage/mail.png"), timeout=30000)
#
# 意思是「反复试这几个条件，谁先命中就点谁；一直试到超时为止」。
# 这正是 next 列表的语义，但它是普通 Python 表达式，能读、能调试、能自由组合。


@dataclass(frozen=True)
class Cand:
    """一个「找一找然后点一下」的候选项。

    Attributes:
        kind: ``"ocr"`` 文字识别 / ``"img"`` 模板匹配。
        target: OCR 时是词表（字符串，或字符串列表表示任一命中）；
            模板匹配时是图库里的相对路径（同样可以是列表）。
        roi: 只在这个区域里找，``(x, y, w, h)``，像素用**1280x720 基准**。
        threshold: 覆盖默认阈值（OCR 0.3 / 模板 0.7）。
        offset: 点的时候在识别框上叠加的偏移，``(dx, dy, dw, dh)``。
        point: 直接点这个绝对坐标 ``(x, y)``，**忽略识别框的位置**（对应旧
            pipeline 的 ``"target": [x, y, 0, 0]`` 写法）。
        delay: 点完之后等多少毫秒。
        wait_freezes: 点完之后再等画面静止多少毫秒。
        desc: 写进日志的中文说明。
        green_mask: 模板匹配时先抠掉绿色（旧 pipeline 的 ``green_mask``）。
        index: 多个命中里取第几个（旧 pipeline 的 ``index``，``-1`` = 最后一个）。
        method: 模板匹配算法编号，默认 5（``TM_CCOEFF_NORMED``）。
    """

    kind: str
    target: Any
    roi: Optional[tuple[int, int, int, int]] = None
    threshold: Optional[float] = None
    offset: Optional[tuple[int, int, int, int]] = None
    point: Optional[tuple[int, int]] = None
    delay: int = 0
    wait_freezes: Optional[int] = None
    desc: str = ""
    green_mask: bool = False
    index: int = 0
    method: int = 5

    def __repr__(self) -> str:
        what = self.target if isinstance(self.target, str) else "|".join(map(str, self.target))
        return f"<{'图' if self.kind == 'img' else '文'}:{what}>"


def OCR(target: Any, *, roi: Optional[tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None, offset: Optional[tuple[int, int, int, int]] = None,
        point: Optional[tuple[int, int]] = None, delay: int = 0,
        wait_freezes: Optional[int] = None, desc: str = "",
        index: int = 0) -> Cand:
    """文字识别候选项。``target`` 可以是词，也可以是词表（任一命中即可）。"""
    return Cand("ocr", target, roi, threshold, offset, point, delay, wait_freezes, desc,
                index=index)


def IMG(target: Any, *, roi: Optional[tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None, offset: Optional[tuple[int, int, int, int]] = None,
        point: Optional[tuple[int, int]] = None, delay: int = 0,
        wait_freezes: Optional[int] = None, desc: str = "",
        green_mask: bool = False, index: int = 0, method: int = 5) -> Cand:
    """模板匹配候选项。``target`` 是图库里的相对路径，如 ``"Mainpage/mail.png"``。"""
    return Cand("img", target, roi, threshold, offset, point, delay, wait_freezes, desc,
                green_mask, index, method)


def ANY(*cands: Cand) -> tuple[Cand, ...]:
    """把若干候选项打包，纯粹为了在任务代码里读起来顺一点。"""
    return cands


#: 「步骤」= 要么是一个候选项（``OCR(...)``/``IMG(...)``），要么是一个
#: ``def 某步(ctx) -> bool`` 的普通函数。把递归的 ``next`` 链条直接写成函数
#: 调用，就能一个节点一个节点地对照旧 JSON，不丢任何分支。
Step = Union[Cand, Callable[["TaskContext"], bool]]


#: 「已经站在游戏主界面」的标记（Startup/11.png 只会出现在右上角那一块）。
MAIN_PAGE = IMG("Startup/11.png", roi=(906, 340, 170, 205), desc="主界面标记")

#: 通用的「关掉当前面板 / 退出当前界面」按钮（旧 pipeline 里那个被 6 个文件共用的
#: ``Quit`` 节点，识别的是 Collect/06.png）。它以前散落在每个 json 的 ``next`` 里，
#: 现在只在这里定义一次。
QUIT = IMG("Collect/06.png", desc="关掉当前面板")

#: 开屏读条时底部会轮播出现的词，出现任意一个就说明还在加载。
LOADING_WORDS = ("服务", "同步", "更新", "解压", "检测", "资源", "配置")

#: 各任务都会遇到的通用干扰：登录提示、养成特惠弹窗、误入其它界面。
#:
#: 旧 pipeline 是靠往**每个**节点的 ``next`` 里塞
#: ``[JumpBack]Exception-handling-*`` 来兜这些的，节点一多就极易漏。搬到 Python
#: 之后它就是一个普通函数，在耗时循环里顺手 ``handle_exceptions(ctx)`` 即可。
EXCEPTION_CANDS: tuple[Cand, ...] = (
    OCR("今日登录不再提示", roi=(115, 590, 277, 100), point=(1160, 130), delay=2000,
        desc="关掉「今日登录不再提示」"),
    OCR("养成特惠", point=(1160, 130), delay=2000, desc="关掉养成特惠弹窗（第一下）"),
    OCR("养成特惠", point=(1190, 120), delay=2000, desc="关掉养成特惠弹窗（补一下）"),
    IMG("Collect/06.png", roi=(0, 0, 500, 300), delay=2000, desc="误入器者征集，退出"),
    IMG("Startup/10.png", roi=(0, 0, 500, 300), delay=2000, desc="误入某个界面，回主页"),
)


def handle_exceptions(ctx: "TaskContext", *, rounds: int = 2) -> bool:
    """处理常见的干扰弹窗 / 误入界面，返回是否动过手。

    没命中就立刻返回 ``False``，开销只是一次识别；所以在长循环里可以放心多调。
    """
    did = False
    for _ in range(max(1, rounds)):
        if ctx.tap_first(*EXCEPTION_CANDS) is None:
            break
        did = True
    return did


# --------------------------------------------------------------------- 运行上下文


class TaskContext:
    """传给任务函数的上下文。

    任务函数只应该通过这个对象与外界打交道，这样它才能被单独测试、
    也才能在 GUI 里被单跑。
    """

    def __init__(
        self,
        *,
        screen: Screen,
        settings: Optional[dict[str, Any]] = None,
        spec: Optional[TaskSpec] = None,
        cancel: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.screen = screen
        self.settings: dict[str, Any] = dict(settings or {})
        self.spec = spec
        self.tasker = getattr(screen, "_tasker", None)
        self.controller = getattr(screen, "_controller", None)
        self.log = get_logger(spec.key if spec else "任务")
        self._cancel = cancel or (lambda: False)
        self._started = time.monotonic()

    # ------------------------------------------------------------- 中断

    @property
    def cancelled(self) -> bool:
        return bool(self._cancel())

    def check_cancel(self) -> None:
        """在耗时循环里调用；被中断时抛出 ``TaskCancelled``。"""
        if self.cancelled:
            raise TaskCancelled()

    # ------------------------------------------------------------- 参数

    def option(self, key: str, default: Any = None) -> Any:
        """取一个选项的最终取值（已按声明类型收敛）。"""
        if self.spec is not None:
            declared = self.spec.option(key)
            if declared is not None:
                raw = self.settings.get(key, declared.default)
                return declared.coerce(raw)
        return self.settings.get(key, default)

    def text(self, key: str, default: str = "") -> str:
        value = self.option(key, default)
        return "" if value is None else str(value)

    def flag(self, key: str, default: bool = False) -> bool:
        return bool(self.option(key, default))

    def number(self, key: str, default: int = 0) -> int:
        try:
            return int(self.option(key, default))
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------- 输出

    def emit(self, event: str, *args: Any) -> None:
        events.emit(event, *args)

    def step(self, text: str) -> None:
        """汇报当前在做什么（GUI 会显示）。"""
        self.log.info(text)
        self.emit(Events.STEP, text)

    # ------------------------------------------------------------- 常用组合

    def find_then_click(
        self,
        target: Any,
        *,
        kind: str = "template",
        roi: Optional[tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        offset: Optional[tuple[int, int, int, int]] = None,
        delay: int = 0,
        wait_freezes: Optional[int] = None,
        desc: str = "",
    ) -> bool:
        """识别到就点它。最常用的一步，把三种分支收敛成一行。"""
        self.check_cancel()
        if kind == "template":
            match = self.screen.find(
                target, roi=roi, threshold=0.7 if threshold is None else threshold
            )
        else:
            match = self.screen.text(
                target, roi=roi, threshold=0.3 if threshold is None else threshold
            )
        if not match:
            return False
        self.screen.click(match, offset=offset, delay=delay, wait_freezes=wait_freezes, desc=desc)
        return True

    # ------------------------------------------------------------- 候选项玩法

    def look(self, cand: Cand) -> Optional[Match]:
        """只看一眼，不点。命中返回 ``Match``，没命中返回 ``None``。"""
        self.check_cancel()
        if cand.kind == "img":
            return self.screen.find(
                cand.target,
                roi=cand.roi,
                threshold=0.7 if cand.threshold is None else cand.threshold,
                green_mask=cand.green_mask,
                index=cand.index,
                method=cand.method,
            )
        return self.screen.text(
            cand.target,
            roi=cand.roi,
            threshold=0.3 if cand.threshold is None else cand.threshold,
            index=cand.index,
        )

    def tap(self, cand: Cand) -> bool:
        """看一眼，命中就点它。返回是否点到。"""
        match = self.look(cand)
        if not match:
            return False
        where: Any = cand.point if cand.point is not None else match
        self.screen.click(
            where,
            offset=cand.offset,
            delay=cand.delay,
            wait_freezes=cand.wait_freezes,
            desc=cand.desc,
        )
        return True

    def _do(self, step: "Step") -> bool:
        """执行一个「步骤」：候选项就点它，可调用对象就调它。"""
        if isinstance(step, Cand):
            return self.tap(step)
        if callable(step):
            return bool(step(self))
        raise TypeError(f"不认识的步骤：{step!r}（要么是 Cand，要么是 def 步骤(ctx) -> bool）")

    def tap_first(self, *steps: "Step") -> Optional["Step"]:
        """按顺序试每个步骤，做到第一个成功的。返回成功的那个（都没成返回 None）。"""
        for step in steps:
            if self._do(step):
                if isinstance(step, Cand) and step.desc:
                    self.log.debug("命中 %s", step.desc)
                return step
        return None

    def scan(
        self,
        *steps: "Step",
        timeout: int = 20000,
        interval: int = 400,
        desc: str = "",
    ) -> Optional["Step"]:
        """反复扫整张步骤表，直到有一个做成了，或者超时。

        这是旧 pipeline ``next`` 列表的直接对应物：列表从头到尾试一遍，全不中
        就歇一下再从头试，直到该节点的 ``timeout`` 到期。

        ``steps`` 里既可以放候选项（``OCR(...)`` / ``IMG(...)`` / ``QUIT``），
        也可以放 ``def 某步(ctx) -> bool`` 这样的普通函数 —— 后者让递归的
        ``next`` 链条可以直接写成函数调用，从而**逐节点**对照旧 JSON。

        Returns:
            做成了的那个步骤；超时返回 ``None``。
        """
        deadline = time.monotonic() + timeout / 1000.0
        while True:
            self.check_cancel()
            hit = self.tap_first(*steps)
            if hit is not None:
                return hit
            if time.monotonic() >= deadline:
                if desc:
                    self.log.warning("%s：扫了 %.1fs 没有任何命中", desc, timeout / 1000.0)
                return None
            time.sleep(interval / 1000.0)

    # ------------------------------------------------------------- 通用小动作

    def back(self, *, delay: int = 800) -> None:
        """按一次返回键（Android KEYCODE_BACK）。"""
        self.screen.press_key(4, delay=delay)

    def retry(
        self,
        action: Callable[[], bool],
        *,
        timeout: int = 60000,
        interval: int = 500,
        desc: str = "",
    ) -> bool:
        """反复尝试 ``action`` 直到成功或超时。

        ``action`` 内部通常就是「截图 + 识别 + 点击」。
        """
        deadline = time.monotonic() + timeout / 1000.0
        attempt = 0
        while True:
            self.check_cancel()
            attempt += 1
            try:
                if action():
                    if desc:
                        self.log.debug("%s 第 %d 次尝试成功", desc, attempt)
                    return True
            except TaskCancelled:
                raise
            except Exception:
                self.log.debug("第 %d 次尝试异常", attempt, exc_info=True)
            if time.monotonic() >= deadline:
                if desc:
                    self.log.warning("%s 超时（%d ms，尝试 %d 次）", desc, timeout, attempt)
                return False
            time.sleep(interval / 1000.0)

    def wait_for(self, matcher: Callable[[], bool], *, timeout: int = 20000, interval: int = 400) -> bool:
        """等待某个画面条件成立。"""
        return self.retry(matcher, timeout=timeout, interval=interval)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started


# --------------------------------------------------------------------- 执行


@dataclass
class TaskResult:
    key: str
    name: str
    success: bool = False
    skipped: bool = False
    cancelled: bool = False
    error: str = ""
    elapsed: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "success": self.success,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
            "error": self.error,
            "elapsed": round(self.elapsed, 2),
        }


def _settings_for(key: str, settings: Optional[dict[str, Any]]) -> dict[str, Any]:
    """挑出属于某个任务的选项取值。

    ``settings`` 支持两种写法：

    * ``{"任务key": {"选项": 值}}`` —— GUI 用这种，每个任务的参数互不干扰；
    * ``{"选项": 值}`` —— 命令行图省事时用这种，原样交给每个任务。

    判据很简单：如果 ``settings`` 里有这个任务 key、且它的值是个 dict，
    就按第二种解读，否则当成扁平表。
    """
    if not settings:
        return {}
    scoped = settings.get(key)
    if isinstance(scoped, dict):
        return dict(scoped)
    return {k: v for k, v in settings.items() if not isinstance(v, dict)}


class TaskRunner:
    """按顺序执行若干个注册过的任务。"""

    def __init__(self, screen: Screen, *, cancel: Optional[Callable[[], bool]] = None) -> None:
        self.screen = screen
        self._cancel = cancel or (lambda: False)
        self.results: list[TaskResult] = []

    def run_one(
        self,
        spec: TaskSpec,
        settings: Optional[dict[str, Any]] = None,
    ) -> TaskResult:
        result = TaskResult(key=spec.key, name=spec.label)
        context = TaskContext(
            screen=self.screen, settings=_settings_for(spec.key, settings),
            spec=spec, cancel=self._cancel,
        )
        started = time.monotonic()
        logger.info("▶ 开始任务：%s", spec.label)
        events.emit(Events.TASK_START, spec.key, spec.label)
        try:
            ok = spec.func(context)
            result.success = bool(ok)
            if not ok:
                result.error = "任务返回 False（未按预期完成）"
                logger.warning("✗ 任务未完成：%s", spec.label)
            else:
                logger.info("✓ 完成任务：%s", spec.label)
        except TaskCancelled:
            result.cancelled = True
            result.error = "已中断"
            logger.warning("■ 任务被中断：%s", spec.label)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            logger.error("✗ 任务异常：%s\n%s", spec.label, traceback.format_exc())
        finally:
            result.elapsed = time.monotonic() - started
            events.emit(Events.TASK_END, spec.key, result.success, result.elapsed)
        return result

    def run(
        self,
        keys: Sequence[str],
        settings: Optional[dict[str, Any]] = None,
        *,
        stop_on_error: bool = False,
    ) -> list[TaskResult]:
        """依次执行 ``keys`` 里的任务。整体结束会发 ``Events.FINISHED``。"""
        self.results = []
        try:
            for key in keys:
                spec = get_task(key)
                if spec is None:
                    logger.warning("忽略未注册的任务：%s", key)
                    self.results.append(
                        TaskResult(key=key, name=key, error="未注册的任务")
                    )
                    continue
                if self._cancel():
                    self.results.append(
                        TaskResult(key=key, name=spec.label, cancelled=True, error="已中断")
                    )
                    break
                result = self.run_one(spec, settings)
                self.results.append(result)
                if stop_on_error and not result.success and not result.cancelled:
                    logger.warning("因 %s 失败而中止后续任务", spec.label)
                    break
        finally:
            events.emit(Events.FINISHED, [r.as_dict() for r in self.results])
        return self.results
