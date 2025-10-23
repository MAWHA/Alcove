from MWATools.MWAController import MWAControllerClass
from MWATools.MWAResource import MWAResourceClass
from MWATools.MWATasker import MWATaskerClass
from MWATools.MWAInterface import interface
from MWATools.MWATaskPipeline import MWATaskPipelineClass
from PyPipeline.CustomActions.StartAction import StartApp
from PyPipeline.CustomActions.Email import RecoEmail
from PyPipeline.CustomActions.Return import Return
MWAResource = MWAResourceClass()


@MWAResource.resource.custom_action("RecoEmail")
class RecoEmail(RecoEmail):
    ...

@MWAResource.resource.custom_action("Return")
class Return(Return):
    ...

if __name__ == '__main__':
    try:
        pipeline_override = {
            "MyCustomEntry": {"action": "custom", "custom_action": "RecoEmail"},
        }
        MWAController = MWAControllerClass()
        MWAController.load_controller()
        MWAController.choose_adb_controller()

        MWATasker = MWATaskerClass()

        adb_controller = MWAController.connect_adb_controller()
        MWATasker.MWATaskerBind(controller=adb_controller, resource=MWAResource.resource)
        task_detail = MWATasker.run_action("MyCustomEntry", pipeline_override)
        # MWATaskPipelineClass = MWATaskPipelineClass()
        # print(MWATaskPipelineClass.add_pipeline('启动'))
        # print(MWATaskPipelineClass.add_pipeline('器者征集',True))
    except KeyboardInterrupt:
        # 捕获Ctrl+C触发的异常
        print("\n检测到Ctrl+C，程序将取消并退出")
        MWATasker.Tasker.stopping()
        # 可选：在这里添加退出前的清理操作（如关闭文件、释放资源等）
        # 程序会在except块执行完后自动退出