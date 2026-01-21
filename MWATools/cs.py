import sys
import os
# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import yaml
import subprocess
from MWATools.MWAInterface import interface
from maa.controller import AdbController
from maa.toolkit import Toolkit
from MWATools.MWALogging import logger


class MWAControllerClass:
    def __init__(self):
        """初始化controller"""
        try:
            self._controller_config = interface["controller"][0]
            self.full_config = {}
            logger.info(f"成功加载控制器配置, interface路径: {self._controller_config.get('interface_path', '未指定')}")
            logger.debug(f"完整控制器配置:\n{self._controller_config}")
        except Exception as e:
            logger.error(f"加载控制器配置失败: {str(e)}")
            raise
        
        self.adb_controllers = None
        self.desktop_controllers = None
        self.adb_controller = None

    def load_controller(self):
        """"加载控制器"""
        if self._controller_config["name"] == "安卓端":
            self.adb_controllers = Toolkit.find_adb_devices()
            logger.info(f"Alcove搜索到了{len(self.adb_controllers)}个设备")
            return self.adb_controllers
        elif self._controller_config["name"] == "win32端":
            '''基本没用'''
            self.desktop_controllers = Toolkit.find_desktop_windows()
            logger.info(f"Alcove搜索到了{len(self.desktop_controllers)}个设备")
            return self.desktop_controllers
   
    def find_adb_controller(self, adb_path, address):
        self.adb_controllers = Toolkit.find_adb_devices()
        for controller in self.adb_controllers:
            if controller.adb_path == adb_path or controller.address == address:
                # TODO: adb_path和address暂时没有都匹配
                self.choose_adb_controller(device_index=self.adb_controllers.index(controller))
                logger.info(f"从Alcove_config.yaml中读取到{adb_path,address}这个设备并连接")
    
    def choose_adb_controller(self, device_index=0):
        """选择adb控制器"""
        print(self.adb_controllers)
        if len(self.adb_controllers) == 0:
            logger.error("未搜索到adb设备!")
            return None
        elif len(self.adb_controllers) == 1:
            self.adb_controller = self.adb_controllers[0]
            logger.info(f"自动选择了唯一设备: {self.adb_controller.name, self.adb_controller.address}")
            return self.adb_controller
        else:
            print("发现多个设备，请选择要连接的设备:")
            for i, device in enumerate(self.adb_controllers):
                print(f"{i}: {device.name} - {device.address}")
            
            while True:
                try:
                    choice = int(input("请输入设备编号: "))
                    if 0 <= choice < len(self.adb_controllers):
                        self.adb_controller = self.adb_controllers[choice]
                        logger.info(f"用户选择了设备: {self.adb_controller.name, self.adb_controller.address}")
                        return self.adb_controller
                    else:
                        print(f"无效输入，请输入0-{len(self.adb_controllers)-1}之间的数字")
                except ValueError:
                    print("请输入有效的数字编号")
        
    def connect_adb_controller(self):
        """连接adb控制器并更新配置文件"""
        logger.info(f"正在尝试连接设备: {self.adb_controller.name} - {self.adb_controller.address}")
        
        try:
            # 创建控制器实例
            adb_controller = AdbController(
                adb_path=self.adb_controller.adb_path,
                screencap_methods=self.adb_controller.screencap_methods,
                address=self.adb_controller.address,
                input_methods=self.adb_controller.input_methods,
                config=self.adb_controller.config
            )

            # 尝试连接并等待结果
            connection = adb_controller.post_connection()
            if connection.wait():
                logger.info(f" 成功连接到模拟器: {adb_controller}")
                
                # 验证连接状态
                # 增加手动adb devices检查作为连接验证
                try:
                    proc = subprocess.run(
                        [str(self.adb_controller.adb_path), "devices"],
                        timeout=5,
                        capture_output=True,
                        text=True
                    )
                    logger.debug(f"ADB devices输出:\n{proc.stdout}")
                    if self.adb_controller.address not in proc.stdout:
                        logger.error(f"设备{self.adb_controller.address}未在adb devices列表中")
                        raise ConnectionError("设备未连接或未授权")
                except subprocess.TimeoutExpired:
                    logger.error("ADB命令执行超时")
                    raise TimeoutError("ADB服务响应超时")
                except Exception as e:
                    logger.error(f"ADB检查失败: {str(e)}")
                    raise ConnectionError("ADB服务检查失败")

                logger.info("连接状态验证通过")
                
                # 更新配置
                config_file = 'Alcove_config.yaml'
                try:
                    if self.modify_adb_path(config_file, str(self.adb_controller.adb_path)):
                        logger.info(f"更新ADB路径配置: {self.adb_controller.adb_path}")
                    if self.modify_adb_address(config_file, self.adb_controller.address):
                        logger.info(f"更新ADB地址配置: {self.adb_controller.address}")
                    print("\nADB连接成功!")
                    print(f"设备名称: {self.adb_controller.name}")
                    print(f"设备地址: {self.adb_controller.address}")
                    print(f"ADB路径: {self.adb_controller.adb_path}")
                except Exception as e:
                    logger.error(f"配置更新失败: {str(e)}")
                    raise
            else:
                logger.error("连接超时")
                raise TimeoutError("连接超时")

        except Exception as e:
            logger.error(f"连接过程中发生错误: {str(e)}")
            # 检查ADB服务是否运行
            try:
                subprocess.run([str(self.adb_controller.adb_path), "devices"], timeout=5, check=True)
            except:
                logger.error("ADB服务可能未正常运行")
            raise
        return adb_controller
        
    def choose_desktop_controller(self, device_index=0):
        pass
        
    def connect_desktop_controller(self):
        pass

    def modify_adb_path(self, file_path=None, new_adb_path=None):
        """修改ADB路径"""
        import os
        try:
            if file_path is None:
                file_path = 'Alcove_config.yaml'
                
                # 如果当前目录不存在配置文件，尝试在上级目录查找
                if not os.path.exists(file_path):
                    parent_dir_config = os.path.join('..', 'Alcove_config.yaml')
                    if os.path.exists(parent_dir_config):
                        file_path = parent_dir_config
                    
                # 如果仍不存在，尝试基于模块路径查找    
                if not os.path.exists(file_path):
                    module_dir_config = os.path.join(os.path.dirname(__file__), '..', 'Alcove_config.yaml')
                    module_dir_config = os.path.normpath(module_dir_config)
                    if os.path.exists(module_dir_config):
                        file_path = module_dir_config

                if not os.path.exists(file_path):
                    raise FileNotFoundError("找不到配置文件Alcove_config.yaml，请确保配置文件存在")

            with open(file_path, 'r', encoding='utf-8') as file:
                # 禁用自定义构造器，防止WindowsPath等特殊对象造成问题
                yaml.SafeLoader.add_constructor(None, lambda loader, node: None)
                config = yaml.safe_load(file) or {}
            
            if config and 'ADB_Controller' in config:
                adb_controller = config['ADB_Controller']
                # 处理ADB_Controller可能是列表或字典的情况
                if isinstance(adb_controller, list) and len(adb_controller) > 0:
                    adb_controller = adb_controller[0]
                if isinstance(adb_controller, dict):
                    adb_controller['adb_path'] = [str(new_adb_path)]
                    self.full_config = config  # Save full config
                    logger.debug(f"更新后的完整配置:\n{config}")
                    with open(file_path, 'w', encoding='utf-8') as file:
                        yaml.dump(config, file, allow_unicode=True, sort_keys=False,
                                 default_flow_style=False, Dumper=yaml.SafeDumper)
                    return True
                return True
            return False
        except Exception as e:
            logger.error(f"修改ADB路径失败: {str(e)}")
            raise

    def get_current_config(self):
        """获取当前配置信息"""
        if not self.adb_controller:
            return "无当前配置"
        return f"""当前设备配置:
ADB路径: {self.adb_controller.adb_path}
设备地址: {self.adb_controller.address}
完整配置: {self.adb_controller.config}"""

    def modify_adb_address(self, file_path, new_address):
        """修改ADB地址"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # 禁用自定义构造器
                yaml.SafeLoader.add_constructor(None, lambda loader, node: None)
                config = yaml.safe_load(file) or {}
            
            if config and 'ADB_Controller' in config:
                adb_controller = config['ADB_Controller']
                # 处理ADB_Controller可能是列表或字典的情况
                if isinstance(adb_controller, list) and len(adb_controller) > 0:
                    adb_controller = adb_controller[0]
                if isinstance(adb_controller, dict):
                    adb_controller['address'] = str(new_address)
                    self.full_config = config  # Save full config
                    logger.debug(f"更新后的完整配置:\n{config}")
                    with open(file_path, 'w', encoding='utf-8') as file:
                        yaml.dump(config, file, allow_unicode=True, sort_keys=False,
                                 default_flow_style=False, Dumper=yaml.SafeDumper)
                    return True
                return True
            return False
        except Exception as e:
            logger.error(f"修改ADB地址失败: {str(e)}")
            raise

if __name__ == '__main__':
    MWAController = MWAControllerClass()
    
    # 加载可用控制器
    controllers = MWAController.load_controller()
    if not controllers:
        print("错误：未找到可用设备控制器，请检查：")
        print("1. 模拟器是否已启动")
        print("2. ADB服务是否正常运行")
        print("3. 设备是否已授权")
        logger.error("未找到可用设备控制器，请检查：")
        logger.error("1. 模拟器是否已启动")
        logger.error("2. ADB服务是否正常运行")
        logger.error("3. 设备是否已授权")
        exit(1)
        
    # 自动选择和连接第一个ADB设备
    if MWAController.adb_controllers:
        MWAController.choose_adb_controller()
        MWAController.connect_adb_controller()