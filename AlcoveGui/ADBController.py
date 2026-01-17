from PySide6.QtQml import QmlElement, QmlSingleton  
from PySide6.QtCore import QObject, Slot, Signal, QThread  
import sys
import os
import json 

# 1. 获取当前脚本（main_gui.py）的目录路径
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 向上跳转一级，得到项目根目录（Alcove/，即AlcoveGui的上级目录）
project_root = os.path.dirname(current_script_dir)
# 3. 将项目根目录添加到Python的系统搜索路径中
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from MWATools.MWAController import MWAControllerClass
from MWATools.MWALogging import logger
from typing import List
from maa.toolkit import AdbDevice

QML_IMPORT_NAME = "ADBController"
QML_IMPORT_MAJOR_VERSION = 1  

mwa_controller = MWAControllerClass()

class FindADBThread(QThread):
    ADBSignal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def run(self):
        """线程启动后自动执行，运行在子线程中"""
        devices = mwa_controller.load_controller()
         
        adb_device_list = []
        
        for device in devices:
            adb_path = str(device.adb_path) 
            address = str(device.address) 
            
            adb_device_dict = {
                "adb_path": adb_path,
                "adb_address": address
            }
            
            adb_device_list.append(adb_device_dict)
            
        devices_adb_paths_json = json.dumps(adb_device_list)
        self.ADBSignal.emit(devices_adb_paths_json)

class ConnectADBThread(QThread):
    ConnectADBSignal = Signal(str)
    
    def __init__(self, adb_path: str, adb_address: str, parent=None):
        """
        初始化ADB连接线程，接收ADB路径和设备地址
        :param adb_path: ADB工具路径
        :param adb_address: ADB设备地址（如127.0.0.1:16384）
        :param parent: 父对象
        """
        super().__init__(parent)
        # 保存待连接设备的信息（供run方法使用）
        self.adb_path = adb_path
        self.adb_address = adb_address
    
    def run(self):
        mwa_controller.find_adb_controller(self.adb_path, self.adb_address)
        mwa_controller.connect_adb_controller()
        

@QmlElement  
@QmlSingleton  
class ADBController(QObject):
    ADBSignal = Signal(str)
    ConnectADBSignal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workerThread = None
        self.connectWorkerThread = None
    def _handle_adb_data(self, progressInfo: str):
        try:
            self.ADBSignal.emit(progressInfo)
            logger.info(f"获取adb设备路径成功：{progressInfo}")
        except Exception as e:
            logger.error(f"获取adb设备路径失败：ADBController._handle_adb_data()异常：{e}")

    @Slot()
    def find_adb_controller(self):
        if self.workerThread is not None and self.workerThread.isRunning():
            self.ADBSignal.emit("子线程正在扫描ADB设备，请勿重复触发！")
            return
        
        self.workerThread = FindADBThread()
        
        self.workerThread.ADBSignal.connect(self._handle_adb_data)
        
        self.workerThread.start()
        self.workerThread.finished.connect(self.resetWorkerThread)
    
    def resetWorkerThread(self):
        self.workerThread.deleteLater()
        self.workerThread = None

    def _handle_connect_adb_status(self, connectStatus: str):
        try:
            self.ConnectADBSignal.emit(connectStatus)
            logger.info(f"ADB连接状态反馈：{connectStatus}")
        except Exception as e:
            logger.error(f"处理ADB连接状态失败：ADBController._handle_connect_adb_status()异常：{e}")

    @Slot(str, str)
    def connect_adb_controller(self, adb_path: str, adb_address: str):
        """
        供QML调用的ADB连接方法
        :param adb_path: ADB工具路径
        :param adb_address: ADB设备地址
        """
        # 1. 防重复连接：判断连接线程是否正在运行
        if self.connectWorkerThread is not None and self.connectWorkerThread.isRunning():
            self.ConnectADBSignal.emit("正在连接ADB设备，请勿重复触发！")
            return
        
        # 2. 可选：参数校验，避免空参数传入
        if not adb_path or not adb_address:
            self.ConnectADBSignal.emit("连接失败：ADB路径或设备地址不能为空！")
            logger.warning("ADB连接参数为空：路径或地址未填写")
            return
        
        # 3. 初始化连接线程，传入ADB路径和设备地址
        self.connectWorkerThread = ConnectADBThread(adb_path, adb_address)
        
        # 4. 连接线程信号到处理方法，转发连接状态到QML
        self.connectWorkerThread.ConnectADBSignal.connect(self._handle_connect_adb_status)
        
        # 5. 启动连接线程
        self.connectWorkerThread.start()
        
        # 6. 绑定线程结束信号，释放资源
        self.connectWorkerThread.finished.connect(self.resetConnectWorkerThread)

    def resetConnectWorkerThread(self):
        self.connectWorkerThread.deleteLater()
        self.connectWorkerThread = None