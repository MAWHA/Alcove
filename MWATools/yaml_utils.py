import subprocess
import sys

try:
    # 内置异常处理，尝试导入PYyaml模块
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is not installed. Please install it by running: "
        "pip install pyyaml"
    )

def check_adb_connection(adb_path, address):
    """检查ADB连接状态"""
    try:
        result = subprocess.run(
            [adb_path, 'connect', address],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=20
        )
        
        if not result.stdout or not isinstance(result.stdout, str):
            raise ConnectionError(f"ADB命令返回无效输出: {result}")
            
        stdout = result.stdout.lower()
        
        if "connected" in stdout:
            return True
        elif "cannot connect" in stdout:
            raise ConnectionError(f"无法连接到ADB设备: {address}\n错误详情: {result.stderr}")
        else:
            raise ConnectionError(f"未知连接错误: {result.stdout}\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        raise TimeoutError("ADB连接超时，请检查设备和网络")
    except FileNotFoundError:
        raise FileNotFoundError(f"ADB工具未找到，请检查路径: {adb_path}")
    except Exception as e:
        raise Exception(f"ADB连接发生意外错误: {str(e)}")

def read_yaml_file(file_path):
    """读取YAML文件内容"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def write_yaml_file(file_path, data):
    """将数据写入YAML文件"""
    with open(file_path, 'w', encoding='utf-8') as file:
        yaml.dump(data, file, allow_unicode=True, sort_keys=False)

def modify_adb_path(file_path, new_adb_path):
    """修改ADB路径"""
    config = read_yaml_file(file_path)
    if config and 'ADB_Controller' in config:
        config['ADB_Controller']['adb_path'] = [new_adb_path]
        write_yaml_file(file_path, config)
        return True
    return False

def modify_adb_address(file_path, new_address):
    """修改ADB地址"""
    config = read_yaml_file(file_path)
    if config and 'ADB_Controller' in config:
        config['ADB_Controller']['address'] = new_address
        write_yaml_file(file_path, config)
        return True
    return False

if __name__ == '__main__':
    import os
    # 配置文件路径查找逻辑
    config_file = 'Alcove_config.yaml'
    
    # 如果当前目录不存在配置文件，尝试在上级目录查找
    if not os.path.exists(config_file):
        parent_dir_config = os.path.join('..', 'Alcove_config.yaml')
        if os.path.exists(parent_dir_config):
            config_file = parent_dir_config
        
    # 如果仍不存在，尝试基于模块路径查找    
    if not os.path.exists(config_file):
        module_dir_config = os.path.join(os.path.dirname(__file__), '..', 'Alcove_config.yaml')
        module_dir_config = os.path.normpath(module_dir_config)
        if os.path.exists(module_dir_config):
            config_file = module_dir_config

    if not os.path.exists(config_file):
        raise FileNotFoundError("找不到配置文件Alcove_config.yaml，请确保配置文件存在")
    
    try:
        # 读取YAML文件
        config_data = read_yaml_file(config_file)
        print("当前配置:", config_data)
        
        # 获取ADB配置并尝试自动连接
        try:
            adb_path = config_data['ADB_Controller']['adb_path'][0]
            address = config_data['ADB_Controller']['address']
            print(f"\n尝试自动连接ADB设备: {address}")
            
            if check_adb_connection(adb_path, address):
                print(" ADB自动连接成功")
                sys.exit(0)
                
            raise ConnectionError("未能自动连接设备")
                
        except (KeyError, ConnectionError, Exception) as e:
            print(f"\n 自动连接失败: {str(e)}", file=sys.stderr)
            
            # 自动连接失败，转入手动输入模式
            while True:
                try:
                    print("\n示例ADB路径: C:\\platform-tools\\adb.exe 或 /usr/bin/adb")
                    new_adb_path = input("请输入新的ADB路径: ").strip()
                    if not new_adb_path:
                        raise ValueError("ADB路径不能为空")
                        
                    print("\n示例雷电模拟器ADB地址: 127.0.0.1:5555")
                    new_address = input("请输入新的ADB地址: ").strip()
                    if not new_address or ':' not in new_address:
                        raise ValueError("ADB地址格式应为IP:端口")
                    
                    break
                except ValueError as ve:
                    print(f"\n 输入错误: {ve}")
                    print("请重新输入\n")
            
            # 修改ADB配置
            if modify_adb_path(config_file, new_adb_path):
                print("\nADB路径修改成功")
            else:
                print("\nADB路径修改失败")
                
            if modify_adb_address(config_file, new_address):
                print("ADB地址修改成功")
            else:
                print("ADB地址修改失败")
            
            # 获取更新后的ADB配置并重新尝试连接
            config_data = read_yaml_file(config_file)
            adb_path = config_data['ADB_Controller']['adb_path'][0]
            address = config_data['ADB_Controller']['address']
            
            print(f"\n尝试重新连接ADB设备: {address}")
            if check_adb_connection(adb_path, address):
                print(" ADB重新连接成功")
            else:
                raise ConnectionError("手动连接失败")
                
    except KeyError as e:
        print(f"\n 配置错误: 缺少必要的ADB配置项 {str(e)}", file=sys.stderr)
    except ConnectionError as e:
        print(f"\n 连接失败: {str(e)}", file=sys.stderr)
    except Exception as e:
        print(f"\n 发生错误: {str(e)}", file=sys.stderr)
