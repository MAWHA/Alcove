# Alcove · 物华弥新小助手（Python 重写版）

用 Python 重写原本由 **MaaPiCli + `assets/interface.json`** 驱动的《物华弥新》自动化助手。

核心思路：maafw 的 Python 绑定**不提供 ProjectInterface 支持**（`maa` 包里没有任何 interface 相关 API），
所以这里自己实现了「读 interface.json / 合并 option 覆盖 / 驱动任务」这一层，并把原本 36 个 pipeline JSON
里的流程改写成了**模块化的 Python 任务**：纯 Python 控制流，maafw 只负责「眼睛（识别）和手（点击）」。

---

## 快速开始

```bash
# 1. 装依赖（如果要用界面，带上 gui extra）
uv sync              # 只跑命令行
uv sync --extra gui  # 要 GUI

# 2. 看看有哪些设备和任务
uv run python main.py --list

# 3. 跑任务（任务名就是 --list 里显示的名字）
uv run python main.py -t 启动 -t 邮箱
uv run python main.py --all          # 跑所有默认勾选的任务
uv run python main.py --gui          # 打开图形界面
```

没有 uv 的话，`pip install -e ".[gui]"` 然后 `python main.py` 也一样。

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `-l`, `--list` | 列出可用设备与任务后就退出 |
| `-t`, `--task 名字` | 要跑的任务，可重复；省略时跑「默认勾选」的那批 |
| `--all` | 跑全部任务（包括没默认勾选的） |
| `-d`, `--device 序号或地址` | 指定设备；`--list` 里的 `[0]`/`[1]` 就是序号，也可以写 `127.0.0.1:16384` |
| `-b`, `--bundle 路径` | 换一个资源包目录（默认 `assets/resource_picli/base`） |
| `--no-ocr` | 不加载 OCR 模型（启动快，但所有认字的识别都用不了） |
| `--no-pipeline` | 不加载旧 pipeline 节点表。只跑已迁移的 Python 任务时可以加，启动更快 |
| `--debug` | 打开 maafw 的调试日志与存图 |
| `--gui` | 打开图形界面 |
| `--keep-error` | 出错时不清理临时文件 |
| `-q`, `--quiet` | 只留文件日志，不往控制台打 |

---

## 目录结构

```
main.py                     入口：命令行 / 界面
MWATools/                   基础设施层（不依赖任何具体游戏功能）
  MWAPaths.py                 路径解析（基于文件位置，不看当前工作目录）
  MWALogging.py               日志 + 事件总线（界面靠它拿实时消息）
  MWAController.py            找设备 / 建控制器（ADB、桌面窗口）
  MWAResource.py              加载资源包：模板图库 + OCR 模型（+ 可选旧 pipeline）
  MWATasker.py                把 controller / resource / tasker 组装起来
  MWAScreen.py                ★「眼睛和手」：截图、找图、认字、点击、滑动、等画面静止
  MWATask.py                  ★任务注册表 + 步骤词汇表（Cand / OCR / IMG / scan）+ 执行器
  MWAImage.py                 不依赖 Pillow 的 PNG 编码（给界面传预览图用）
  MWAInterface.py             interface.json 的轻量只读解析
  MWAReadTask.py              interface.json 的任务目录读取
  MWATaskPipeline.py          option → pipeline_override 合并（等价 MaaPiCli 的 Configurator）
  MWACustomAction.py          自定义动作 / 识别的注册表
PyPipeline/
  Tasks/                      业务层：一个游戏功能一个模块，导入即注册
    startup.py  mail.py  dissect.py  ...
  CustomActions/              旧式自定义动作（供 MWACustomAction 发现）
MWAGui/                     Flet 图形界面
docs/移植规范.md             把 pipeline JSON 改写成 Python 任务的规范
assets/                     资源包、图片、OCR 模型、interface.json
```

---

## 写一个新任务

在 `PyPipeline/Tasks/` 下新建一个 `.py`，声明好就自动生效（不用改任何注册表）：

```python
from MWATools.MWATask import IMG, OCR, QUIT, handle_exceptions, task

@task("邮箱", group="日常", order=60, description="打开邮箱把东西领了")
def 邮箱(ctx) -> bool:
    """旧节点 ``Mail``。"""
    ctx.tap(IMG("Mainpage/mail.png"))                       # 找图并点
    ctx.scan(领全部, QUIT, handle_exceptions, timeout=20_000)  # 谁先命中就干谁
    return True

def 领全部(ctx) -> bool:
    """旧节点 ``ReceiveMail``。"""
    ctx.tap(OCR("全部", delay=5000, desc="全部领取"))
    return True
```

要点：

- **`ctx.scan(A, B, C)` 就是旧 pipeline 的 `next` 列表** —— 反复按顺序试，谁先命中就执行谁，全不中就一直重试到超时。
- `ctx.tap(x)` 命中后自动点它的中心；`ctx.screen.click((x, y, w, h))` 点矩形中心，等价于旧 JSON 的 `"target": [x,y,w,h]`。
- **坐标一律用截图坐标系**（maafw 把画面缩到短边 720 后的坐标），识别结果和点击/滑动都是这一套，不用自己换算。
- 模块之间不要互相 import；共用件（`QUIT` / `MAIN_PAGE` / `handle_exceptions` 等）放在 `MWATools` 里。
- 详细规范见 [`docs/移植规范.md`](docs/移植规范.md)。

---

## 两个任务来源

1. **Python 实现** —— `PyPipeline/Tasks/` 下的模块，纯 Python 控制流。**目前 19 个任务全部是这一种。**
2. **旧流水线（过渡机制，当前用不上）** —— 万一某个 `interface.json` 里的任务还没写成 Python 模块，
   它会自动注册成「旧流水线（待迁移）」组，直接把 `entry` 交给 maafw 原生执行（这时**不要**加
   `--no-pipeline`）。同一个任务名，Python 实现优先，旧流水线自动让位；`--list` 最后会打印迁移进度。

`MWATools/MWAInterface.py`（读 `interface.json`）+ `MWAReadTask.py`（任务目录）+ `MWATaskPipeline.py`
（option → `pipeline_override` 合并，等价官方 MaaPiCli 的 `Configurator`）+ `MWACustomAction.py`
（自定义动作/识别注册表）就是这条过渡通路，位置留给未来新增任务用。

---

## 运行环境说明

- **Python ≥ 3.13**。`maafw` 的 `maa/define.py` 无条件 `import strenum`，但 maafw 自己没声明这个依赖，
  所以 `strenum` 被显式写进了 `pyproject.toml`，别删。
- **OCR 模型不在版本库里**（`assets/*/base/model/.gitignore` 里写着 `ocr`）。运行前需要有
  `assets/resource_picli/base/model/ocr/` 下的 `det.onnx` / `rec.onnx` / `keys.txt`，
  否则所有 OCR 识别会报 `model file not found`。模型来自
  [MaaXYZ/MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets) 的 `OCR/ppocr_v5/zh_cn/`（约 20 MB）。
- 两个资源包：`assets/resource_picli/base`（命令行这边用）与 `assets/resource/base`（图形界面那边用）。
- **日志**在 `logs/` 下；maafw 自己的日志在 `logs/maa/`。
