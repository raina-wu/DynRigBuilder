__author__ = 'wuxiaoyu'

import pymel.core as pm
import mayautils
import rigutils
import scaffold

map(reload, [mayautils, scaffold, rigutils])

class SplineRig(object):

    scaffoldType = "spline"
    scaffoldChain = {"start":[0,15,0], "end":[0,0,0]}
    rigAttrs = [
        {"ln":"jointNum", "at": "long", "dv":20, "min":2},
        {"ln":"hasFK", "at": "bool", "dv":True},
        {"ln":"fkType", "at": "long", "dv":0, "min":0, "max":1},
        {"ln":"fkCtrlNum", "at": "long", "dv":5, "min":1},
        {"ln":"hasIK", "at": "bool", "dv":True},
        {"ln":"masterCtrlNum", "at": "long", "dv":5, "min":3},
        {"ln":"ibtSubCtrlNum", "at": "long", "dv":1, "min":0},
        {"ln":"preserveVolume", "at": "bool", "dv":True},
        {"ln":"preserveLength", "at": "bool", "dv":True},
        {"ln":"hasDynamic", "at": "bool", "dv":True}
    ]
    RIG_TOP_TAG = "rigTop"

    def __init__(self, prefix):
        super(SplineRig, self).__init__()
        self.prefix = prefix

        for attr in self.rigAttrs:
            setattr(self, attr["ln"], attr["dv"])
        self.startPos = self.scaffoldChain["start"]
        self.endPos = self.scaffoldChain["end"]
        self.metaPos = self.startPos

    def _getAttrFromScaffold(self, scaffoldTop):
        if scaffold.getScaffoldType(scaffoldTop) != "spline":
            return
        for attr in self.rigAttrs:
            setattr(self, attr["ln"], pm.getAttr("{0}.{1}".format(scaffoldTop,
                                                                  attr["ln"])))
        scaffLocs = scaffold.getScaffoldLocs(scaffoldTop)
        self.startPos = scaffold.getLocPosition(scaffLocs[0])
        self.endPos = scaffold.getLocPosition(scaffLocs[-1])
        self.metaPos = scaffold.getMetaPivotPosition(scaffoldTop)

    def _cleanUp(self):
        pass

    def _buildBaseCtrls(self):
        # create global ctrl
        self.globalCtrl = mayautils.createCtrl("{0}_all_ctrl".format(self.prefix), "crossArrow", 1, "yellow")
        globalCtrlAttr = [
            {"ln":"globalScale", "at":"float", "dv":1, "k":1},
            {"ln":self.RIG_TOP_TAG, "dt":"string"}
        ]
        mayautils.addAttributes(self.globalCtrl, globalCtrlAttr)

        # create meta ctrl
        self.metaCtrl = mayautils.createCtrl("{0}_meta_ctrl".format(self.prefix), "fatCross", 1, "yellow", None, [0,0,90])
        pm.xform(self.metaCtrl, t=self.metaPos, ws=1)
        mayautils.aimObject(self.endPos, self.metaCtrl)
        mayautils.createParentTransform("org", self.metaCtrl).setParent(self.globalCtrl)

        # build globalScale connections
        for ch in 'xyz':
            pm.connectAttr(self.globalCtrl.globalScale, "{0}.s{1}".format(self.metaCtrl.name(), ch))
            pm.setAttr("{0}.s{1}".format(self.metaCtrl.name(), ch), cb=0, keyable=0, lock=1)
            pm.setAttr("{0}.s{1}".format(self.globalCtrl.name(), ch), cb=0, keyable=0, lock=1)

    def buildRig(self, scaffoldTop, hairSystem=None):
        if scaffoldTop:
            self._getAttrFromScaffold(scaffoldTop)

        # build base ctrls
        self._buildBaseCtrls()

        # build base joints
        baseJnts = rigutils.buildJointChain(self.prefix,"base_jnt",self.startPos,self.endPos,self.jointNum)
        baseJntGrp = pm.group(baseJnts[0], n="{0}_base_grp".format(self.prefix))
        baseJntGrp.setParent(self.metaCtrl)

        # build ik/fk systems
        ikTop = None
        if self.hasIK:
            ikTop = self._buildIKSystem()

        fkTop = None
        if self.hasFK:
            fkTop = self._buildVariableFKSystem(baseJnts)

        if ikTop and fkTop:
            # build ikfk switch
            ikfkAttrs = [
                {"ln":"ikfkSwitch", "at":"float", "dv":0, "min":0, "max":1, "cb":1},
                {"ln":"ikfkSwitchRev", "at":"float", "dv":1, "min":0, "max":1}
            ]
            mayautils.addAttributes(self.globalCtrl, ikfkAttrs)
            ikfkRev = pm.createNode("reverse", n="{0}_ikfk_rev".format(self.prefix))
            self.globalCtrl.ikfkSwitch.connect(ikfkRev.inputX)
            ikfkRev.outputX.connect(self.globalCtrl.ikfkSwitchRev)

            # connect ctrl visibility
            fkCtrls = fkTop.ctrl.get()
            ikCtrls = ikTop.ctrl.get()
            for ikCtrl in ikCtrls:
                self.globalCtrl.ikfkSwitchRev.connect(ikCtrl.getShape().visibility)
            for fkCtrl in fkCtrls:
                self.globalCtrl.ikfkSwitch.connect(fkCtrl.getShape().visibility)

            # joint blend
            fkJnts = fkTop.resultJnt.get()
            ikJnts = ikTop.resultJnt.get()
            for i in range(self.jointNum):
                parCst = pm.parentConstraint(fkJnts[i], ikJnts[i], baseJnts[i], mo=0)
                weightAttrs = pm.parentConstraint(parCst, q=1, wal=1)
                self.globalCtrl.ikfkSwitch.connect(weightAttrs[0])
                self.globalCtrl.ikfkSwitchRev.connect(weightAttrs[1])
                scb = pm.createNode("blendColors", n="{0}_{1:0>2d}_s_cb".format(self.prefix, i))
                fkJnts[i].scale.connect(scb.color1)
                ikJnts[i].scale.connect(scb.color2)
                scb.output.connect(baseJnts[i].scale)
                self.globalCtrl.ikfkSwitch.connect(scb.blender)

        elif ikTop or fkTop:
            retJnts = fkTop.resultJnt.get() if fkTop else ikTop.resultJnt.get()
            for i in range(self.jointNum):
                pm.parentConstraint(retJnts[i], baseJnts[i], mo=0)
                retJnts[i].scale.connect(baseJnts[i].scale)

        dynTop = None
        # build dynamic system
        if self.hasDynamic:
            dynAttrs = [
                {"ln":"dynamicSwitch", "at":"bool", "dv":1, "k":1, "cb":1},
                {"ln":"animationBlend", "at":"float", "dv":0, "k":1, "min":0, "max":1}
            ]
            mayautils.addAttributes(self.globalCtrl, dynAttrs)
            dynTop = self._buildDynamicSystem(baseJnts, hairSystem)

        # mark influence joints
        infJnts = dynTop.resultJnt.get() if dynTop else baseJnts
        for i, jnt in enumerate(infJnts):
            jnt.rename(jnt.name()+"_inf")



    def _buildDynamicSystem(self, joints, hairSystem=None):
        return rigutils.buildDynamicSystem(self.prefix, joints, self.metaCtrl, hairSystem)

    def _buildIKSystem(self):
        return rigutils.buildIKSystem(self.prefix, self.startPos, self.endPos,
                              self.masterCtrlNum, self.ibtSubCtrlNum,
                              self.jointNum, self.metaCtrl, self.preserveVolume,
                              self.preserveLength, self.globalCtrl.globalScale)

    def _buildRegularFKSystem(self, joints):
        pass

    def _buildVariableFKSystem(self, joints):
        return rigutils.buildVariableFKSystem(joints, self.prefix,
                                              self.fkCtrlNum, self.metaCtrl)

    @classmethod
    def buildScaffoldChain(rig, prefix):
        scaffoldTop = scaffold.buildScaffoldChain(prefix, rig.scaffoldChain)

        # add rig attrs to scaffold attributes
        scaffold.setScaffoldType(scaffoldTop, rig.scaffoldType)
        mayautils.addAttributes(scaffoldTop, rig.rigAttrs)
        return scaffoldTop

    @classmethod
    def rigExists(rig, prefix):
        return pm.ls("{0}*.{1}".format(prefix, rig.RIG_TOP_TAG), o=1)

    @staticmethod
    def deleteRig(rigTop):
        pm.delete(rigTop)