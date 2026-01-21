from MWATools.MWAController import MWAControllerClass
from MWATools.MWAResource import MWAResourceClass
from MWATools.MWATasker import MWATaskerClass
from MWATools.MWAInterface import interface
from MWATools.MWATaskPipeline import MWATaskPipelineClass
from MWATools.MWAConfig import MWAConfig


from PyPipeline.CustomActions.Start import StartApp
from PyPipeline.CustomActions.Return import Return
from PyPipeline.CustomActions.OpenRecruitment import OpenRecruitment

from PyPipeline.CustomRecos.PopUpRecognition import PopUpRecognition

# todo: 任务列表，从配置文件读取，如果没有相关配置则在第一次添加任务时生成配置文件，后续更换则更新配置文件

MWAResource = MWAResourceClass()


@MWAResource.resource.custom_action("StartApp")
class StartApp(StartApp):
    ...

@MWAResource.resource.custom_action("Return")
class Return(Return):
    ...

@MWAResource.resource.custom_action("OpenRecruitment")
class OpenRecruitment(OpenRecruitment):
    ...

@MWAResource.resource.custom_recognition("PopUpRecognition")
class PopUpRecognition(PopUpRecognition):
    ...
if __name__ == '__main__':
    MWAConfig.generate_Alcove_config(adb_path="adb", address="127.0.0.1:5037")
    print(MWAConfig.read_Alcove_resource())
    # try:
    #     pipeline_override = {
    #         "MyCustomEntry": {"action": "custom", "custom_action": "StartApp"},
    #     }
    #     MWAController = MWAControllerClass()
    #     MWAController.load_controller()
    #     MWAController.choose_adb_controller()

    #     MWATasker = MWATaskerClass()

    #     adb_controller = MWAController.connect_adb_controller()
    #     MWATasker.MWATaskerBind(controller=adb_controller, resource=MWAResource.resource)
    #     # task_detail = MWATasker.run_action("MyCustomEntry", pipeline_override)
    #     reco_pipeline_override = {
    #         "MyCustomReco": {"recognition":"custom", "custom_recognition":"PopUpRecognition"},
    #     }
    #     reco_detail = MWATasker.run_custom_recognition("MyCustomReco", pipeline_override=reco_pipeline_override)
    #     print("识别结果：", reco_detail)
        # MWATaskPipelineClass = MWATaskPipelineClass()
        # print(MWATaskPipelineClass.add_pipeline('启动'))
        # print(MWATaskPipelineClass.add_pipeline('器者征集',True))
    # except KeyboardInterrupt:
    #     # 捕获Ctrl+C触发的异常
    #     print("\n检测到Ctrl+C，程序将取消并退出")
    #     MWATasker.Tasker.stopping()
        # 可选：在这里添加退出前的清理操作（如关闭文件、释放资源等）
        # 程序会在except块执行完后自动退出