from PySide2 import QtCore, QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya import OpenMaya
from maya import OpenMayaUI
from shiboken2 import wrapInstance
import sys

class DimensionEditorWindow(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    
    def __init__(self, parent=None):
        #call the baseclass constructor
        super(DimensionEditorWindow, self).__init__(parent=parent)
        
        #Kill any still-living instances to prevent doubles.
        self.ClosePreviousInstances();
        
        #--Window properties:
        self.setDockableParameters(dockable=True)
        self.setWindowTitle("Dimension Editor")
        #delete itself when you close the window to prevent spooky ghost windows from haunting your maya session.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        
        #--Event ID declarations
        self.selectionEvent = OpenMaya.MEventMessage.addEventCallback("SelectionChanged", self.OnSelectionChanged) #To handle a change in the selection
        QtWidgets.QApplication.instance().focusChanged.connect(self.OnFocusChanged) #To apply the changes when a field loses focus
        self.SJUnit = cmds.scriptJob(e=["linearUnitChanged", self.OnUnitChanged]) #ID for the unit change scriptJob
        self.SJScaleX = -1 #IDs for the scale change scriptJobs
        self.SJScaleY = -1
        self.SJScaleZ = -1
        self.SJConnectX = -1 #IDs for the connection change scriptJobs
        self.SJConnectY = -1
        self.SJConnectZ = -1
        self.currentActive = "" #Keep track of the object currently active (last selected)
        
        #prepare the widgets
        mainWidget = QtWidgets.QWidget()
        mainLayout = QtWidgets.QHBoxLayout()
        
        self.noSelectionLabel = QtWidgets.QLabel("Nothing is selected")
        self.noSelectionLabel.hide();
        mainLayout.addWidget(self.noSelectionLabel)

        self.xField = self.BuildDimensionInput("W: ", mainLayout)
        self.yField = self.BuildDimensionInput("H: ", mainLayout)
        self.zField = self.BuildDimensionInput("D: ", mainLayout)
        
        mainWidget.setLayout(mainLayout)
        self.setCentralWidget(mainWidget)
        
        #Run these once to set up initial values.
        self.OnSelectionChanged(None)
        self.OnUnitChanged()
        self.LockInputs()
        self.resize(self.minimumSizeHint())
        
    #Function to build one of the dimension inputs
    def BuildDimensionInput(self, labelText, outputLayout):
        label = QtWidgets.QLabel(labelText)
        inputBox = QtWidgets.QDoubleSpinBox()
        inputBox.setRange(sys.float_info.min, sys.float_info.max)
        inputBox.setDecimals(2)
        inputBox.setMinimumWidth(70)
        inputBox.setMaximumWidth(250)
        inputBox.label = label
        outputLayout.addWidget(label)
        outputLayout.addWidget(inputBox)
        return inputBox
    
    #-- Event handlers:    
    #To handle when field lose focus. Changes are applies at this time.
    def OnFocusChanged(self, previousFocus, currentFocus):
        if self.xField is previousFocus:
            self.ApplyValue('x', self.xField.value())
        elif self.yField is previousFocus:
            self.ApplyValue('y', self.yField.value())
        elif self.zField is previousFocus:
            self.ApplyValue('z', self.zField.value())
    
    #To handle a change in selection
    def OnSelectionChanged(self, args):
        selected = cmds.ls(sl=1, transforms=1)
        if not selected or not cmds.listRelatives(selected[-1], shapes=True): #Happens when nothing is selected or the selected transform doesn't have any shape nodes.
            self.HideInputs()
            self.EndAttributeScriptjobs()
            self.currentActive = ""
        else: #Happens when something is selected. Works on the active element
            self.currentActive = selected[-1]
            self.ShowInputs()
            self.UpdateValues()
            self.LockInputs()
            self.SJScaleX = cmds.scriptJob(attributeChange=[self.currentActive+".sx", self.UpdateValues])
            self.SJScaleY = cmds.scriptJob(attributeChange=[self.currentActive+".sy", self.UpdateValues])
            self.SJScaleZ = cmds.scriptJob(attributeChange=[self.currentActive+".sz", self.UpdateValues])
            self.SJConnectX = cmds.scriptJob(connectionChange=[self.currentActive+".sx", self.LockInputs])
            self.SJConnectY = cmds.scriptJob(connectionChange=[self.currentActive+".sy", self.LockInputs])
            self.SJConnectZ = cmds.scriptJob(connectionChange=[self.currentActive+".sz", self.LockInputs])
    
    #Fires when the user changes the linear scene unit in settings.
    def OnUnitChanged(self):
        fields = [self.xField, self.yField, self.zField]
        for field in fields:
            field.setSuffix(" " + cmds.currentUnit(query=True, l=True)) #Change the suffix to the current unit.
        if not self.currentActive == "":
            self.UpdateValues() #Update the values to the new unit.
    
    #-- Data management functions:
    #Update the values displayed in the fields.
    def UpdateValues(self):
        if not self.currentActive == "":
            size = self.GetUntransformedSize(self.currentActive)
            xSize = size[0] * cmds.getAttr(self.currentActive+".sx")
            ySize = size[1] * cmds.getAttr(self.currentActive+".sy")
            zSize = size[2] * cmds.getAttr(self.currentActive+".sz")
            self.xField.setValue(xSize)
            self.yField.setValue(ySize)
            self.zField.setValue(zSize)
    
    #Apply the values from the fields to the object's scale attributes.
    def ApplyValue(self, axis, value):
        if not self.currentActive == "":
            #Match a number to each axis for easy matching later.
            axisv = 0;
            if axis == "y": axisv = 1
            elif axis == "z": axisv = 2
        
            attribute = self.currentActive+".s"+axis
            size = self.GetUntransformedSize(self.currentActive)
            baseSize = size[axisv]
            
            newScale = value/baseSize
            cmds.setAttr(attribute, newScale)
    
    #Utility to get the size of the shape node without any transforms applied to it.
    def GetUntransformedSize(self, object):
        mSelectionList = OpenMaya.MSelectionList()
        mSelectionList.add(object)
        
        selectedPath = OpenMaya.MDagPath()
        mSelectionList.getDagPath(0, selectedPath)
        
        transform = OpenMaya.MFnTransform(selectedPath)
        matrix = transform.transformationMatrix()
        
        selectedPath.extendToShape()
        fnMesh = OpenMaya.MFnMesh(selectedPath)
        bounds = fnMesh.boundingBox()
        
        min = bounds.min()
        max = bounds.max()
        
        xsize = max.x - min.x
        ysize = max.y - min.y
        zsize = max.z - min.z
        
        return xsize, ysize, zsize
    
    #Stopping scriptjobs.
    def EndAttributeScriptjobs(self):      
        if self.SJScaleX > 0:
            cmds.scriptJob(kill=self.SJScaleX)
            self.SJScaleX = -1
            
        if self.SJScaleY > 0:
            cmds.scriptJob(kill=self.SJScaleY)
            self.SJScaleY = -1
            
        if self.SJScaleZ > 0:
            cmds.scriptJob(kill=self.SJScaleZ)
            self.SJScaleZ = -1
            
        if self.SJConnectX > 0:
            cmds.scriptJob(kill = self.SJConnectX)
            self.SJConnectX = -1
            
        if self.SJConnectY > 0:
            cmds.scriptJob(kill = self.SJConnectY)
            self.SJConnectY = -1
            
        if self.SJConnectZ > 0:
            cmds.scriptJob(kill = self.SJConnectZ)
            self.SJConnectZ = -1
    
    #-- Widget management functions:
    #Hide the input fields
    def HideInputs(self):
        fields = [self.xField, self.yField, self.zField]
        for field in fields:
            field.hide()
            field.label.hide()
        self.noSelectionLabel.show()
    
    #Show the input fields again.
    def ShowInputs(self):
        fields = [self.xField, self.yField, self.zField]
        for field in fields:
            field.show()
            field.label.show()
        self.noSelectionLabel.hide()
    
    def LockInputs(self):
        if not self.currentActive == "":
            for(field, attribute) in zip([self.xField, self.yField, self.zField], ["sx","sy","sz"]):
                connections = cmds.listConnections(self.currentActive+"."+attribute)
                if connections:
                    field.setDisabled(True)
                else:
                    field.setDisabled(False)
    
    #-- Cleanup functions:
    #Function for closing previous instances that are still open.
    def ClosePreviousInstances(self):
        mayaWindowPointer = OpenMayaUI.MQtUtil.mainWindow()
        mayaWindow = wrapInstance(int(mayaWindowPointer), QtWidgets.QMainWindow)
        
        children = mayaWindow.findChildren((QtWidgets.QMainWindow))
        for child in children:
            if child.objectName().startswith("DimensionEditorWindow_"):
                child.close()
                
    #Cleanup after itself.
    def DockCloseEventTriggered(self):
        OpenMaya.MMessage.removeCallback(self.selectionEvent)
        QtWidgets.QApplication.instance().focusChanged.disconnect()
        self.EndAttributeScriptjobs()
        cmds.scriptJob(kill=self.SJUnit)
        
#Actually create the window
if __name__== '__main__':
    w = DimensionEditorWindow()
    w.show()