import QtQuick  
import HuskarUI.Basic  
  
Item {  // ✅ 使用 Item，不是 HusWindow  
    Column {  
        anchors.centerIn: parent  
        spacing: 20  
          
        HusText {  
            text: "首页内容"  
            font.pixelSize: 20  
        }  
          
        HusButtonBlock {  
            model: [  
                { text: "按钮1", iconSource: HusIcon.HomeOutlined },  
                { text: "按钮2", iconSource: HusIcon.SettingOutlined }  
            ]  
        }  
    }
}