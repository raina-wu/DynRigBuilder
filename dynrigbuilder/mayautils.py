__author__ = 'wuxiaoyu'


import pymel.core as pm


def addAttributes(target, attrList):
    """
    Add attributes to target.
    :param target: `PyNode` target node
    :param attrList: `list` list of dictionaries defining attribute properties
                    [{ "ln": `string`    - name of the attribtue,
                       "at": `string`   - type of the attribute,
                       ... - other pm.addAttr funtion flags,
                       "cb": `bool` - display in channelBox
                    },
                    {
                    }
                    ...
                    ]
    :return:
    """
    if not isinstance(attrList, list):
        attrList = [attrList]
    for attrDict in attrList:
        paramDict = attrDict.copy()
        cb = 0
        if "cb" in attrDict.keys():
            cb = attrDict["cb"]
            del paramDict["cb"]
        pm.addAttr(target, **paramDict)
        if "cb" in attrDict.keys():
            pm.setAttr("{0}.{1}".format(target.name(), attrDict["ln"]), cb=cb)



def disableChannels(target, channels="trsv", operation="hl"):
    """
    Hide or lock the specified object channels.
    :param target: `PyNode` object channels
    :param channels: `string` 'trsv' translate, rotate, scale, visibility
    :param operation: `string` 'hl' hide or lock or both
    :return:
    """
    inChannelBox = 0 if "h" in operation else 1
    lock = 1 if "l" in operation else 0
    for channel in channels:
        attrList = [channel+x for x in "xyz"] if channel in "trs" else [channel]
        for attr in attrList:
            pm.setAttr("{0}.{1}".format(target, attr), l=lock, cb=inChannelBox, k=inChannelBox)

def enableChannels(target, channels="trsv", operation="hl"):
    """
    Unhide or unlock the specified object channels.
    :param target: `PyNode` object channels
    :param channels: `string` 'trsv' translate, rotate, scale, visibility
    :param operation: `string` 'hl' unhide or unlock or both
    :return:
    """
    inChannelBox = 1 if "h" in operation else 0
    lock = 0 if "l" in operation else 1
    for channel in channels:
        attrList = [channel+x for x in "xyz"] if channel in "trs" else [channel]
        for attr in attrList:
            pm.setAttr("{0}.{1}".format(target, attr), l=lock, k=inChannelBox)

def createParentTransform(suffix="grp", targetNode=None):
    """
    Create a parent transform of the node that matches the node position.
    :param suffix: `string` parent node name
    :param targetNode: `PyNode` node to add parent transform
    :return: `PyNode` result transform node
    """
    if not targetNode:
        try:
            targetNode = pm.ls(sl=True)[0]
        except:
            print "No target node is specified."
            return None

    grpNode = pm.createNode("transform", n="{0}_{1}".format(targetNode.name(),suffix))
    pm.delete(pm.parentConstraint(targetNode, grpNode, mo=False))
    grpNode.setParent(targetNode.getParent())
    targetNode.setParent(grpNode)
    return grpNode

def matchObject(toTarget, fromTarget, channels="trs"):
    """
    Match object to the target.
    :param toTarget: `PyNode` object to match to
    :param fromTarget: `PyNode` object to transform
    :return:
    """
    if "r" in channels:
        pm.delete(pm.orientConstraint(toTarget, fromTarget, mo=0))
    if "t" in channels:
        pm.delete(pm.pointConstraint(toTarget, fromTarget, mo=0))
    if "s" in channels:
        pm.delete(pm.scaleConstraint(toTarget, fromTarget, mo=0))

def aimObject(toTarget, fromTarget):
    """
    Aim object to the target.
    :param toTarget: `PyNode` or `list` object or world position to aim to
    :param fromTarget: `PyNode` object to transform
    :return:
    """
    if isinstance(toTarget, list):
        targetObj = pm.createNode("transform")
        pm.xform(targetObj, t=toTarget, ws=1)
        pm.delete(pm.aimConstraint(targetObj, fromTarget, mo=0, wut=0))
        pm.delete(targetObj)
    else:
        pm.delete(pm.aimConstraint(toTarget, fromTarget, mo=0, wut=0))

def colorObject(target, color):
    """
    Change the display color of the object.
    :param target: `PyNode` target object
    :param color: `string` color
    :return:
    """
    colorDict = { "red":13, "blue":6, "green":14, "yellow":17}
    targetShape = target.getShape()
    targetShape.overrideEnabled.set(1)

    shdConnections =  pm.listConnections(targetShape, t="shadingEngine", c=1, p=1)
    for shdCon in shdConnections:
        pm.disconnectAttr(shdCon[0], shdCon[1])

    if color in colorDict:
        targetShape.overrideColor.set(colorDict[color])
    else:
        print "color:", color
        targetShape.overrideColor.set(int(color))


def createCtrl(ctrlName, type="locator", size=1, color=None, matchTarget=None, rotation=[0,0,0]):
    """
    Create a controler.
    :param ctrlName: `string` controler name
    :param type: `string` controler type
    :param size: `float` controler size
    :param color: `string` controler color
    :param matchTarget: `PyNode` match the controler to the target object
    :return: `PyNode` controler object
    """
    ctrlLib = {
        "locator":{ "d": 1,
                     "p": [(-1,0,0),(1,0,0),(0,0,0),(0,0,-1),
                           (0,0,1),(0,0,0),(0,1,0),(0,-1,0)]},
        "cube":{"d": 1,
                 "p": [(-1, 1, -1), (-1, 1, 1), (-1, -1, 1), (-1, -1, -1),
                      (-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1),
                      (-1, -1, 1), (1, -1, 1), (1, -1, -1), (1, 1, -1),
                      (1, 1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]},
        "circle":{
                    "d":3,
                    "p":[(0, -0.783612, -0.783612), (0, 0, -1.108194),
                         (0, 0.783612, -0.783612), (0, 1.108194, 0),
                         (0, 0.783612, 0.783612), (0, 0, 1.108194),
                         (0, -0.783612, 0.783612), (0, -1.108194, 0),
                         (0, -0.783612, -0.783612), (0, 0, -1.108194),
                         (0, 0.783612, -0.783612)],
                    "k":[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        "crossArrow":{
                    "d":1,
                    "p":[(1, 0, 1),(3, 0, 1),(3, 0, 2),(5, 0, 0),(3, 0, -2),
                         (3, 0, -1),(1, 0, -1),(1, 0, -3),(2, 0, -3),
                         (0, 0, -5),(-2, 0, -3),(-1, 0, -3),(-1, 0, -1),
                         (-3, 0, -1),(-3, 0, -2),(-5, 0, 0),(-3, 0, 2),
                         (-3, 0, 1),(-1, 0, 1),(-1, 0, 3),(-2, 0, 3),(0, 0, 5),
                         ( 2, 0, 3),(1, 0, 3),(1, 0, 1)],
                    "k":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,
                         18,19,20,21,22,23,24]},
        "cross":{
                    "d":1,
                    "p":[(0.4, 0, -0.4), (0.4, 0, -2), (-0.4, 0, -2),
                         (-0.4, 0, -0.4), (-2, 0, -0.4), (-2, 0, 0.4),
                         (-0.4, 0, 0.4), (-0.4, 0, 2), (0.4, 0, 2),
                         (0.4, 0, 0.4), (2, 0, 0.4), (2, 0, -0.4), (0.4, 0, -0.4)],
                    "k":[0,1,2,3,4,5,6,7,8,9,10,11,12]},
        "fatCross":{
                    "d":1,
                    "p":[(-1, 0, -1), (-1, 0, -2), (1, 0, -2), (1, 0, -1),
                         (2, 0, -1), (2, 0, 1), (1, 0, 1), (1, 0, 2), (-1, 0, 2),
                         (-1, 0, 1), (-2, 0, 1), (-2, 0, -1), (-1, 0, -1)],
                    "k":[0,1,2,3,4,5,6,7,8,9,10,11,12]},
        "hollowSphere":{"d":1,
                  "p":[(0, 1, 0), (0, 0.9239, 0.3827), (0, 0.7071, 0.7071),
                      (0, 0.3827, 0.9239), (0, 0, 1), (0, -0.3827, 0.9239),
                      (0, -0.7071, 0.7071), (0, -0.9239, 0.3827), (0, -1, 0),
                      (0, -0.9239, -0.3827), (0, -0.7071, -0.7071), (0, -0.3827, -0.9239),
                      (0, 0, -1), (0, 0.3827, -0.9239), (0, 0.7071, -0.7071),
                      (0, 0.9239, -0.3827), (0, 1, 0), (0.3827, 0.9239, 0),
                      (0.7071, 0.7071, 0), (0.9239, 0.3827, 0), (1, 0, 0),
                      (0.9239, -0.3827, 0), (0.7071, -0.7071, 0), (0.3827, -0.9239, 0),
                      (0, -1, 0), (-0.3827, -0.9239, 0), (-0.7071, -0.7071, 0),
                      (-0.9239, -0.3827, 0), (-1, 0, 0), (-0.9239, 0.3827, 0),
                      (-0.7071, 0.7071, 0), (-0.3827, 0.9239, 0), (0, 1, 0),
                      (0, 0.9239, -0.3827), (0, 0.7071, -0.7071), (0, 0.3827, -0.9239),
                      (0, 0, -1), (-0.3827, 0, -0.9239), (-0.7071, 0, -0.7071),
                      (-0.9239, 0, -0.3827), (-1, 0, 0), (-0.9239, 0, 0.3827),
                      (-0.7071, 0, 0.7071), (-0.3827, 0, 0.9239), (0, 0, 1),
                      (0.3827, 0, 0.9239), (0.7071, 0, 0.7071), (0.9239, 0, 0.3827),
                      (1, 0, 0), (0.9239, 0, -0.3827), (0.7071, 0, -0.7071),
                      (0.3827, 0, -0.9239), (0, 0, -1)], }
    }



    try:
        if type == "sphere":
            ctrl = pm.sphere(n=ctrlName, r=0.5, ax=[0,1,0], ch=0)[0]
        else:
            ctrl = pm.curve(**ctrlLib[type])
            ctrl.rename(ctrlName)
    except:
        print("error creating ctrl.")
        return None

    ctrl.s.set((size, size, size))
    ctrl.r.set(rotation)
    pm.makeIdentity(ctrl, a=1)
    if matchTarget and ctrl:
        pm.delete(pm.parentConstraint(matchTarget, ctrl, mo=0))

    if color:
        colorObject(ctrl, color)

    return ctrl

def connectChannels(source, destination, channels='trsv'):
    """
    Connect the specified channels of the source and destination objects.
    :param source: `PyNode` source object
    :param destination: `PyNode` destination object
    :param channels: `string` channels to connect
    :return:
    """
    for channel in channels:
        pm.connectAttr("{0}.{1}".format(source.name(), channel),
                       "{0}.{1}".format(destination.name(), channel))

def addBreakLine(ctrl, contentString):
    """
    add a breakline to object's channelbox, usually for ctrlers
    :param ctrl: `PyNode` object to add breakline to
    :param contentString: `string` breakline content
    :return:
    """
    attrName = "_"
    while pm.objExists("{0}.{1}".format(ctrl.name(), attrName)):
        attrName = attrName + "_"
    pm.addAttr(ctrl, ln=attrName, at="enum", en=contentString)
    pm.setAttr("{0}.{1}".format(ctrl.name(), attrName), e=1, channelBox=1)

