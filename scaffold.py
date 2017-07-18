__author__ = 'wuxiaoyu'

import pymel.core as pm
import utils

class Scaffold(object):

    def __init__(self, prefix, scaffoldChainDict):
        self.joints = []
        self.locCtrls = []
        self.pivots = []
        self.scaffoldChainDic = scaffoldChainDict
        self.prefix = prefix


    @property
    def joints(self):
        return self.joints

    @property
    def locCtrls(self):
        return self.locCtrls


    def buildScaffoldChain(self, prefix, scaffoldChainDict):
        """
        Build a basic scaffold chain
        :param prefix: `string` scaffold chain prefix. eg."tail"
        :param scaffoldChainDict:`dict`
            dictionary that defines the chain structure.
            chain locator prefix: chain locator world position
            example: {"base": [0,0,0], "end":[3,-6,7]}
        :return: `PyNode` scaffold chain top group
        """
        scaffLocColor = 13
        scaffEndLocColor = 6
        scaffPivColor = 17

        # create group hierarchy
        scaffoldChainGrp = pm.createNode("transform", n="{0}_scaffold_grp".format(prefix))
        jntGrp = pm.createNode("transform", n="{0}_scaffold_jnt_grp".format(prefix))
        locGrp = pm.createNode("transform", n="{0}_scaffold_loc_grp".format(prefix))
        crvGrp = pm.createNode("transform", n="{0}_scaffold_curve_grp".format(prefix))
        pivGrp = pm.createNode("transform", n="{0}_scaffold_piv_grp".format(prefix))
        pm.parent(jntGrp, locGrp, crvGrp, pivGrp, scaffoldChainGrp)
        utils.disableChannels(scaffoldChainGrp, "trs", "lh")
        pm.addAttr(scaffoldChainGrp, ln="locatorSize", at="float", dv=1, k=1)
        for grp in [jntGrp, locGrp, crvGrp, pivGrp]:
            utils.disableChannels(grp, "trsv", "lh")

        # create global pivot ctrl
        globalPiv = pm.spaceLocator(n="{0}_scaffold_piv".format(prefix))
        globalPiv.setParent(scaffoldChainGrp)

        # create scaffold joints and ctrls
        scaffLocators = []
        for i, locName in enumerate(scaffoldChainDict):
            locPos = scaffoldChainDict[locName]

            # create joints
            locJnt = pm.joint(n="{0}_{1}_scaffold_jnt".format(prefix, locName), p=locPos)
            locJnt.v.set(0)
            locJnt.setParent(jntGrp)

            # create loc ctrls
            ctrlColor = scaffLocColor if i<len(scaffoldChainDict)-1 else scaffEndLocColor
            locCtrl = utils.createCtrl("{0}_{1}_scaffold_loc".format(prefix, locName), "sphere", 0.5, ctrlColor)
            utils.matchObject(locJnt, locCtrl, "t")
            scaffoldChainGrp.locatorSize.connect(locCtrl.sx)
            scaffoldChainGrp.locatorSize.connect(locCtrl.sy)
            scaffoldChainGrp.locatorSize.connect(locCtrl.sz)
            utils.disableChannels(locCtrl, "rsv")
            locCtrlOff = utils.createParentTransform("off", locCtrl)
            locCtrlOff.setParent(locGrp)
            pm.pointConstraint(locCtrl, locJnt, n=locJnt.name()+"_pnt", mo=0)
            scaffLocators.append(locCtrl)

            # create pivot ctrls
            if i < len(scaffoldChainDict) - 1:
                locPiv = utils.createCtrl("{0}_{1}_scaffold_piv".format(prefix, locName), "locator", 1.0, scaffPivColor, locJnt) #pm.createNode("locator", n="{0}_{1}_scaffold_piv".format(prefix, locName))
                locPiv.setParent(pivGrp)

        # build secondary axis controls
        for i in range(len(scaffLocators)-1):
            locName = scaffLocators[i].name()
            followOff = pm.createNode("transform", n=locName+"_follow_off", p=scaffLocators[i])
            orientOff = pm.createNode("transform", n=locName+"_orient_off", p=followOff)
            upVectorOff = pm.createNode("transform", n=locName+"_upVector_off", p=orientOff)
            upVectorOff.dla.set(1)

            pm.addAttr(scaffLocators[i], ln="upAxis", at="enum", en="y:-y:z:-z", dv=0, keyable=1)
            pm.addAttr(scaffLocators[i], ln="upAxisOffset", at="float", dv=0, keyable=1)
            scaffLocators[i].upAxisOffset.connect(orientOff.rotateX)
            followOffAim = pm.aimConstraint(scaffLocators[i+1], followOff, n=followOff.name()+"_aim", mo=0)
            for dvValue, drvnKey in enumerate([(0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]):
                pm.setDrivenKeyframe(followOffAim.upVectorX, dv=dvValue, v=drvnKey[0], cd=scaffLocators[i].upAxis)
                pm.setDrivenKeyframe(followOffAim.upVectorY, dv=dvValue, v=drvnKey[1], cd=scaffLocators[i].upAxis)
                pm.setDrivenKeyframe(followOffAim.upVectorZ, dv=dvValue, v=drvnKey[2], cd=scaffLocators[i].upAxis)

        # create reference curve connecting locators
        crv = pm.curve(n="{0}_scaffold_crv".format(prefix), d=1, p=[scaffoldChainDict[x] for x in scaffoldChainDict])
        crv.setParent(crvGrp)
        pm.skinCluster(jntGrp.getChildren(),crv)

        # Todo lock hide useless channels

        return scaffoldChainGrp