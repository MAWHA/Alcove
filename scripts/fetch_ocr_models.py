#!/usr/bin/env python3
"""把 PP-OCRv5 中文模型下载到 ``assets/*/base/model/ocr/``。

模型一共约 20MB，进版本库不合适，所以 ``assets/resource*/base/model/.gitignore``
里只有一行 ``ocr``，把它整个挡在外面。代价是：刚 clone 下来的仓库跑起来一认字就
报 ``model file not found``，打包出来的 exe 也一样（打包脚本里只是打印警告，
不会因此中断）。

    python scripts/fetch_ocr_models.py            # 两个资源包都补齐
    python scripts/fetch_ocr_models.py --check    # 只检查，缺文件就退出码 1
    python scripts/fetch_ocr_models.py --pack resource_picli

模型来自 https://github.com/MaaXYZ/MaaCommonAssets 的 ``OCR/ppocr_v5/zh_cn/``。
换源（内网镜像、离线包）用环境变量 ``ALCOVE_OCR_BASE_URL``，它会被当作目录前缀，
后面拼 ``det.onnx`` / ``rec.onnx`` / ``keys.txt``。
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

#: 每个文件的期望字节数 —— 顺手当成校验和用，能挡掉截断的下载。
FILES: dict[str, int] = {
    "det.onnx": 4_748_769,
    "rec.onnx": 16_517_247,
    "keys.txt": 74_012,
}

PACKS: tuple[str, ...] = ("resource_picli", "resource")

DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/MaaXYZ/MaaCommonAssets/main/OCR/ppocr_v5/zh_cn"
)

ROOT = Path(__file__).resolve().parent.parent


def target_dir(pack: str) -> Path:
    """某个资源包的 OCR 模型目录。"""
    return ROOT / "assets" / pack / "base" / "model" / "ocr"


def missing_files(pack: str) -> list[str]:
    """返回该资源包里缺失（或大小对不上）的模型文件名。"""
    folder = target_dir(pack)
    bad: list[str] = []
    for name, size in FILES.items():
        path = folder / name
        if not path.is_file() or path.stat().st_size != size:
            bad.append(name)
    return bad


def download(url: str, dest: Path) -> None:
    """流式下载到 ``dest``；先写 ``.part`` 再改名，中断不会留下半个正式文件。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)


def fetch(pack: str, base_url: str, *, force: bool = False) -> int:
    """补齐一个资源包，返回下载了几个文件。"""
    folder = target_dir(pack)
    todo = list(FILES) if force else missing_files(pack)
    if not todo:
        print(f"  {pack}: 已齐全（{folder}）")
        return 0

    print(f"  {pack}: 缺 {', '.join(todo)} → {folder}")
    for name in todo:
        url = f"{base_url.rstrip('/')}/{name}"
        dest = folder / name
        print(f"    下载 {name} …", end="", flush=True)
        try:
            download(url, dest)
        except (urllib.error.URLError, OSError) as exc:
            print(f" 失败：{exc}")
            print(f"    可以手动从 {url} 下载后放到 {dest}")
            raise SystemExit(1)
        got = dest.stat().st_size
        want = FILES[name]
        flag = "OK" if got == want else f"大小不对（拿到 {got}，期望 {want}）"
        print(f" {got / 1048576:.1f} MB  {flag}")
        if got != want:
            raise SystemExit(1)
    return len(todo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_ocr_models",
        description="下载 PP-OCRv5 中文模型到 assets/*/base/model/ocr/",
    )
    parser.add_argument(
        "--pack",
        action="append",
        choices=PACKS,
        help="只处理这个资源包，可重复；默认两个都处理",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查不下载；有缺失就返回 1",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使文件已经在了也重新下一遍",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ALCOVE_OCR_BASE_URL", DEFAULT_BASE_URL),
        help="模型来源目录（也可用环境变量 ALCOVE_OCR_BASE_URL）",
    )
    args = parser.parse_args(argv)

    packs = tuple(args.pack) if args.pack else PACKS

    if args.check:
        bad = {pack: missing_files(pack) for pack in packs}
        for pack, names in bad.items():
            state = "齐全" if not names else f"缺 {', '.join(names)}"
            print(f"  {pack}: {state}")
        if any(bad.values()):
            print("\n跑 `python scripts/fetch_ocr_models.py` 补齐。")
            return 1
        return 0

    print(f"来源：{args.base_url}")
    total = sum(fetch(pack, args.base_url, force=args.force) for pack in packs)
    print(f"完成，本次下载 {total} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
