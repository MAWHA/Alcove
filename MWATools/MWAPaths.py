"""路径解析。

两条设计原则：

1. **任何路径都不依赖当前工作目录（CWD）。**
   旧版 MWATools 里写死的 `./assets/resource_picli/base`、`../config.json` 这类相对路径，
   只要不是从仓库根启动就会静默失效，这是重写时首先要解决的问题。
2. **只读的东西和要写的东西分家。**
   打包成 exe 之后，代码和 assets 待在发行目录里（可能是 Program Files、可能被
   杀软盯着），而 config.json / logs / maafw 自身的工作目录必须可写 —— 而且不能
   放在 PyInstaller 的临时解压目录里，那个目录退出即删。

所以区分两个根：

``BUNDLE_ROOT``
    **只读**资源根：代码、``assets/``、``interface.json`` 都在它下面。
    源码运行时是仓库根；打包后是 PyInstaller 的 ``sys._MEIPASS``
    （onedir 模式下就是 exe 旁边的 ``_internal/``）。
``USER_ROOT``
    **可写**根：``config.json``、``logs/``、maa 的 option 目录写这里。
    源码运行时同样是仓库根（行为与改造前一致）；打包后是 **exe 所在目录**，
    若那里不可写（典型：装在 ``C:\\Program Files`` 下）则退回家目录的 ``.alcove/``。

``PROJECT_ROOT`` 保留旧名字，语义 = ``BUNDLE_ROOT``，避免改动调用方。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

__all__ = [
    "FROZEN",
    "BUNDLE_ROOT",
    "USER_ROOT",
    "PROJECT_ROOT",
    "ASSETS_DIR",
    "CONFIG_FILE",
    "LOG_DIR",
    "interface_path",
    "read_config",
    "write_config",
]

#: 是否运行在 PyInstaller 打包出来的可执行文件里。
FROZEN: bool = bool(getattr(sys, "frozen", False))
INTERFACE_NAME: str = "interface.json"


def _bundle_root() -> Path:
    """只读资源根。源码运行时 = 仓库根；打包后 = PyInstaller 解包目录。"""
    if FROZEN:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    # MWATools/MWAPaths.py -> MWATools/ -> 仓库根
    return Path(__file__).resolve().parent.parent


def _writable(directory: Path) -> bool:
    """真写一个临时文件来判断可写（Windows 上 ``os.access`` 不算数）。"""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".alcove_", suffix=".tmp"):
            pass
        return True
    except OSError:
        return False


def _user_root(bundle: Path) -> Path:
    """可写根。源码运行时就是仓库根；打包后优先 exe 所在目录。

    逐级退让：exe 旁边 → ``~/.alcove`` → 系统临时目录下的 ``Alcove`` →
    退回只读根（读还能用，写会失败但各调用点都已有 warning 兜底）。
    全程不抛异常：导入期炸掉的话连一句人话都打不出来。
    """
    if not FROZEN:
        return bundle
    exe_dir = Path(sys.executable).resolve().parent
    if _writable(exe_dir):
        return exe_dir
    for fallback in (
        _safe_home() / ".alcove",
        Path(tempfile.gettempdir()) / "Alcove",
    ):
        try:
            if _writable(fallback):
                return fallback
        except OSError:
            continue
    return bundle


def _safe_home() -> Path:
    """``Path.home()`` 在某些受限环境里会抛异常，这里兜住。"""
    try:
        return Path(os.path.expanduser("~"))
    except Exception:  # noqa: BLE001 - 拿不到家目录不是致命错误
        return Path(tempfile.gettempdir())


BUNDLE_ROOT: Path = _bundle_root()
USER_ROOT: Path = _user_root(BUNDLE_ROOT)
PROJECT_ROOT: Path = BUNDLE_ROOT  # 旧名字，等价于 BUNDLE_ROOT
ASSETS_DIR: Path = BUNDLE_ROOT / "assets"
CONFIG_FILE: Path = USER_ROOT / "config.json"
LOG_DIR: Path = USER_ROOT / "logs"


def read_config() -> dict:
    """读可写根下的 config.json；不存在或损坏时返回空 dict。"""
    import json

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(data: dict) -> None:
    """写回 config.json（缩进 4，保留中文）。"""
    import json

    CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )


def interface_path(create_if_missing: bool = True) -> Path:
    """定位 interface.json。

    查找顺序：
    1. config.json 里的 ``interface_path``（历史字段，可能指向别处的绝对路径）
    2. 项目内 ``interface.json``
    3. ``assets/interface.json``

    找到后把结果写回 config.json，方便用户直接看到当前用的是哪一份。
    """
    config = read_config()

    candidates: list[Path] = []
    raw = config.get("interface_path")
    if isinstance(raw, str) and raw.strip():
        candidates.append(Path(raw))
    candidates.append(PROJECT_ROOT / INTERFACE_NAME)
    candidates.append(ASSETS_DIR / INTERFACE_NAME)

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved.is_file():
            if str(resolved) != raw:
                config["interface_path"] = str(resolved)
                try:
                    write_config(config)
                except OSError:
                    pass  # 写不进去不影响运行
            return resolved

    if create_if_missing:
        raise FileNotFoundError(
            "找不到 interface.json，已尝试：\n  "
            + "\n  ".join(str(c) for c in candidates)
        )
    return candidates[-1]
