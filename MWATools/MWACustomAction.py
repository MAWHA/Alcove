"""自定义动作 / 自定义识别的注册表。

旧版这个文件是空的（0 字节）——「自定义动作」这一步当时靠
``@MWAResource.resource.custom_action("StartApp")`` 在 ``main.py`` 里硬写。
随着要跑的任务变多（``PyPipeline/CustomActions/`` 下会不止一个动作），
散在入口文件里就不合适了，于是把这一层收进这里：

* **登记**：``register("名字", 动作类或实例)``，或 ``@actions.action("名字")`` 装饰器；
* **自动发现**：扫描 ``PyPipeline/CustomActions/`` 与
  ``PyPipeline/CustomRecognitions/`` 下的模块，把其中继承自
  ``CustomAction`` / ``CustomRecognition`` 的类按「类名或 ``ACTION_NAME``」
  登记进来 —— 所以以后新增一个自定义动作，只要往那两个目录里丢一个 .py
  文件就行，不用改这里，也不用改 ``main.py``；
* **挂载**：``attach(resource)`` 把登记好的全部注册到 maa 的 ``Resource`` 上。

自定义动作跑在 maafw 的原生线程里（实测线程名 ``Dummy-1``），
在它内部 ``post_screencap().wait()`` 不会死锁；但**不能**在里面 wait 同一
tasker 的 task job，那才会死锁。详见 ``MWAScreen`` 与
``assets/resource/data/app.py`` 的说明。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .MWALogging import get_logger
from .MWAPaths import PROJECT_ROOT

__all__ = [
    "MWACustomActionClass",
    "actions",
    "discover",
    "register_all",
    "ACTION_DIR",
    "RECOGNITION_DIR",
]

logger = get_logger("自定义动作")

#: 自定义动作放这里 —— 一个动作一个 .py，丢进去就会被自动发现。
ACTION_DIR = PROJECT_ROOT / "PyPipeline" / "CustomActions"
#: 自定义识别放这里（上游现有 ``CustomRecos/PopUpRecognition.py``）。
#: 目录名跟随上游的既成事实 ``CustomRecos``，**不是** ``CustomRecognitions``。
#: 早先这里写成后者，后果是 ``PopUpRecognition`` 从来没被发现过 —— 扫的是一个
#: 不存在的目录，``_scan`` 只打一行 debug 就跳过去了，静默失效。
RECOGNITION_DIR = PROJECT_ROOT / "PyPipeline" / "CustomRecos"


def _ensure_importable() -> None:
    """保证 ``PyPipeline`` 能被 import（脚本从别处运行时 sys.path 里可能没有项目根）。"""
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


class MWACustomActionClass:
    """一张「名字 -> 实例」表，外加把表挂到 maa Resource 上的能力。"""

    def __init__(
        self,
        *,
        action_dir: Path = ACTION_DIR,
        recognition_dir: Path = RECOGNITION_DIR,
    ) -> None:
        self.action_dir = Path(action_dir)
        self.recognition_dir = Path(recognition_dir)
        self._actions: dict[str, Any] = {}
        self._recognitions: dict[str, Any] = {}
        self._discovered: bool = False

    # ================================================================== 登记

    @staticmethod
    def _instantiate(target: Any) -> Any:
        """接受类或实例；是类就无参实例化。"""
        if inspect.isclass(target):
            return target()
        return target

    def register(self, name: str, action: Any, *, replace: bool = False) -> Any:
        """登记一个自定义动作。``name`` 必须与 pipeline 里的 ``custom_action`` 一致。"""
        if not name:
            raise ValueError("自定义动作名不能为空")
        if name in self._actions and not replace:
            logger.debug("自定义动作 %r 已登记，跳过", name)
            return self._actions[name]
        instance = self._instantiate(action)
        self._actions[name] = instance
        logger.debug("登记自定义动作 %r -> %s", name, type(instance).__name__)
        return instance

    def register_recognition(self, name: str, recognition: Any, *, replace: bool = False) -> Any:
        """登记一个自定义识别（与 pipeline 里的 ``custom_recognition`` 一致）。"""
        if not name:
            raise ValueError("自定义识别名不能为空")
        if name in self._recognitions and not replace:
            logger.debug("自定义识别 %r 已登记，跳过", name)
            return self._recognitions[name]
        instance = self._instantiate(recognition)
        self._recognitions[name] = instance
        logger.debug("登记自定义识别 %r -> %s", name, type(instance).__name__)
        return instance

    def action(self, name: str) -> Callable[[Any], Any]:
        """装饰器：``@actions.action("MyAct")``。返回被装饰的类本身。"""

        def decorator(cls: Any) -> Any:
            self.register(name, cls)
            return cls

        return decorator

    def recognition(self, name: str) -> Callable[[Any], Any]:
        """装饰器：``@actions.recognition("event_select")``。"""

        def decorator(cls: Any) -> Any:
            self.register_recognition(name, cls)
            return cls

        return decorator

    # ================================================================== 查询

    def get(self, name: str) -> Optional[Any]:
        return self._actions.get(name)

    def get_recognition(self, name: str) -> Optional[Any]:
        return self._recognitions.get(name)

    def names(self) -> list[str]:
        return sorted(self._actions)

    def recognition_names(self) -> list[str]:
        return sorted(self._recognitions)

    def __len__(self) -> int:
        return len(self._actions) + len(self._recognitions)

    def __contains__(self, name: object) -> bool:
        return name in self._actions or name in self._recognitions

    def __repr__(self) -> str:
        return f"<MWACustomActionClass 动作 {len(self._actions)} 个、识别 {len(self._recognitions)} 个>"

    def clear(self) -> None:
        self._actions.clear()
        self._recognitions.clear()
        self._discovered = False

    # ================================================================== 自动发现

    def _package_of(self, directory: Path) -> Optional[str]:
        try:
            relative = directory.resolve().relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            logger.debug("%s 不在项目里，跳过自动发现", directory)
            return None
        return ".".join(relative.parts)

    def discover(
        self,
        *,
        action_dir: Optional[Path] = None,
        recognition_dir: Optional[Path] = None,
        force: bool = False,
    ) -> list[str]:
        """扫描两个目录，把自定义动作 / 识别类登记进来。返回新登记的名字。"""
        if self._discovered and not force:
            return []
        self._discovered = True

        _ensure_importable()

        try:
            from maa.custom_action import CustomAction
            from maa.custom_recognition import CustomRecognition
        except ImportError as exc:  # pragma: no cover - 只有没装 maafw 时才会走到
            logger.error("无法导入 maa，自定义动作不会被登记：%s", exc)
            return []

        added: list[str] = []
        added += self._scan(Path(action_dir or self.action_dir), CustomAction, self._actions, "自定义动作")
        added += self._scan(
            Path(recognition_dir or self.recognition_dir),
            CustomRecognition,
            self._recognitions,
            "自定义识别",
        )
        if added:
            logger.info("自动发现 %d 个自定义扩展：%s", len(added), added)
        return added

    def _scan(self, directory: Path, base: type, target: dict[str, Any], label: str) -> list[str]:
        if not directory.is_dir():
            logger.debug("%s 目录不存在，跳过：%s", label, directory)
            return []

        package = self._package_of(directory)
        if package is None:
            return []

        added: list[str] = []
        for info in pkgutil.iter_modules([str(directory)]):
            module_name = f"{package}.{info.name}"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001 - 单个模块坏掉不该拖垮其它模块
                logger.error("导入 %s 失败，已跳过：%s", module_name, exc)
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, base) or obj is base:
                    continue
                if obj.__module__ != module.__name__:
                    continue  # 只认本模块里定义的类，避免把 import 进来的基类也登记了

                name = str(getattr(obj, "ACTION_NAME", "") or getattr(obj, "RECOGNITION_NAME", "") or obj.__name__)
                if name in target:
                    continue
                try:
                    target[name] = self._instantiate(obj)
                except Exception as exc:  # noqa: BLE001
                    logger.error("实例化 %s.%s 失败：%s", module_name, obj.__name__, exc)
                    continue
                added.append(name)
                logger.debug("从 %s 发现%s %r", module_name, label, name)
        return added

    # ================================================================== 挂载

    def attach(self, resource: Any) -> tuple[int, int]:
        """把登记好的动作 / 识别注册到 maa 的 ``Resource`` 上。

        返回 ``(动作数, 识别数)``。重复注册（maa 会抛 ``RuntimeError``）视为已完成，
        这样同一个 Resource 被重复 attach 也不会炸。
        """
        if resource is None:
            logger.warning("resource 为空，无法挂载自定义扩展")
            return (0, 0)

        ok_actions = 0
        for name, instance in self._actions.items():
            try:
                resource.register_custom_action(name, instance)
                ok_actions += 1
            except RuntimeError as exc:
                logger.debug("自定义动作 %r 已在 maa 侧注册过：%s", name, exc)
                ok_actions += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("注册自定义动作 %r 失败：%s", name, exc)

        ok_recognitions = 0
        for name, instance in self._recognitions.items():
            try:
                resource.register_custom_recognition(name, instance)
                ok_recognitions += 1
            except RuntimeError as exc:
                logger.debug("自定义识别 %r 已在 maa 侧注册过：%s", name, exc)
                ok_recognitions += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("注册自定义识别 %r 失败：%s", name, exc)

        logger.info(
            "已挂载自定义扩展：动作 %d/%d，识别 %d/%d",
            ok_actions,
            len(self._actions),
            ok_recognitions,
            len(self._recognitions),
        )
        return (ok_actions, ok_recognitions)

    def detach(self, resource: Any) -> None:
        """从 Resource 上撤销本表登记的扩展。"""
        for name in self._actions:
            try:
                resource.unregister_custom_action(name)
            except Exception:  # noqa: BLE001
                pass
        for name in self._recognitions:
            try:
                resource.unregister_custom_recognition(name)
            except Exception:  # noqa: BLE001
                pass

    def describe(self) -> str:
        lines = [
            f"自定义动作（{len(self._actions)}）：{[*self.names()]}",
            f"自定义识别（{len(self._recognitions)}）：{[*self.recognition_names()]}",
            f"扫描目录：{self.action_dir} / {self.recognition_dir}",
        ]
        return "\n".join(lines)


#: 项目级单例 —— 其它模块 ``from .MWACustomAction import actions`` 即可共用一张表。
actions = MWACustomActionClass()


def discover(*, force: bool = False) -> list[str]:
    """便捷函数：对单例做一次自动发现。"""
    return actions.discover(force=force)


def register_all(resource: Any) -> tuple[int, int]:
    """便捷函数：先自动发现，再把单例里的扩展全部挂到 ``resource`` 上。"""
    actions.discover()
    return actions.attach(resource)


if __name__ == "__main__":
    from .MWALogging import setup_logging

    setup_logging()
    discover(force=True)
    print(actions.describe())
