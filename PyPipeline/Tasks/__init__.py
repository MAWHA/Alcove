"""任务模块包。

每个游戏功能一个模块，模块内用 ``@task(...)`` 声明自己。
本包在 ``load_all()`` 时把同目录下所有模块都 import 一遍 —— 导入即注册。

**互不干扰**是这里的硬要求：任何一个模块 import 失败或语法错误，
只会让它自己缺席任务列表，其余模块照常加载、照常运行。

除了本目录的 Python 模块，``load_all()`` 还会做第二步：把 ``interface.json``
里**还没有 Python 实现**的任务注册成「旧流水线任务」（见
``MWATools.MWATask.register_legacy_tasks``）。这样迁移可以一个一个来，
没迁的那些照旧能用，整体功能不会出现空窗期。
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from MWATools.MWALogging import get_logger

logger = get_logger("任务包")

__all__ = ["load_all", "loaded_modules", "legacy_keys"]

_loaded: list[str] = []
_legacy: list[str] = []


def load_all(force: bool = False) -> list[str]:
    """导入本目录下所有任务模块，并补齐旧流水线任务，返回成功导入的模块名列表。"""
    global _loaded, _legacy
    if _loaded and not force:
        return _loaded

    imported: list[str] = []
    skipped: list[str] = []
    here = Path(__file__).resolve().parent

    for info in pkgutil.iter_modules([str(here)]):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__name__}.{info.name}")
            imported.append(info.name)
        except Exception as exc:
            # 单个模块坏掉不影响其它模块
            skipped.append(info.name)
            logger.error("任务模块 %s 导入失败，已跳过：%s", info.name, exc, exc_info=True)

    if skipped:
        logger.warning("有 %d 个任务模块未能加载：%s", len(skipped), ", ".join(skipped))
    logger.info("已加载 %d 个任务模块", len(imported))
    _loaded = imported

    # 第二步：把 interface.json 里还没迁过来的任务接上旧流水线
    try:
        from MWATools.MWATask import legacy_task_keys, register_legacy_tasks

        register_legacy_tasks()
        _legacy = legacy_task_keys()
    except Exception as exc:  # noqa: BLE001 - 读不到 interface.json 也不该让界面起不来
        logger.error("注册旧流水线任务失败：%s", exc, exc_info=True)
        _legacy = []

    return imported


def loaded_modules() -> list[str]:
    return list(_loaded)


def legacy_keys() -> list[str]:
    """当前还在走旧流水线的任务 key（迁移进度就看这个列表在变短）。"""
    return list(_legacy)
