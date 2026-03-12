from MWATools.MWAController import MWAControllerClass
from MWATools.MWAResource import MWAResourceClass
from MWATools.MWATasker import MWATaskerClass
from MWATools.MWAInterface import interface
from MWATools.MWATaskPipeline import MWATaskPipelineClass
from MWATools.MWAConfig import MWAConfig

from maa.custom_action import CustomAction
from maa.context import Context
from maa.pipeline import JRecognitionType, JOCR

from PyPipeline.CustomActions.Start import StartApp
from PyPipeline.CustomActions.Return import Return
from PyPipeline.CustomActions.OpenRecruitment import OpenRecruitment


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
@MWAResource.resource.custom_action("test")
class Test(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        detail = context.run_recognition_direct(JRecognitionType.OCR, 
                                    JOCR(
                                        expected="招集",  # 期望识别的文本列表
                                        # roi=[100, 50, 200, 80]  # 识别区域：x=100, y=50, 宽200, 高80
                                        ),
                                    image=context.tasker.controller.post_screencap().wait().get())
        print(detail)
        return True

if __name__ == '__main__':
    pipeline_override = {
        "MyCustomEntry": {"action": "custom", "custom_action": "test"},
    }
    MWAController = MWAControllerClass()
    MWAController.load_controller()
    MWAController.choose_adb_controller()
    MWATasker = MWATaskerClass()
    adb_controller = MWAController.connect_adb_controller()
    MWATasker.MWATaskerBind(controller=adb_controller, resource=MWAResource.resource)

    reco_detail = MWATasker.run_custom_recognition("MyCustomEntry", pipeline_override=pipeline_override)
    print(reco_detail)