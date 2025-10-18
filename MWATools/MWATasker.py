from maa.tasker import Tasker
from maa.toolkit import Toolkit
from MWATools.MWAResource import MWAResourceClass
from MWATools.MWAController import MWAControllerClass


class MWATaskerClass:
    def __init__(self, user_path: str = "./"):
        """初始化tasker,初始化用户路径"""
        self.Tasker = Tasker()
        self.UserPath = user_path
        Toolkit.init_option(self.UserPath)

    def MWATaskerBind(self, resource, controller,):
        """将controller和resource绑定到Tasker"""
        self.Tasker.bind(resource, controller)

    def run_action(self, entry, pipeline_override={}):
        """运行任务"""
        task_detail = self.Tasker.post_task(entry, pipeline_override).wait().get()
        return task_detail

    def run_custom_action(self, action_name, action_param):
        """运行自定义任务"""
        pass

if __name__ == "__main__":
    MWATasker = MWATaskerClass()
    resource = MWAResourceClass()
    resource2 = resource.resource
    MWAController = MWAControllerClass()
    MWAController.load_controller()
    MWAController.choose_adb_controller()
    adb_controller = MWAController.connect_adb_controller()
    adb_controller.post_connection().wait()
    MWATasker.MWATaskerBind(controller=adb_controller, resource=resource2)
    MWATasker.run_action("Start")