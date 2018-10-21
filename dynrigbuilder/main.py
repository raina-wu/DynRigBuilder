__author__ = 'wuxiaoyu'
from maya import OpenMayaUI as omui
import pymel.core as pm

from Qt.QtCore import *
from Qt.QtGui import *
from Qt.QtWidgets import *

try:
    from shiboken import wrapInstance
except:
    from shiboken2 import wrapInstance

import dynrigbuilderui
import splinerig
import scaffold

map(reload,[splinerig, scaffold, dynrigbuilderui])


mayaMainWindowPtr = omui.MQtUtil.mainWindow()
mayaMainWindow = wrapInstance(long(mayaMainWindowPtr), QWidget)


_win = None
def show():
    global _win
    if _win == None:
        _win = DynRigBuilderUI()
    _win.show()

class DynRigBuilderUI(QWidget):

    def __init__(self, *args, **kwargs):
        super(DynRigBuilderUI, self).__init__(*args, **kwargs)

        # Parent widget under Maya main window
        self.setParent(mayaMainWindow)
        self.setWindowFlags(Qt.Window)

        # Set the object name
        self.setObjectName('DynRigBuilderUI_uniqueId')
        self.setWindowTitle('DynRigBuilder')

        self._scaffold = None
        self._rig = None
        self._initUI()

    def _initUI(self):
        self.ui = dynrigbuilderui.Ui_Form()
        self.ui.setupUi(self)

        self._updateUI()

        # set validators
        self.ui.lineEdit_prefix.setValidator(QRegExpValidator(QRegExp("[A-Za-z]+[0-9]+")))
        self.ui.lineEdit_jntNum.setValidator(QIntValidator(1, 100))
        self.ui.lineEdit_fkCtrlNum.setValidator(QIntValidator(1, 100))
        self.ui.lineEdit_masterCtrlNum.setValidator(QIntValidator(1, 100))
        self.ui.lineEdit_ibtCtrlNum.setValidator(QIntValidator(1, 100))

        # connect signals and slots
        self.ui.pushButton_buildLayout.clicked.connect(self._buildLayout)
        self.ui.lineEdit_jntNum.editingFinished.connect(self._setJointNum)
        self.ui.pushButton_buildRig.clicked.connect(self._buildRig)

        # ik
        self.ui.groupBox_ik.toggled.connect(self._setIK)
        self.ui.lineEdit_masterCtrlNum.editingFinished.connect(self._setMasterCtrlNum)
        self.ui.lineEdit_ibtCtrlNum.editingFinished.connect(self._setIbtCtrlNum)
        self.ui.checkBox_psvVolume.stateChanged.connect(self._setPreserveVolume)
        self.ui.checkBox_psvLength.stateChanged.connect(self._setPreserveLength)

        # fk
        self.ui.groupBox_fk.toggled.connect(self._setFK)
        self.ui.comboBox_fkType.currentIndexChanged.connect(self._setFKType)
        self.ui.lineEdit_fkCtrlNum.editingFinished.connect(self._setFKCtrlNum)

        # dynamic
        self.ui.groupBox_dynamic.toggled.connect(self._setDynamic)

    def _updateUI(self):
        if self._scaffold:
            self.ui.lineEdit_jntNum.setText(str(self._scaffold.jointNum.get()))

            # ik
            self.ui.groupBox_fk.setChecked(self._scaffold.hasFK.get())
            self.ui.comboBox_fkType.setCurrentIndex(self._scaffold.fkType.get())
            self.ui.lineEdit_fkCtrlNum.setText(str(self._scaffold.fkCtrlNum.get()))

            # fk
            self.ui.groupBox_ik.setChecked(self._scaffold.hasIK.get())
            self.ui.lineEdit_masterCtrlNum.setText(str(self._scaffold.masterCtrlNum.get()))
            self.ui.lineEdit_ibtCtrlNum.setText(str(self._scaffold.ibtSubCtrlNum.get()))
            self.ui.checkBox_psvVolume.setCheckState(Qt.Checked if self._scaffold.preserveVolume.get() else Qt.Unchecked)
            self.ui.checkBox_psvLength.setCheckState(Qt.Checked if self._scaffold.preserveLength.get() else Qt.Unchecked)

            # dynamics
            self.ui.groupBox_dynamic.setChecked(self._scaffold.hasDynamic.get())

        self.ui.comboBox_hairSystem.clear()
        self.ui.comboBox_hairSystem.addItem("New")
        hairSystems = pm.ls(type="hairSystem")
        for hairSys in hairSystems:
            self.ui.comboBox_hairSystem.addItem(hairSys.name())


    def _buildLayout(self):
        if not self._rig:
            prefix = self.ui.lineEdit_prefix.text()
            if not prefix:
                msgBox = QMessageBox()
                msgBox.setText("Please enter the prefix.")
                msgBox.exec_()
                return
            if scaffold.doesScaffoldExist(prefix):
                self._scaffold = scaffold.getScaffoldTop(prefix)[0]
            else:
                self._scaffold = splinerig.SplineRig.buildScaffoldChain(prefix)

            self._updateUI()

    def _buildRig(self):
        prefix = self.ui.lineEdit_prefix.text()
        oldRig = splinerig.SplineRig.rigExists(prefix)
        if oldRig:
            msgBox = QMessageBox()
            msgBox.setText("Rig with the same prefix already exists. Delete and rebuild?")
            msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            msgBox.setDefaultButton(QMessageBox.Ok)
            ret = msgBox.exec_()
            if ret == QMessageBox.Ok:
                splinerig.SplineRig.deleteRig(oldRig)
            else:
                return
        splineRig = splinerig.SplineRig(prefix)

        try:
            hairSystem = pm.PyNode(self.ui.comboBox_hairSystem.currentText())
        except:
            hairSystem = None
        splineRig.buildRig(self._scaffold, hairSystem)
        self._updateUI()


    def _setJointNum(self):
        if self._scaffold:
            try:
                self._scaffold.jointNum.set(int(self.ui.lineEdit_jntNum.text()))
            except:
                self.ui.lineEdit_jntNum.setText(str(self._scaffold.jointNum.get()))
                return

    def _setFK(self, checked):
        print self._scaffold, checked
        if self._scaffold:
            self._scaffold.hasFK.set(checked)

    def _setFKType(self, index):
        if self._scaffold:
            self._scaffold.fkType.set(index)

    def _setFKCtrlNum(self):
        if self._scaffold:
            try:
                self._scaffold.fkCtrlNum.set(int(self.ui.lineEdit_fkCtrlNum.text()))
            except:
                self.ui.lineEdit_fkCtrlNum.setText(str(self._scaffold.fkCtrlNum.get()))
                return

    def _setIK(self, checked):
        if self._scaffold:
            self._scaffold.hasIK.set(checked)

    def _setMasterCtrlNum(self):
        if self._scaffold:
            try:
                self._scaffold.masterCtrlNum.set(int(self.ui.lineEdit_masterCtrlNum.text()))
            except:
                self.ui.lineEdit_masterCtrlNum.setText(str(self._scaffold.masterCtrlNum.get()))
                return

    def _setIbtCtrlNum(self):
        if self._scaffold:
            try:
                self._scaffold.ibtSubCtrlNum.set(int(self.ui.lineEdit_ibtCtrlNum.text()))
            except:
                self.ui.lineEdit_ibtCtrlNum.setText(str(self._scaffold.ibtSubCtrlNum.get()))
                return

    def _setPreserveVolume(self, state):
        self._scaffold.preserveVolume.set(True if state == Qt.Checked else False)

    def _setPreserveLength(self, state):
        self._scaffold.preserveLength.set(True if state == Qt.Checked else False)

    def _setDynamic(self, checked):
        if self._scaffold:
            self._scaffold.hasDynamic.set(checked)

