"""路径解析。

设计原则：**任何路径都不依赖当前工作目录（CWD）**。
旧版 MWATools 里写死的 `./assets/resource_picli/base`、`../config.json` 这类相对路径，
只要不是从仓库根启动就会静默失效，这是重写时首先要解决的问题。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "PROJECT_ROOT",
    "ASSETS_DIR",
    "CONFIG_FILE",
    "LOG_DIR",
    "interface_path",
    "read_config",
    "write_config",
]

# MWATools/MWAPaths.py -> MWATools/ -> 项目根
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
CONFIG_FILE: Path = PROJECT_ROOT / "config.json"
LOG_DIR: Path = PROJECT_ROOT / "logs"
INTERFACE_NAME: str = "interface.json"


def read_config() -> dict:
    """读项目根下的 config.json；不存在或损坏时返回空 dict。"""
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
