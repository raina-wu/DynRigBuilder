__author__ = 'wuxiaoyu'

import pymel.core as pm
import mayautils

map(reload, [mayautils])

SCAFFOLD_TOP_TAG = "scaffoldTop"
SCAFFOLD_META_PIV_TAG = "metaPiv"
SCAFFOLD_LOC_COLOR = 13
SCAFFOLD_END_LOC_COLOR = 6
SCAFFOLD_PIV_COLOR = 17


def buildScaffoldChain(prefix, scaffoldChainDict):
    """
    Build a basic scaffold chain
    :param prefix: `string` scaffold chain prefix. eg."tail"
    :param scaffoldChainDict:`dict`
        dictionary that defines the chain structure.
        chain locator prefix: chain locator world position
        example: {"base": [0,0,0], "end":[3,-6,7]}
    :return: `PyNode` scaffold chain top group
    """
    # create scaffold top node
    scaffoldTop = pm.createNode("transform", n="{0}_scaffold_grp".format(prefix))
    mayautils.disableChannels(scaffoldTop, "trs", "lh")
    scaffAttrs = [
        {"ln":SCAFFOLD_TOP_TAG, "dt":"string"},
        {"ln":SCAFFOLD_META_PIV_TAG, "dt":"string"},
        {"ln":"locatorSize", "at":"float", "dv":1, "k":1},
        {"ln":"locators", "at":"message", "m":1},
        {"ln":"scaffoldType", "dt":"string"}
    ]
    mayautils.addAttributes(scaffoldTop, scaffAttrs)
    pm.setAttr("{0}.{1}".format(scaffoldTop.name(), SCAFFOLD_TOP_TAG), prefix)

    # create group hierarchy
    jntGrp = pm.createNode("transform", n="{0}_scaffold_jnt_grp".format(prefix))
    locGrp = pm.createNode("transform", n="{0}_scaffold_loc_grp".format(prefix))
    crvGrp = pm.createNode("transform", n="{0}_scaffold_curve_grp".format(prefix))
    pivGrp = pm.createNode("transform", n="{0}_scaffold_piv_grp".format(prefix))
    pm.parent(jntGrp, locGrp, crvGrp, pivGrp, scaffoldTop)
    for grp in [jntGrp, locGrp, crvGrp, pivGrp]:
        mayautils.disableChannels(grp, "trsv", "lh")


    # create meta pivot ctrl
    # metaPiv = pm.spaceLocator(n="{0}_scaffold_piv".format(prefix))
    metaPiv = mayautils.createCtrl("{0}_scaffold_piv".format(prefix), "locator", 1.5, SCAFFOLD_PIV_COLOR)
    pm.xform(metaPiv, t=scaffoldChainDict.values()[0], ws=1)
    metaPiv.setParent(scaffoldTop)
    pm.connectAttr(metaPiv.message,
                   "{0}.{1}".format(scaffoldTop.name(), SCAFFOLD_META_PIV_TAG))

    # create scaffold joints and ctrls
    scaffLocators = []
    for i, locName in enumerate(scaffoldChainDict):
        locPos = scaffoldChainDict[locName]

        # create joints
        locJnt = pm.joint(n="{0}_{1}_scaffold_jnt".format(prefix, locName), p=locPos)
        locJnt.v.set(0)
        locJnt.setParent(jntGrp)

        # create loc ctrls
        ctrlColor = SCAFFOLD_LOC_COLOR if i<len(scaffoldChainDict)-1 else SCAFFOLD_END_LOC_COLOR
        locCtrl = mayautils.createCtrl("{0}_{1}_scaffold_loc".format(prefix, locName), "hollowSphere", 0.5, ctrlColor)
        mayautils.matchObject(locJnt, locCtrl, "t")
        locCtrlOff = mayautils.createParentTransform("off", locCtrl)
        locCtrlOff.setParent(locGrp)
        pm.pointConstraint(locCtrl, locJnt, n=locJnt.name()+"_pnt", mo=0)
        scaffLocators.append(locCtrl)
        locCtrl.message.connect(scaffoldTop.locators[i])

        # connect with scaffold top
        scaffoldTop.locatorSize.connect(locCtrl.sx)
        scaffoldTop.locatorSize.connect(locCtrl.sy)
        scaffoldTop.locatorSize.connect(locCtrl.sz)
        mayautils.disableChannels(locCtrl, "rsv")

        # # create pivot ctrls
        # if i < len(scaffoldChainDict) - 1:
        #     locPiv = mayautils.createCtrl("{0}_{1}_scaffold_piv".format(prefix, locName), "locator", 1.0, SCAFFOLD_PIV_COLOR, locJnt) #pm.createNode("locator", n="{0}_{1}_scaffold_piv".format(prefix, locName))
        #     locPiv.setParent(pivGrp)

    # build secondary axis controls
    for i in range(len(scaffLocators)-1):
        locName = scaffLocators[i].name()
        followOff = pm.createNode("transform", n=locName+"_follow_off", p=scaffLocators[i])
        orientOff = pm.createNode("transform", n=locName+"_orient_off", p=followOff)
        upVectorOff = pm.createNode("transform", n=locName+"_upVector_off", p=orientOff)
        upVectorOff.dla.set(1)

        locAttrs = [
            {"ln":"upAxis", "at":"enum", "en":"y:-y:z:-z", "dv":0, "k":0},
            {"ln":"upAxisOffset", "at":"float", "dv":0, "k":0},
        ]
        mayautils.addAttributes(scaffLocators[i], locAttrs)
        scaffLocators[i].upAxisOffset.connect(orientOff.rotateX)
        followOffAim = pm.aimConstraint(scaffLocators[i+1], followOff, n=followOff.name()+"_aim", mo=0)
        for dvValue, drvnKey in enumerate([(0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]):
            pm.setDrivenKeyframe(followOffAim.upVectorX, dv=dvValue, v=drvnKey[0], cd=scaffLocators[i].upAxis)
            pm.setDrivenKeyframe(followOffAim.upVectorY, dv=dvValue, v=drvnKey[1], cd=scaffLocators[i].upAxis)
            pm.setDrivenKeyframe(followOffAim.upVectorZ, dv=dvValue, v=drvnKey[2], cd=scaffLocators[i].upAxis)

        pm.addAttr(scaffLocators[i], ln="upAxisObject", at="message")
        upVectorOff.message.connect(scaffLocators[i].upAxisObject)


    # create reference curve connecting locators
    crv = pm.curve(n="{0}_scaffold_crv".format(prefix), d=1, p=[scaffoldChainDict[x] for x in scaffoldChainDict])
    crv.setParent(crvGrp)
    pm.skinCluster(jntGrp.getChildren(),crv)

    # Todo lock hide useless channels
    pm.select(scaffoldTop)
    return scaffoldTop


def getScaffoldLocs(scaffoldTop):
    return scaffoldTop.locators.get()

def getScaffoldTop(prefix):
    return pm.ls("{0}*.{1}".format(prefix, SCAFFOLD_TOP_TAG), o=1)

def doesScaffoldExist(prefix):
    return True if getScaffoldTop(prefix) else False

def setScaffoldType(scaffoldTop, type):
    scaffoldTop.scaffoldType.set(type)

def getScaffoldType(scaffoldTop):
    return scaffoldTop.scaffoldType.get()

def getLocUpAxisObject(locator):
    try:
        return pm.listConnections(locator.upAxisObject)
    except:
        return None

def getLocPosition(locator):
    return pm.xform(locator, q=1, ws=1, t=1)

def getMetaPivotPosition(scaffoldTop):
    piv = pm.listConnections("{0}.{1}".format(scaffoldTop.name(), SCAFFOLD_META_PIV_TAG))
    return pm.xform(piv, q=1, t=1, ws=1)