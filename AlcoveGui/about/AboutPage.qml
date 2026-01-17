import QtQuick  
import HuskarUI.Basic  
  
Item {  // ✅ 使用 Item，不是 HusWindow  
    Column {  
        anchors.centerIn: parent  
        spacing: 20  
          
        HusText {  
            text: "关于页面"  
            font.pixelSize: 20  
        }  
          
        HusText {  
            text: "版本信息: 1.0.0"  
        }  
    }  
}