from MWATools.MWAInterface import interface

import json


class MWAReadTaskClass:
    def __init__(self):
        # 用来显示任务列表
        self.tasks = [task['name'] for task in interface['task']]
        # 实际需要用到的任务名
        self.tasknames = {task['name'] : task for task in interface['task']}


        self.options = []
        self.option_entry = []

    def get_task_entry(self, task_name: str) -> str:
        if task_name not in self.tasks:
            return None
        self.entry = self.tasknames[task_name]['entry']
        return self.entry
    
    def get_task_options(self, task_name: str) -> list:
        if task_name not in self.tasks or not "option" in self.tasknames[task_name]:
            return None
        self.options = self.tasknames[task_name]['option']
        return self.options
    
    def get_task_option_entry(self, options: list = None) -> str:
        self.option_entry = interface['option']
        if self.option_entry:
            return [name for name in self.option_entry.keys()]
    




if __name__ == '__main__':
    MWAReadTaskClass = MWAReadTaskClass()
    # print(MWAReadTaskClass.get_task_entry('启动'))
    # print(MWAReadTaskClass.get_task_options('启动'))
    # print(MWAReadTaskClass.tasks)
    # print(MWAReadTaskClass.tasknames)
    print(MWAReadTaskClass.get_task_options("启动"))
    print(MWAReadTaskClass.get_task_option_entry())