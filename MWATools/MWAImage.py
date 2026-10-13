"""把 maafw 交回来的 numpy 图变成能在界面上显示的 PNG。

界面预览不需要 Pillow 这种大家伙：PNG 的容器格式很简单，
自己用 ``numpy`` + ``zlib`` 拼出来就行，少一个必须安装的依赖。

maafw 的截图是 **BGR** 排列，这里顺手换成 RGB。
"""

from __future__ import annotations

import base64
import struct
import zlib

import numpy as np

__all__ = ["to_rgb", "encode_png", "to_data_uri"]


def to_rgb(image: np.ndarray) -> np.ndarray:
    """把 maafw 的 BGR/RGBA/灰度图统一成连续的 RGB uint8 数组。"""
    array = np.asarray(image)

    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    elif array.ndim == 3:
        channels = array.shape[2]
        if channels == 3:
            array = array[:, :, ::-1]          # BGR -> RGB
        elif channels == 4:
            array = array[:, :, [2, 1, 0]]     # BGRA -> RGB
        elif channels != 3:
            array = np.repeat(array[:, :, :1], 3, axis=2)
    else:
        raise ValueError(f"不支持的图像形状：{array.shape}")

    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(array)


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def encode_png(image: np.ndarray, *, max_width: int | None = None,
               compress_level: int = 1) -> bytes:
    """把图像编码成 PNG 字节。

    Args:
        image: BGR/RGB/RGBA/灰度图。
        max_width: 超过这个宽度就按整数步长抽稀（预览用，够看就行）。
        compress_level: zlib 级别，1 是速度与体积的折中。
    """
    rgb = to_rgb(image)

    if max_width and rgb.shape[1] > max_width:
        step = -(-rgb.shape[1] // max_width)     # 向上取整
        rgb = np.ascontiguousarray(rgb[::step, ::step])

    height, width = rgb.shape[:2]
    if height == 0 or width == 0:
        raise ValueError("空图像")

    # 每行前面加一个 filter 类型字节（0 = None）
    raw = np.empty((height, width * 3 + 1), dtype=np.uint8)
    raw[:, 0] = 0
    raw[:, 1:] = rgb.reshape(height, width * 3)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw.tobytes(), compress_level))
        + _chunk(b"IEND", b"")
    )


def to_data_uri(png: bytes) -> str:
    """包装成 Flet / 浏览器能直接吃的 data URI。"""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
