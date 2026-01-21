import QtQuick
import QtQuick.Controls 6.2
import QtQml 2.15
import QtQuick.Dialogs

import HuskarUI.Basic  

import ADBController 1.0
import ConfigRead
Item {
    id: rootItem
    property string selectedPath: ""
    Component.onCompleted: {
        if (ConfigRead && ConfigRead.ResourceSignal) {
            ConfigRead.ResourceSignal.connect(function(resources_path){
                console.log("QML接收resources路径：", resources_path);
                resourcePathInput.text = resources_path
            });
        }
        if (ADBController && ADBController.ADBSignal) {
            ADBController.ADBSignal.connect(function(devices_adb_paths) {
                var deviceList = JSON.parse(devices_adb_paths);
                if (deviceList.length > 0) {
                    var firstDeviceAdbPath = deviceList[0].adb_path;
                    adbPathInput.text = firstDeviceAdbPath;
                    var firstDeviceAddress = deviceList[0].adb_address;
                    adbAddressInput.text = firstDeviceAddress;
                }
            });
        } else {
            console.error("===== 信号绑定失败：ADBController或progressSignal不存在 =====");
        }
        if (ADBController && ADBController.ConnectADBSignal) {
            ADBController.ConnectADBSignal.connect(function(status) {
                console.log("QML接收ADB连接状态：", status);
            });
        } else {
            console.error("===== 信号绑定失败：ADBController或progressSignal不存在 =====");
        }
    }

    Column {  
        anchors.centerIn: parent  
        spacing: 20
       
        Column{
            HusText {
                text: "资源路径"
                font.pixelSize: 20
            }
            Row {
                HusInput {
                    id: resourcePathInput
                    width: 345
                    height: 30
                    placeholderText: "请输入资源路径"
                    radiusBg.topRight: 0
                    radiusBg.bottomRight: 0
                }
                HusButton{
                    text: "选择资源路径"  
                    type: HusButton.Type_Filled
                    onClicked: {
                        fileDialog.open()
                    }
                    radiusBg.all: resourcePathInput.radiusBg.all
                    radiusBg.topLeft: 0
                    radiusBg.bottomLeft: 0
                }
                FileDialog {
                    id: fileDialog
                    title: "选择文件"
                    nameFilters: ["yaml配置文件(*.yaml)"]
                    onAccepted: {
                        console.log("选择的文件: " + fileDialog.selectedFile)
                        if (ConfigRead) {
                            ConfigRead.get_resource();
                        }
                    }
                    onRejected: {
                        console.log("取消选择")
                    }
                    }
                }
        }
         HusText {
            text: "ADB路径"
            font.pixelSize: 20  
        }
        Row{
            HusInput {
                id: adbPathInput
                width: 345
                height: connectAndScanBtn.height
                placeholderText: "请输入ADB路径，例：C:/path/to/adb.exe"
                radiusBg.topRight: 0
                radiusBg.bottomRight: 0
            }

            HusButtonBlock{
                id: connectAndScanBtn
                model: [  
                    { text: "扫描ADB设备", label: "扫描ADB设备", type: HusButton.Type_Filled},  
                    { text: "连接ADB设备", label: "连接ADB设备", type: HusButton.Type_Filled}  
                ]
                radiusBg.all: adbPathInput.radiusBg.all
                radiusBg.topLeft: 0
                radiusBg.bottomLeft: 0

                onClicked: {
                    var itemText = model[index].text  
                    if (itemText == "扫描ADB设备") {  
                        console.log("扫描ADB设备（点击按钮）");
                        if (ADBController) {
                            ADBController.find_adb_controller();
                        } else {
                            console.error("ADBController未定义，无法调用扫描方法");
                        }
                    } else if (itemText == "连接ADB设备") {  
                        ADBController.connect_adb_controller(adbPathInput.text, adbAddressInput.text);
                    }
                }
            }
        }
        Row {
            HusText {
            text: "address:"
            font.pixelSize: 20
            }

            HusInput {
                id: adbAddressInput
                width: 150
                placeholderText: "请输入ADB地址"
            }
        }
    }    
}