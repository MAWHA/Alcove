#!/usr/bin/env python3
"""打包收尾：删掉 flet 桌面端的重复副本，顺便报一下体积。

PyInstaller 打完包之后，``_internal/flet_desktop/app/`` 里通常有**两份**东西：

* 预置的压缩包（Windows 是 ``flet-windows.zip``）—— 运行时真正读的那一份，
  ``flet_desktop.ensure_client_cached()`` 只认它；
* 一棵解开的目录树 —— ``hook-flet.py`` 把 ``~/.flet/client/...`` 里的缓存目录
  顺手也塞了进来，几十 MB，运行时无人问津。

    python scripts/prune_dist.py                    # 处理 dist/Alcove
    python scripts/prune_dist.py --dist dist/Alcove
    python scripts/prune_dist.py --dry-run          # 只报告不删

删错了也没有灾难性后果：运行时发现压缩包在、解开的目录不在，就自己解压一次
（或者联网重下）。所以这个脚本是安全的瘦身步骤。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def human(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} GB"


def tree_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            pass
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prune_dist",
        description="删掉打包产物里重复的 flet 桌面端目录，并报告体积",
    )
    parser.add_argument("--dist", default=str(ROOT / "dist" / "Alcove"), help="onedir 产物目录")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不真的删")
    args = parser.parse_args(argv)

    dist = Path(args.dist).resolve()
    if not dist.is_dir():
        print(f"找不到产物目录：{dist}", file=sys.stderr)
        return 1

    before = tree_size(dist)
    app_dir = dist / "_internal" / "flet_desktop" / "app"
    if app_dir.is_dir():
        for child in sorted(app_dir.iterdir()):
            if not child.is_dir():
                continue
            size = tree_size(child)
            if args.dry_run:
                print(f"  [dry-run] 会删掉 {child}（{human(size)}）")
                continue
            shutil.rmtree(child)
            print(f"  已删掉冗余副本 {child.name}（省下 {human(size)}）")
        kept = [p.name for p in sorted(app_dir.iterdir())] if app_dir.is_dir() else []
        print(f"  flet_desktop/app 保留：{', '.join(kept) if kept else '（空！）'}")
        if not any(p.is_file() for p in app_dir.iterdir()):
            print(
                "  ！ 目录里没有压缩包了 —— 运行时只能联网下载桌面端客户端。"
                "先在打包前跑 `python scripts/fetch_flet_client.py`。",
                file=sys.stderr,
            )
    else:
        print(f"  （没有 {app_dir}，跳过 flet 清理）")

    after = tree_size(dist)
    print(f"  产物体积：{human(before)} → {human(after)}（省 {human(before - after)}）")

    internal = dist / "_internal"
    if internal.is_dir():
        biggest = sorted(
            ((tree_size(p), p.name) for p in internal.iterdir() if p.is_dir()),
            reverse=True,
        )[:8]
        print("  _internal 里最大的几项：")
        for size, name in biggest:
            print(f"    {human(size):>10}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
