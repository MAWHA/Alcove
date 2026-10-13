# -*- mode: python ; coding: utf-8 -*-
"""Alcove 的 PyInstaller 配方（onedir）。

用法 —— 在仓库根目录，依赖装好之后：

    pyinstaller --noconfirm --clean Alcove.spec

产物是 ``dist/Alcove/``：里面有 ``Alcove.exe``（Linux 上是 ``Alcove``）和一大坨
``_internal/``。**整个目录**才是可分发的成品，单独拿走那个可执行文件跑不起来。

配这份 spec 时被坑到的点，按重要性列在这里：

1. ``assets/`` 是只读资源（图片、OCR 模型、旧 pipeline JSON），打包后由
   ``MWATools/MWAPaths.py`` 用 ``sys._MEIPASS`` 找回，即 ``_internal/assets``。
   用户的可写数据（``config.json``、``logs/``）走另一条路，见 MWAPaths 的注释。

2. ``PyPipeline/{Tasks,CustomActions,CustomRecos}`` 全是**扫目录**加载的
   （``Tasks.load_all()`` 用 ``pkgutil.iter_modules``，``MWACustomAction._scan``
   用 ``Path.iterdir``）。所以这些源码既得作为数据文件躺在盘上（不然扫不到），
   又得进 ``hiddenimports``（不然 import 不到）。缺一不可。

3. ``MaaAgentBinary/`` 是 ``maaagentbinary`` 装出来的**顶层数据目录**，不是 Python
   模块（``import maaagentbinary`` 会 ModuleNotFoundError），PyInstaller 永远扫不到它。
   而 ``maa/controller.py`` 是按 ``os.path.dirname(maa.__file__)/../MaaAgentBinary``
   去找的 —— 所以它必须和 ``maa/`` 平级放进包里，否则 minitouch/maatouch 全用不了。

4. ``maa`` 里 ``bin/*.dll|*.so`` 是 ``ctypes`` 运行时加载的，只能靠 ``collect_all`` 收。

5. ``flet`` 桌面端最绕，分三层：
   * PyPI 上的 ``flet-desktop`` 是**空壳**（平台无关 wheel，0.01MB，一个二进制都没有），
     真正的客户端由 ``flet_desktop`` 从 GitHub Releases 取 ——
     取的是 ``flet_desktop/app/<flet-windows.zip>`` 这个压缩包，没有就当场下载。
   * PyInstaller 的 hook 由 **``flet-cli``** 用 entry point 注册
     （``[pyinstaller40] hook-dirs = flet_cli.__pyinstaller:get_hook_dirs``），
     所以打包环境里必须有 ``flet-cli``，否则 hook 根本不生效。
   * 那个 hook 拿的是 ``get_flet_bin_path()``，也就是 ``~/.flet/client/...`` 里
     **解开的**整棵目录，把它塞进 ``flet_desktop/app/``；而运行时只认压缩包。
     两边对不上 → 静默退回联网下载。所以本配方要求先把压缩包预置好
     （``scripts/fetch_flet_client.py``），打包后再用 ``scripts/prune_dist.py``
     删掉 hook 塞进来的那份解开的重复副本（几十 MB）。
"""

import os
import sys
import tempfile
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve()

datas: list = []
binaries: list = []
hiddenimports: list = []


def find_in_sys_path(name: str) -> Path | None:
    """在 ``sys.path`` 上找顶层条目（包或数据目录）。"""
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry) / name
        if candidate.exists():
            return candidate
    return None


def add_tree(src: Path, dest: str, *, required: bool = True) -> None:
    """把一棵目录（或单个文件）原样搬进包里，保持相对布局。"""
    if src.is_dir():
        datas.append((str(src), dest))
    elif src.is_file():
        datas.append((str(src), str(Path(dest).parent)))
    elif required:
        raise SystemExit(f"[Alcove.spec] 找不到必需的资源：{src}")


# ---------------------------------------------------------------- 1. 只读资源
add_tree(ROOT / "assets", "assets")  # 图片 / OCR 模型 / 旧 pipeline JSON
add_tree(ROOT / "config", "config")  # maafw 的 schema + maa_option.json

# ------------------------------------------------- 2. 扫目录加载的包（源码 + 模块）
for dotted, folder in (
    ("PyPipeline.Tasks", ROOT / "PyPipeline" / "Tasks"),
    ("PyPipeline.CustomActions", ROOT / "PyPipeline" / "CustomActions"),
    ("PyPipeline.CustomRecos", ROOT / "PyPipeline" / "CustomRecos"),
):
    add_tree(folder, dotted.replace(".", "/"))
    hiddenimports += collect_submodules(dotted)

hiddenimports += collect_submodules("MWATools")
hiddenimports += collect_submodules("MWAGui")

# --------------------------------------------- 3. MaaAgentBinary（必须与 maa/ 平级）
agent_binary = find_in_sys_path("MaaAgentBinary")
if agent_binary is None:
    print(
        "[Alcove.spec] ！！ 找不到 MaaAgentBinary/（来自 maaagentbinary 包）——\n"
        "            打出来的包在连接设备时会报 minitouch/maatouch 不存在，\n"
        "            进游戏后点击会退化得很慢。"
    )
else:
    add_tree(agent_binary, "MaaAgentBinary")

# ------------------------------------------- 4. 靠 collect_all 才收得全的包
# maa             —— bin/ 下的动态库是 ctypes 运行时加载的
# flet            —— 一堆动态导入的控件模块 + icons.json
# flet_desktop    —— 主要是 app/ 里预置好的桌面端压缩包（见文件头第 5 点）
for package in ("maa", "flet", "flet_desktop"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# ------------------- 4b. maa 里「按名字 dlopen」的库要再往包根放一份
# ``collect_all("maa")`` 把 ``maa/bin/*.so`` 收进 ``_internal/maa/bin/``，可
# PyInstaller 的 bootloader 会把 ``_internal`` 塞进 ``LD_LIBRARY_PATH``
# （Windows 上等价于 DLL 搜索目录），于是 ``libMaaUtils.so`` 这类**被 DT_NEEDED
# 依赖**的库会先从包根加载 —— maa 的 C++ 层再用 ``dladdr()`` 反推自己的目录，
# 算出来就成了包根。可框架是用 ``dlopen``/``LoadLibrary`` **按名字**加载控制单元的
# （``MaaAdbControlUnit`` 这些），包根里偏偏没有它们，结果新包一个 ADB 设备都扫不到，
# 只刷 ``Failed to load library [libname=…/_internal/MaaAdbControlUnit]
# [message=Bad file descriptor]``。
# DT_NEEDED 的库 PyInstaller 会自动往包根搬，dlopen 的不会 —— 只能手动补这一份。
# 代价约 2MB：控制单元本身很小，大块头（onnxruntime / opencv / webgpu）早被搬过了。
_maa_pkg = find_in_sys_path("maa")
if _maa_pkg is not None and (_maa_pkg / "bin").is_dir():
    _maa_bin = _maa_pkg / "bin"
    _dlopen_libs = [
        p
        for p in sorted(_maa_bin.iterdir())
        if p.is_file()
        and ("ControlUnit" in p.name or "AgentClient" in p.name or "AgentServer" in p.name)
    ]
    for _lib in _dlopen_libs:
        binaries.append((str(_lib), "."))
    _plugins = _maa_bin / "plugins"
    if _plugins.is_dir():
        binaries.append((str(_plugins), "plugins"))
    print(f"[Alcove.spec] maa 的 dlopen 库补到包根：{len(_dlopen_libs)} 个 + plugins/")
else:
    print(
        "[Alcove.spec] ！！ 找不到 maa/bin ——\n"
        "            打出来的包连不上设备（控制单元加载失败）。"
    )

# ---------------------------------------------------------- 5. 打包前预警（不中断）
for pack in ("resource_picli", "resource"):
    ocr_dir = ROOT / "assets" / pack / "base" / "model" / "ocr"
    if not (ocr_dir / "det.onnx").is_file() or not (ocr_dir / "rec.onnx").is_file():
        print(
            f"[Alcove.spec] ！！ {pack} 的 OCR 模型不全（{ocr_dir}）——\n"
            "            打出来的包在识别文字时会报 model file not found；\n"
            "            先跑 `python scripts/fetch_ocr_models.py`。"
        )

_flet_app = find_in_sys_path("flet_desktop")
_flet_zip: Path | None = None
if _flet_app is not None and (_flet_app / "app").is_dir():
    _flet_zip = next((p for p in sorted((_flet_app / "app").iterdir()) if p.is_file()), None)

if _flet_zip is None:
    print(
        "[Alcove.spec] 提示：flet_desktop/app/ 里没有预置的桌面端压缩包 ——\n"
        "            打包时会去 GitHub Releases 下载（约 40MB），而且打出来的包\n"
        "            没法离线跑（运行时还要再下一次）。想省这一步就先跑\n"
        "            `python scripts/fetch_flet_client.py`。"
    )

# ------------------------------------------- 6. 让 flet 的 hook 别去碰 ~/.flet
# ``flet-cli`` 的 ``hook-flet.py`` 会调 ``get_flet_bin_path()``，它的解析顺序是：
#   1. 环境变量 FLET_VIEW_PATH —— 存在就直接返回，不再往下走；
#   2. ``ensure_client_cached()`` —— 会往 ``~/.flet/client/`` 里解压，既要求家目录
#      可写，又会把解开的整棵树塞进包里（几十 MB，而运行期只认压缩包）。
# 所以这里塞一个空目录给它。桌面端客户端改由 ``collect_all("flet_desktop")``
# 把预置好的压缩包**原样**带进 ``flet_desktop/app/`` —— 那才是运行时真正读的。
if not os.environ.get("FLET_VIEW_PATH"):
    _view_stub = Path(tempfile.mkdtemp(prefix="alcove-flet-view-"))
    (_view_stub / ".keep").write_text(
        "占位目录：让 flet_cli 的 PyInstaller hook 跳过下载/解压桌面端客户端。\n",
        encoding="utf-8",
    )
    os.environ["FLET_VIEW_PATH"] = str(_view_stub)

# ------------------------------------------------------------------- 7. 分析组装
a = Analysis(  # noqa: F821 - PyInstaller 注入的全局
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "_tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Alcove",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 命令行 + GUI 双入口，留着控制台才看得到日志和报错
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Alcove",
)
