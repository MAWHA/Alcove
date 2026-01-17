from PySide6.QtGui import QGuiApplication  
from PySide6.QtQml import QQmlApplicationEngine  
from pyhuskarui.husapp import HusApp  
from ADBController import ADBController

app = QGuiApplication([])  
engine = QQmlApplicationEngine()  
  
engine.singletonInstance("HuskarUI.Basic", "HusApp")  
engine.singletonInstance("ADBController", "ADBController")  
engine.singletonInstance("MWAADB", "MWAADB")  
engine.load("./AlcoveGui/main.qml")
app.exec()