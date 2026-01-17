import QtQuick  
import HuskarUI.Basic  
import ADBController 1.0

Item {
    id: rootItem

    Component.onCompleted: {
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
                    { text: "扫描ADB设备", label: "扫描ADB设备", type: HusButton.Type_Outlined},  
                    { text: "连接ADB设备", label: "连接ADB设备", type: HusButton.Type_Filled}  
                ]
                radiusBg.all: adbPathInput.radiusBg.all
                radiusBg.topLeft: 0
                radiusBg.bottomLeft: 0

                onClicked: {
                    var itemText = model[index].text  
                    if (itemText == "扫描ADB设备") {  
                        console.log("扫描ADB设备（点击按钮）");
                        // 先判断ADBController是否可用，避免调用失败
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
        HusText {
            text: "资源路径"
            font.pixelSize: 20  
        }
        HusInput {
            width: 595
            placeholderText: "请输入资源路径"
            active: false
        }
    }    
}