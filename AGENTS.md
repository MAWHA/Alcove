# Alcove 项目代理指南

## 项目概述
Alcove 是"物华弥新"游戏的Python自动化助手，基于MAA框架。项目使用uv进行依赖管理，包含MWATools核心模块、PyPipeline自定义动作模块和assets资源文件。

## 构建与运行命令

### 环境设置
```bash
# 安装uv（如果未安装）
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync

# 激活虚拟环境（可选）
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### 运行应用
```bash
# 运行主程序
python main.py

# 运行测试脚本
python test.py
```

### 依赖管理
```bash
# 添加新依赖
uv add package_name

# 添加开发依赖
uv add --dev package_name

# 同步依赖
uv sync

# 更新所有依赖
uv sync --upgrade
```

### 当前依赖
- maafw>=4.5.6 (MAA框架)
- pyyaml>=6.0.3 (YAML配置解析)
- Python>=3.13

## 代码质量工具

项目当前未配置代码质量工具，建议添加：

### 建议的工具配置
```bash
# 添加代码质量工具
uv add --dev ruff black mypy pytest

# 运行代码格式化
ruff check --fix
ruff format

# 运行类型检查
mypy .

# 运行测试
pytest
```

## 测试命令

### 当前测试结构
项目包含一个测试文件 `test.py`，用于测试基本功能。

### 运行测试
```bash
# 运行所有测试
python test.py

# 运行特定测试模块
python -m pytest MWATools/tests/
```

### 编写测试
- 测试文件应放在 `tests/` 目录或与源文件同级
- 测试函数名以 `test_` 开头
- 使用pytest框架

## 代码风格指南

### 文件组织
```
Alcove/
├── MWATools/          # 核心工具模块
│   ├── __init__.py
│   ├── MWAController.py
│   ├── MWAResource.py
│   ├── MWATasker.py
│   ├── MWAInterface.py
│   ├── MWALogging.py
│   ├── MWATaskPipeline.py
│   ├── MWAReadTask.py
│   ├── MWAConfig.py
│   ├── yaml_utils.py
│   ├── cs.py
│   └── adbcs.py
├── PyPipeline/        # 自定义动作和识别
│   ├── CustomActions/
│   └── CustomRecos/
├── assets/           # 资源文件
├── main.py          # 主程序入口
└── test.py          # 测试文件
```

### 命名约定
1. **类名**: CamelCase
   ```python
   class MWAControllerClass:
   class MWAResourceClass:
   ```

2. **函数名**: snake_case
   ```python
   def load_controller(self):
   def connect_adb_controller(self):
   ```

3. **变量名**: snake_case
   ```python
   adb_controller = MWAController.connect_adb_controller()
   mwa_resource = MWAResourceClass()
   ```

4. **常量名**: UPPER_SNAKE_CASE
   ```python
   INTERFACE_FILE = 'interface.json'
   CONFIG_FILE = '../config.json'
   ```

5. **模块名**: snake_case（文件）或 CamelCase（目录）
   ```
   MWATools/MWAController.py  # 类文件
   PyPipeline/CustomActions/  # 功能目录
   ```

### 导入顺序
1. 标准库导入
2. 第三方库导入
3. 本地模块导入
4. 按字母顺序排序

```python
# 标准库
import json
import os
import time

# 第三方库
from maa.controller import AdbController
from maa.toolkit import Toolkit
import yaml

# 本地模块
from MWATools.MWAInterface import interface
from MWATools.MWALogging import logger
```

### 类型提示
- 所有函数和方法都应使用类型提示
- 返回类型使用 `-> type` 语法

```python
def load_controller(self) -> list:
    """加载控制器"""
    # 实现...

def connect_adb_controller(self) -> AdbController:
    """连接adb控制器"""
    # 实现...
```

### 文档字符串
1. **模块文档**: 文件顶部简要说明模块功能
2. **类文档**: 说明类的作用和主要方法
3. **函数文档**: 说明功能、参数和返回值

```python
class MWAControllerClass:
    def __init__(self):
        """初始化controller"""
        
    def load_controller(self) -> list:
        """加载控制器
        
        根据配置加载ADB或桌面控制器
        
        Returns:
            list: 找到的设备列表
        """
```

### 错误处理
1. 使用try-except处理预期异常
2. 记录错误信息到日志
3. 避免使用裸except

```python
try:
    adb_controller.post_connection().wait()
    logger.info(f"已连接到模拟器:{adb_controller}")
except Exception as e:
    logger.error(f"模拟器连接失败: {e}")
    raise
```

### 日志记录
- 使用 `MWATools.MWALogging.logger`
- 适当使用不同日志级别
- 包含有意义的上下文信息

```python
from MWATools.MWALogging import logger

logger.info(f"选择了{self.adb_controller.name}这个设备")
logger.error("未搜索到adb设备!")
logger.debug(f"控制器配置: {self._controller_config}")
```

### 配置管理
- 配置文件使用YAML格式（`Alcove_config.yaml`）
- JSON配置使用 `config.json`
- 接口定义使用 `interface.json`

### 资源管理
- 游戏资源放在 `assets/resource_picli/`
- 图片资源按功能分类存放
- 管道配置文件放在 `assets/resource_picli/base/pipeline/`

## 开发工作流

### 1. 功能开发
1. 在 `MWATools/` 中添加核心功能
2. 在 `PyPipeline/CustomActions/` 中添加自定义动作
3. 在 `PyPipeline/CustomRecos/` 中添加自定义识别

### 2. 测试验证
1. 在 `test.py` 中添加测试用例
2. 运行 `python test.py` 验证功能
3. 使用 `main.py` 进行集成测试

### 3. 代码审查
1. 检查类型提示
2. 验证错误处理
3. 确保日志记录适当
4. 遵循命名约定

### 4. 资源更新
1. 更新 `assets/` 中的游戏资源
2. 同步更新 `interface.json` 配置
3. 验证管道配置文件

## 提交规范

### 提交信息格式
```
类型(范围): 简短描述

详细描述（可选）
```

### 类型
- feat: 新功能
- fix: 错误修复
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具

### 示例
```
feat(MWAController): 添加ADB设备自动发现功能

- 实现ADB设备扫描
- 添加设备选择逻辑
- 更新配置文件路径
```

## 注意事项

### 平台兼容性
- 主要支持Windows平台（ADB控制器）
- 可扩展支持macOS/Linux

### 依赖管理
- 使用uv锁定依赖版本
- 确保maafw版本兼容性
- 注意Python 3.13+特性使用

### 性能考虑
- 避免阻塞主线程的长时间操作
- 合理使用延迟和等待
- 优化图像识别性能

### 安全性
- 不要提交包含敏感信息的配置文件
- 验证外部输入
- 使用安全的ADB连接

## 故障排除

### 常见问题
1. **ADB连接失败**: 检查模拟器是否运行，ADB路径是否正确
2. **资源加载失败**: 验证 `assets/` 目录结构
3. **导入错误**: 确保虚拟环境已激活，依赖已安装
4. **权限问题**: 以管理员权限运行（如果需要）

### 调试建议
1. 启用调试日志: 修改 `MWALogging.py` 中的日志级别
2. 检查日志文件: `PYMWA.log`
3. 验证配置文件: `Alcove_config.yaml`, `config.json`

---

*最后更新: 2025-03-09*
*适用于Alcove项目开发团队和AI代理*