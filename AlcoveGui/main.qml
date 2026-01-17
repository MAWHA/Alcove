import QtQuick      
import QtQuick.Layouts      
import HuskarUI.Basic      
import QtQuick.Controls.Basic      
        
HusWindow {      
    width: 800      
    height: 600
    property string currentSource: "home/HomePage.qml"  // 初始页面  
    
    function switchToPage(source) {      
        if (currentSource !== source) {      
            currentSource = source      
            pageLoader.source = source      
        }      
    }      
    
    // 背景色      
    Rectangle {      
        anchors.fill: content      
        color: HusTheme.isDark ? '#181818' : '#f5f5f5'      
        opacity: 0.2      
    }      
          
    // 左侧菜单区域      
    HusMenu {      
        id: leftMenu      
        anchors.left: parent.left      
        anchors.top: parent.top      
        anchors.bottom: parent.bottom      
        width: 200      
        showEdge: true      
        y: 80
        initModel: [      
            { key: 'home', label: '首页', source: 'home/HomePage.qml', iconSource: HusIcon.HomeOutlined },      
            { key: 'settings', label: '设置', source: 'settings/SettingsPage.qml', iconSource: HusIcon.SettingOutlined },      
            { key: 'about', label: '关于', source: 'about/AboutPage.qml', iconSource: HusIcon.UserOutlined }      
        ]      
              
        onClickMenu: function(deep, key, keyPath, data) {      
            if (data && data.source) {      
                switchToPage(data.source)      
            }      
        }      
    }      
          
    // 主内容区域      
    Item {      
        anchors.left: leftMenu.right      
        anchors.right: parent.right      
        anchors.top: parent.top      
        anchors.bottom: parent.bottom      
        anchors.margins: 20      
              
        // 标题文本      
        HusText {      
            id: titleText      
            anchors.top: parent.top      
            anchors.horizontalCenter: parent.horizontalCenter      
            text: "Alcove"      
            font.pixelSize: 24      
            font.weight: Font.DemiBold      
        }      
    
        // 页面加载器      
        Loader {      
            id: pageLoader      
            anchors.left: parent.left      
            anchors.right: parent.right      
            anchors.top: titleText.bottom      
            anchors.bottom: parent.bottom      
            anchors.topMargin: 20      
            source: currentSource  
        }    
    }      
}