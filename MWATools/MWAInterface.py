"""interface.json（ProjectInterface v2）读取器 —— 仅作兼容与迁移参考。

**新架构不在运行时依赖它。** 任务清单、显示名、选项都改由 Python 侧的
``@task(...)`` 注册表描述（见 ``MWATools/MWATask.py``），
所以这个文件的角色从「配置来源」降级为「迁移参考 + 资源路径来源」。

保留它的两个理由：
1. ``resource[].path`` 声明了用哪套资源包，路径语义（相对 interface.json 目录）
   还是要按 ProjectInterface v2 的规范来解析；
2. 迁移旧任务时需要对照旧的 task/option 名称。

旧版在这里做了三件不该做的事，已全部去掉：
* 模块导入时就 ``os.walk`` 整个项目并把结果写进 ``config.json``；
* 把 ``interface`` 做成模块级全局变量（导入即产生副作用）；
* 用 ``../config.json`` 这种相对 CWD 的路径。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .MWALogging import get_logger
from .MWAPaths import interface_path

__all__ = ["ProjectInterface", "load_interface", "interface"]

logger = get_logger("接口")


@dataclass
class ProjectInterface:
    """interface.json 的轻量视图。"""

    path: Optional[Path] = None
    data: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ 基本项

    @property
    def name(self) -> str:
        return str(self.data.get("name", ""))

    @property
    def version(self) -> str:
        return str(self.data.get("version", ""))

    @property
    def interface_version(self) -> int:
        try:
            return int(self.data.get("interface_version", 0))
        except (TypeError, ValueError):
            return 0

    @property
    def base_dir(self) -> Path:
        """interface.json 所在目录 —— 所有相对路径的基准。"""
        if self.path is not None:
            return self.path.parent
        return Path.cwd()

    # ------------------------------------------------------------------ 列表

    def controllers(self) -> list[dict[str, Any]]:
        value = self.data.get("controller", [])
        return list(value) if isinstance(value, list) else []

    def resources(self) -> list[dict[str, Any]]:
        value = self.data.get("resource", [])
        return list(value) if isinstance(value, list) else []

    def tasks(self) -> list[dict[str, Any]]:
        value = self.data.get("task", [])
        return list(value) if isinstance(value, list) else []

    def options(self) -> dict[str, dict[str, Any]]:
        value = self.data.get("option", {})
        return dict(value) if isinstance(value, dict) else {}

    # ------------------------------------------------------------------ 资源包

    def bundle_paths(self, resource_name: Optional[str] = None) -> list[Path]:
        """解析 ``resource[].path`` 为绝对路径。

        ProjectInterface v2 的路径语义：**相对 interface.json 所在目录**，
        而不是相对当前工作目录 —— 这正是旧版 ``MWAResource`` 写死
        ``"./assets/resource_picli/base"`` 埋下的坑。
        """
        out: list[Path] = []
        for entry in self.resources():
            if resource_name is not None and entry.get("name") != resource_name:
                continue
            raw = entry.get("path", [])
            if isinstance(raw, str):
                raw = [raw]
            for item in raw:
                if not isinstance(item, str) or not item:
                    continue
                candidate = Path(item)
                if not candidate.is_absolute():
                    candidate = self.base_dir / candidate
                out.append(candidate.resolve())
        return out

    # ------------------------------------------------------------------ 迁移参考

    def task_names(self) -> list[str]:
        return [str(t.get("name", "")) for t in self.tasks()]

    def describe(self) -> str:
        lines = [
            f"interface.json: {self.path}",
            f"  name={self.name!r} version={self.version!r} interface_version={self.interface_version}",
            f"  controller: {[c.get('name') for c in self.controllers()]}",
            f"  resource:   {[r.get('name') for r in self.resources()]}",
            f"  task:       {len(self.tasks())} 个",
            f"  option:     {len(self.options())} 个",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ 映射兼容

    #: 旧版 ``interface`` 是一个模块级 dict（``interface["controller"][0]``），
    #: 上游的 ``MWATools/adbcs.py``、``MWATools/cs.py``、``test.py`` 仍这么用。
    #: 这里补一组只读的映射协议，让那些调用方不必改动。

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def load_interface(path: Optional[Path] = None) -> ProjectInterface:
    """读取 interface.json。找不到或解析失败时返回一个空对象并在日志里说明。"""
    if path is None:
        try:
            path = interface_path(create_if_missing=False)
        except Exception:
            path = None

    if path is None or not Path(path).is_file():
        logger.warning("未找到 interface.json，将只使用 Python 侧的任务注册表")
        return ProjectInterface()

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("读取 interface.json 失败：%s", exc)
        return ProjectInterface(path=Path(path))

    if not isinstance(data, dict):
        logger.error("interface.json 顶层不是对象")
        return ProjectInterface(path=Path(path))

    return ProjectInterface(path=Path(path), data=data)


_interface: Optional[ProjectInterface] = None


def __getattr__(name: str) -> Any:
    """按需提供模块级 ``interface``（PEP 562）。

    旧版在导入时就实例化它并顺手写 ``config.json``，那是导入即产生副作用。
    新写法只在真的有人 ``from MWATools.MWAInterface import interface`` 时才读一次，
    而且读失败也只是返回空对象 + 一条 warning，不会炸掉导入方。
    """
    global _interface
    if name == "interface":
        if _interface is None:
            _interface = load_interface()
        return _interface
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    from .MWALogging import setup_logging

    setup_logging()
    print(load_interface().describe())
