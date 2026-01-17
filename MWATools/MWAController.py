from MWATools.MWAInterface import interface
from maa.controller import AdbController
from maa.toolkit import Toolkit
from MWATools.MWALogging import logger


class MWAControllerClass:
    def __init__(self):
        """初始化controller"""
        self._controller_config = interface["controller"][0]
        self.adb_controllers = None
        self.desktop_controllers = None
        self.adb_controller = None

    def load_controller(self):
        """"加载控制器"""
        if self._controller_config["name"] == "安卓端":
            self.adb_controllers = Toolkit.find_adb_devices()
            logger.info(f"Alcove搜索到了{len(self.adb_controllers)}个设备")
            print("请选择要连接的设备:",self.adb_controllers)
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
    
    def choose_adb_controller(self, device_index=0):
        """选择adb控制器"""
        print(self.adb_controllers)
        if len(self.adb_controllers) > 0:
            self.adb_controller = self.adb_controllers[device_index]
            logger.info(f"选择了{self.adb_controller.name,self.adb_controller.address}这个设备")
            return self.adb_controller
        else:
            logger.error("未搜索到adb设备!")
        
    def connect_adb_controller(self):
        """连接adb控制器"""
        adb_controller = AdbController(
            adb_path=self.adb_controller.adb_path,
            screencap_methods=self.adb_controller.screencap_methods,
            address=self.adb_controller.address,
            input_methods=self.adb_controller.input_methods,
            config=self.adb_controller.config
        )
        try:
            adb_controller.post_connection().wait()
            logger.info(f"已连接到模拟器:{self.adb_controller.adb_path,self.adb_controller.address}")
            print(self.adb_controller.config)
        except:
            logger.error(f"模拟器连接失败:{self.adb_controller.adb_path,self.adb_controller.address}")
        return adb_controller
        
    def choose_desktop_controller(self, device_index=0):
        pass
        
    def connect_desktop_controller(self):
        pass
    
if __name__ == '__main__':
    MWAController = MWAControllerClass()
    # adbcontroller = read_Alcove_config()

    # MWAController.find_adb_controller(adbcontroller.get('adb_path'), 
    #                                   adbcontroller.get('address'))