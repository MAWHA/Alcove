import sys
import os

# 1. 获取当前脚本（main_gui.py）的目录路径
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 向上跳转一级，得到项目根目录（Alcove/，即AlcoveGui的上级目录）
project_root = os.path.dirname(current_script_dir)
# 3. 将项目根目录添加到Python的系统搜索路径中
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from MWATools.MWAConfig import MWAConfig
from MWATools.MWAResource import MWAResourceClass

from PySide6.QtQml import QmlElement, QmlSingleton  
from PySide6.QtCore import QObject, Slot, Signal, QThread  

QML_IMPORT_NAME = "ConfigRead"
QML_IMPORT_MAJOR_VERSION = 1  

mwaconfig = MWAConfig()
resource = mwaconfig.read_Alcove_resource()

resourceClass = MWAResourceClass(resource_path=resource)

class getResourceThread(QThread):
    ResourceSignal = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def run(self):
        self.ResourceSignal.emit(resource)

@QmlElement  
@QmlSingleton  
class ConfigRead(QObject):
    ResourceSignal = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workerThread = None
        self.ResourceWorkerThread = None
    
    def _handle_resource_data(self, progressInfo: str):
        self.ResourceSignal.emit(progressInfo)

    @Slot(result=str)
    def get_resource(self):
        self.ResourceWorkerThread = getResourceThread()
        self.ResourceWorkerThread.ResourceSignal.connect(self._handle_resource_data)
        self.ResourceWorkerThread.start()
        return "Resource data is being fetched..."

    def resetResourceWorkerThread(self):
        self.ResourceWorkerThread.deleteLater()
        self.ResourceWorkerThread = None