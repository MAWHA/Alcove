import yaml
from os.path import exists

from maa.controller import AdbController


class MWAConfig:
    def __init__(self):
        self.config_data_existence = exists('Alcove_config.yaml')

    @staticmethod
    def generate_Alcove_config(adb_path: str, address: str):
        # 1. 定义配置数据（支持嵌套字典、列表，数据类型更丰富）
        if not exists('Alcove_config.yaml'):
            config_data = {
                'ADB_Controller': {
                    'adb_path': adb_path,
                    'address': address,
                    },
                'TaskList':{
                    # TODO: 任务列表的配置选项
                }
            }
            
            # 2. 写入到 YAML 文件
            with open('Alcove_config.yaml', 'w', encoding='utf-8') as yaml_file:
                yaml.dump(config_data, yaml_file, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def read_Alcove_config():
        # 1. 读取 YAML 文件
        with open('Alcove_config.yaml', 'r', encoding='utf-8') as yaml_file:
            config_data = yaml.load(yaml_file, Loader=yaml.FullLoader)
            # 2. 解析配置数据
        adb_path = config_data['ADB_Controller']['adb_path']
        address = config_data['ADB_Controller']['address']
        # TODO: 解析任务列表的配置选项
        # 3. 返回配置数据
        return  {'adb_path': adb_path, 'address': address}