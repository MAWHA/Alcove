#!/usr/bin/env python3
"""把 flet 桌面端客户端压缩包预置进 ``flet_desktop/app/``。

**为什么要这么做**：PyPI 上的 ``flet-desktop`` 是个**空壳** —— 平台无关 wheel，
0.01MB，里面一个二进制都没有。flet 真正跑起来要的客户端（Windows 上是
``flet-windows.zip``，约 40MB）由 ``flet_desktop.ensure_client_cached()`` 从
GitHub Releases 下载，解到 ``~/.flet/client/flet-desktop-full-<版本>/``。

平时这样没问题，但两处会难受：

* 用户第一次打开界面得等它下 40MB，没网就直接失败；
* PyInstaller 打包时 ``hook-flet.py`` 会触发同一段下载逻辑。

把 zip 提前放到 ``flet_desktop/app/`` 之后：

* 打包时 hook 直接用现成的，不联网；
* 运行时 ``ensure_client_cached()`` 优先认包里的这个 zip
  （打包后是 ``_internal/flet_desktop/app/``），解开就用，**不再走网络**。

    python scripts/fetch_flet_client.py          # 下载进当前环境的 flet_desktop
    python scripts/fetch_flet_client.py --check  # 只检查有没有
    python scripts/fetch_flet_client.py --force  # 已经有了也重下

下载源：https://github.com/flet-dev/flet/releases/tag/v<flet-desktop 版本>
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

RELEASE_URL = "https://github.com/flet-dev/flet/releases/download/v{version}/{artifact}"


def _flet_desktop():
    """延迟 import，顺便把「没装 flet-desktop」这条错讲清楚。"""
    try:
        import flet_desktop  # noqa: PLC0415
        from flet_desktop import get_artifact_filename, get_package_bin_dir  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 环境问题
        print(
            f"导不进 flet_desktop（{exc}）。\n"
            "先装依赖：pip install 'flet>=1.0.4' 'flet-desktop>=1.0.4'",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    return flet_desktop, get_artifact_filename, get_package_bin_dir


def target_path() -> tuple[Path, str]:
    """返回 (压缩包应放的位置, 该位置的下载地址)。"""
    flet_desktop, get_artifact_filename, get_package_bin_dir = _flet_desktop()
    version = flet_desktop.version.version
    artifact = get_artifact_filename()
    dest = Path(get_package_bin_dir()) / artifact
    url = RELEASE_URL.format(version=version, artifact=artifact)
    return dest, url


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    print(f"  下载 {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with tmp.open("wb") as fh:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        print(f"\r  {done / 1048576:6.1f} / {total / 1048576:.1f} MB  {pct:3d}%", end="")
                    else:
                        print(f"\r  {done / 1048576:6.1f} MB", end="")
        print()
    except (urllib.error.URLError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        print(f"  下载失败：{exc}", file=sys.stderr)
        print(f"  可以手动下载 {url} 后放到 {dest}", file=sys.stderr)
        raise SystemExit(1) from exc
    tmp.replace(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_flet_client",
        description="预置 flet 桌面端客户端，避免打包/首次运行时联网下载",
    )
    parser.add_argument("--check", action="store_true", help="只检查，缺失返回 1")
    parser.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = parser.parse_args(argv)

    dest, url = target_path()
    size = dest.stat().st_size if dest.is_file() else 0

    if size > 1_048_576 and not args.force:  # 1MB 以下基本可以断定是坏文件
        print(f"  已经在了：{dest}（{size / 1048576:.1f} MB）")
        return 0

    if args.check:
        print(f"  缺失：{dest}\n  （应有 {url}）", file=sys.stderr)
        return 1

    download(url, dest)
    got = dest.stat().st_size
    print(f"  完成：{dest}（{got / 1048576:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
