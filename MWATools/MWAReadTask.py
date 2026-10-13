"""interface.json 任务目录读取器（ProjectInterface v2）。

这个文件原本是「从 interface.json 里读任务清单」的那一层，新架构里它
**重新有了正式职责**：作为 Python 任务注册表之外的**第二份目录来源**。

为什么留着旧目录：
* 已经写在 ``interface.json`` 里的 19 个任务 / 19 个 option 是现成的、
  带中文名字和中文选项名的资产，不必在 Python 里再抄一遍；
* 还没迁移成 Python 模块的任务，靠这份目录 + ``MWATaskPipeline`` 就能
  继续用旧 pipeline 跑起来，迁移期间功能不回退。

与旧版的区别：
* 旧版 ``from MWATools.MWAInterface import interface`` 是**模块级全局**，
  导入即读文件、且路径相对 CWD；现在改成构造时惰性读取，路径由
  ``MWAPaths`` 解析，可从任意工作目录运行。
* 旧版 ``self.options`` 恒为空 list、``get_task_option_entry()`` 名不副实
  （返回的是 option 键名列表却不是 entry）。现在 ``self.options`` 是真正的
  option 定义表，旧方法签名与返回值保持不变以免破坏既有调用。
* 每个取值失败都返回 ``None``（旧版隐式返回 None 或抛 AttributeError）。

典型用法::

    reader = MWAReadTaskClass()
    reader.tasks                      # ['启动', '器者征集', ...]
    reader.get_task_entry('启动')      # 'Start'
    reader.get_task_options('演训')    # ['选择关卡-演训', '打哪个-演训', '选择战斗次数']
    reader.case_names('选择战斗次数')   # ['打一次（速通没解锁专用）', ...]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .MWAInterface import ProjectInterface, load_interface
from .MWALogging import get_logger

__all__ = ["MWAReadTaskClass"]

logger = get_logger("任务目录")


class MWAReadTaskClass:
    """把 interface.json 的 ``task`` / ``option`` 两张表读成好用的 Python 结构。"""

    def __init__(
        self,
        path: Optional[Path | str] = None,
        *,
        interface: Optional[ProjectInterface] = None,
    ) -> None:
        if interface is not None:
            self.interface = interface
        else:
            self.interface = load_interface(path)

        self.data: dict[str, Any] = self.interface.data

        # 旧版字段，语义不变 -------------------------------------------------
        # 用来显示任务列表
        self.tasks: list[str] = [str(t.get("name", "")) for t in self.interface.tasks() if t.get("name")]
        # 实际需要用到的任务名 -> 任务定义
        self.tasknames: dict[str, dict[str, Any]] = {
            str(t["name"]): t for t in self.interface.tasks() if t.get("name")
        }
        # 旧版这里是空 list，现在填真正的 option 定义表
        self.options: dict[str, dict[str, Any]] = self.interface.options()
        # 旧版语义：option 键名列表
        self.option_entry: list[str] = list(self.options)

        self.entry: Optional[str] = None

    # ------------------------------------------------------------------ 元信息

    @property
    def path(self) -> Optional[Path]:
        return self.interface.path

    @property
    def name(self) -> str:
        return self.interface.name

    @property
    def version(self) -> str:
        return self.interface.version

    @property
    def base_dir(self) -> Path:
        """interface.json 所在目录 —— 所有相对路径（含 resource[].path）的基准。"""
        return self.interface.base_dir

    def __bool__(self) -> bool:
        return bool(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)

    def __repr__(self) -> str:
        return f"<MWAReadTaskClass {self.name!r} tasks={len(self.tasks)} options={len(self.options)}>"

    # ------------------------------------------------------------------ 旧接口

    def get_task_entry(self, task_name: str) -> Optional[str]:
        """取任务对应的 pipeline 起点节点名。"""
        task = self.tasknames.get(task_name)
        if task is None:
            logger.debug("任务 %r 不在 interface.json 里", task_name)
            return None
        self.entry = task.get("entry")
        return self.entry

    def get_task_options(self, task_name: str) -> Optional[list[str]]:
        """取任务引用的 option 键名列表（顺序就是 UI 顺序，也是合并优先级顺序）。"""
        task = self.tasknames.get(task_name)
        if task is None or "option" not in task:
            return None
        value = task.get("option")
        if not isinstance(value, list):
            return None
        self.options_used = list(value)
        return self.options_used

    def get_task_option_entry(self, options: Optional[list[str]] = None) -> list[str]:
        """返回全部 option 的键名。

        旧版名字容易误解（它返回的从来不是 entry），但为了兼容既有调用，
        签名与返回值保持原样；要拿定义请用 :meth:`get_option` / :attr:`options`。
        """
        self.option_entry = [name for name in (options if options is not None else self.options.keys())]
        return self.option_entry

    # ------------------------------------------------------------------ 任务定义

    def get_task(self, task_name: str) -> Optional[dict[str, Any]]:
        return self.tasknames.get(task_name)

    def get_label(self, task_name: str) -> str:
        """任务的显示名：``label`` 优先，缺失时退回 ``name``。"""
        task = self.tasknames.get(task_name) or {}
        return str(task.get("label") or task_name)

    def describe_task(self, task_name: str) -> str:
        task = self.tasknames.get(task_name)
        if task is None:
            return f"{task_name}（不存在）"
        return str(task.get("description") or "")

    def task_options(self, task_name: str) -> list[str]:
        """:meth:`get_task_options` 的「永不返回 None」版本。"""
        return self.get_task_options(task_name) or []

    # ------------------------------------------------------------------ option 定义

    def get_option(self, option_key: str) -> Optional[dict[str, Any]]:
        return self.options.get(option_key)

    def option_type(self, option_key: str) -> str:
        """``select`` / ``checkbox`` / ``input`` / ``switch`` / ``hotkey``。"""
        option = self.options.get(option_key) or {}
        return str(option.get("type") or "select")

    def get_cases(self, option_key: str) -> list[dict[str, Any]]:
        option = self.options.get(option_key) or {}
        cases = option.get("cases", [])
        return [c for c in cases if isinstance(c, dict)] if isinstance(cases, list) else []

    def case(self, option_key: str, case_name: str) -> Optional[dict[str, Any]]:
        for item in self.get_cases(option_key):
            if item.get("name") == case_name:
                return item
        return None

    def case_names(self, option_key: str) -> list[str]:
        return [str(c.get("name", "")) for c in self.get_cases(option_key) if c.get("name")]

    def case_labels(self, option_key: str) -> list[str]:
        return [str(c.get("label") or c.get("name") or "") for c in self.get_cases(option_key)]

    def case_by_label(self, option_key: str, label: str) -> Optional[dict[str, Any]]:
        """按显示名（label）反查 case —— CLI/GUI 上用户看到的往往是 label。"""
        for item in self.get_cases(option_key):
            if str(item.get("label") or item.get("name") or "") == label:
                return item
        return None

    def default_case(self, option_key: str) -> Optional[str]:
        option = self.options.get(option_key) or {}
        value = option.get("default_case")
        if isinstance(value, str) and value:
            return value
        names = self.case_names(option_key)
        return names[0] if names else None

    def option_labels(self) -> list[str]:
        """全部 option 的显示名（``label`` 优先）。"""
        return [str(o.get("label") or key) for key, o in self.options.items()]

    # ------------------------------------------------------------------ 适用性

    def is_option_applicable(
        self,
        option_key: str,
        controller: Optional[str] = None,
        resource: Optional[str] = None,
    ) -> bool:
        """ProjectInterface v2：option 可用 ``controller`` / ``resource`` 限定适用范围。

        当前 interface.json 里一个都没用，但迁移后的任务可能会用，所以照规范实现：
        声明了限定、且当前选择不在其中时，该 option 整体不产生 override。
        """
        option = self.options.get(option_key)
        if not option:
            return False
        if controller is not None:
            allowed = option.get("controller")
            if isinstance(allowed, list) and allowed and controller not in allowed:
                return False
        if resource is not None:
            allowed = option.get("resource")
            if isinstance(allowed, list) and allowed and resource not in allowed:
                return False
        return True

    # ------------------------------------------------------------------ 汇总

    def describe(self) -> str:
        """一段可直接打印的目录摘要。"""
        lines = [self.interface.describe()]
        lines.append(f"  controller: {[c.get('name') for c in self.interface.controllers()]}")
        lines.append(f"  resource:   {self.interface.bundle_paths()}")
        for task_name in self.tasks:
            entry = self.get_task_entry(task_name)
            options = self.task_options(task_name)
            lines.append(f"  · {task_name} -> {entry}  选项 {len(options)} 个 {options if options else ''}")
        return "\n".join(lines)


def read_tasks(path: Optional[Path | str] = None) -> MWAReadTaskClass:
    """便捷函数：读一份 interface.json 的任务目录。"""
    return MWAReadTaskClass(path)


if __name__ == "__main__":
    from .MWALogging import setup_logging

    setup_logging()
    reader = MWAReadTaskClass()
    print(reader.describe())
    for task_name in reader.tasks:
        for option_key in reader.task_options(task_name):
            print(f"  {task_name} / {option_key} ({reader.option_type(option_key)})")
            for case in reader.get_cases(option_key):
                override = case.get("pipeline_override") or {}
                print(f"      - {case.get('name')}  →  {list(override)}")
