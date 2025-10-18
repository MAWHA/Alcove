import json
import os

# 常量定义
INTERFACE_FILE = 'interface.json'
CONFIG_FILE = '../config.json'

def _find_interface_path() -> str:
    """在项目目录中搜索interface.json文件并返回绝对路径"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for root, _, files in os.walk(base_dir):
        if INTERFACE_FILE in files:
            found_path = os.path.normpath(os.path.join(root, INTERFACE_FILE))
            print(f"Found {INTERFACE_FILE} at: {found_path}")
            return found_path
    print(f"Warning: {INTERFACE_FILE} not found in project directory")
    return None

def _update_config_path(interface_path: str) -> bool:
    """更新配置文件中的路径"""
    config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
    
    try:
        # 读取现有配置或创建新配置
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        
        # 更新路径并写回
        config_data["interface_path"] = interface_path
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
            print(f"Updated {CONFIG_FILE} with new interface path")
        return True
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading {CONFIG_FILE}: {str(e)}")
    except IOError as e:
        print(f"Error writing to {CONFIG_FILE}: {str(e)}")
    return False

def _get_interface(interface_path: str) -> list:
    """从interface.json文件中读取并返回键列表"""
    try:
        with open(interface_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error processing {INTERFACE_FILE}: {str(e)}")
    except IOError as e:
        print(f"Error reading {INTERFACE_FILE}: {str(e)}")
    return []

def load_interface() -> list:
    """主函数：定位文件、更新配置、返回接口键"""
    interface_path = _find_interface_path()
    if not interface_path:
        return []
    
    if not _update_config_path(interface_path):
        print("Failed to update configuration")
    
    return _get_interface(interface_path)


interface = load_interface()


if __name__ == '__main__':
    print("Interface keys:", load_interface()["task"])