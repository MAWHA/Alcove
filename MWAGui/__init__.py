"""Alcove 的图形界面（Flet / Flutter 渲染）。"""

from __future__ import annotations

__all__ = ["run"]


def run(*args, **kwargs):
    """惰性转发到 ``MWAGui.app.run``，这样没装 flet 时也能 import 本包。"""
    from .app import run as _run

    return _run(*args, **kwargs)
