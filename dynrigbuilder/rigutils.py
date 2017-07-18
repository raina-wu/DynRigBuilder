__author__ = 'wuxiaoyu'

import pymel.core as pm
import maya.OpenMaya as om
import mayautils

map(reload, [mayautils])

def buildIKSystem(prefix, startPos, endPos, masterCtrlNum, ibtSubCtrlNum,
                  jointNum, metaCtrl=None, preserveVolume=True,
                  preserveLength=True, globalScalePlug=None):
    """
    Build a spline IK.
    :param prefix: `string` prefix added to the related nodes
    :param startPos: `list` [x, y, z] start position of the spline in world space
    :param endPos: `list` [x, y, z] end position of the spline in world space
    :param masterCtrlNum: `int` number of master controls
    :param ibtSubCtrlNum: `int` number of inbetween sub controls
    :param jointNum: `int` number of joints in the IK chain
    :param metaCtrl: `PyNode` meta ctrl node. will be created if not given.
    :param preserveVolume: `bool` preserve volume when deformed
    :param preserveLength: `bool` preserve spline length when deformed
    :param globalScalePlug: `PyNode` global scale attribute
    :return: `PyNode` top node of the system hierarchy
    """
    # ---------------------------------------------------------------------
    # add ik related attr to meta_ctrl
    if not metaCtrl:
        metaCtrl = mayautils.createCtrl("{0}_ik_meta_ctrl".format(prefix))
    attrList = [
        {"ln":"ikSubCtrlVis", "dv":0, "at":"bool", "keyable":1, "cb":0},
        {"ln":"preserveLength", "dv":1, "at":"bool", "keyable":1, "cb":0},
        {"ln":"preserveVolume", "dv":1, "at":"bool", "keyable":1, "cb":0}
    ]
    mayautils.addBreakLine(metaCtrl, "ik")
    mayautils.addAttributes(metaCtrl, attrList)

   # create groups
    ikTopGrp = pm.createNode("transform", n="{0}_ik_grp".format(prefix))
    ikCtrlGrp = pm.createNode("transform", n="{0}_ik_ctrl_grp".format(prefix))
    ikJntGrp = pm.createNode("transform", n="{0}_ik_jnt_grp".format(prefix))
    ikAuxGrp = pm.createNode("transform", n="{0}_ik_aux_grp".format(prefix))
    ikJntGrp.inheritsTransform.set(0)
    ikAuxGrp.inheritsTransform.set(0)
    ikJntGrp.visibility.set(0)
    ikAuxGrp.visibility.set(0)
    for node in [ikCtrlGrp, ikJntGrp, ikAuxGrp]:
        node.setParent(ikTopGrp)
    ikTopGrp.setParent(metaCtrl)
    ikTopAttrList = [
        {"ln": "ctrl", "at":"message", "m":1, "im":0},
        {"ln": "resultJnt", "at":"message", "m":1, "im":0}
    ]
    mayautils.addAttributes(ikTopGrp, ikTopAttrList)

    # ---------------------------------------------------------------------
    # build from scaffold
    # build top/bottom ctrls
    restLen = om.MPoint(*startPos).distanceTo(om.MPoint(*endPos))
    endJntDict = {"top":startPos, "bot":endPos}#{"top":[0,0,0], "bot":[restLen,0,0]}
    endJnts = []
    for name, pos in endJntDict.iteritems():
        jnt = pm.createNode("joint", n="{0}_{1}_jnt".format(prefix, name))
        jnt.translate.set(pos)
        ctrl = mayautils.createCtrl("{0}_{1}_ctrl".format(prefix, name), "hollowSphere", 1, "yellow")
        ctrl.message.connect(ikTopGrp.ctrl, na=1)
        ctrlOrg = mayautils.createParentTransform("org", ctrl)
        ctrlOrg.setParent(ikCtrlGrp)
        mayautils.matchObject(jnt, ctrlOrg)
        pm.parent(jnt, ctrl)
        endJnts.append(jnt)
    auxSurf = createSurfaceFromJoints(endJnts, "{0}_ik_base_surf".format(prefix), 0, 1)
    pm.skinCluster(endJnts, auxSurf, n="{0}_ik_base_skc".format(prefix), mi=2, dr=1)
    auxSurf.setParent(ikAuxGrp)

    # build master ctrls
    masterJnts = []
    ratio = 1.0/(masterCtrlNum-1)
    for i in range(masterCtrlNum):
        vParam = ratio*i
        masterFol = createFollicle(auxSurf, [0.5,vParam], "{0}_ik_master_{1:0>2d}_fol".format(prefix, i))
        masterFol.setParent(ikAuxGrp)
        masterCtrl = mayautils.createCtrl("{0}_ik_master_{1:0>2d}_ctrl".format(prefix, i), "cross", 0.5, "yellow", None, [0,0,90])
        masterCtrl.message.connect(ikTopGrp.ctrl, na=1)
        masterCtrlOrg = mayautils.createParentTransform("org", masterCtrl)
        mayautils.matchObject(masterFol, masterCtrlOrg)
        masterCtrlOrg.setParent(ikCtrlGrp)
        masterCtrlOff = mayautils.createParentTransform("off", masterCtrl)
        aimTarget = endJnts[1] if i<masterCtrlNum-1 else endJnts[0]
        aimVector = [1,0,0] if i<masterCtrlNum-1 else [-1,0,0]
        pm.delete(pm.aimConstraint(aimTarget, masterCtrlOrg, wut=0, aim=aimVector))
        pm.aimConstraint(aimTarget, masterCtrlOff, wut=0, aim=aimVector)
        pm.pointConstraint(masterFol, masterCtrlOff, mo=0)
        masterJnt = pm.createNode("joint", n="{0}_ik_master_{1:0>2d}_jnt".format(prefix, i))
        masterJntOrg = mayautils.createParentTransform("org", masterJnt)
        masterJntOrg.setParent(ikAuxGrp)
        pm.parentConstraint(masterCtrl, masterJntOrg)
        masterJnts.append(masterJnt)

    masterCrv = createCurveFromJoint(masterJnts, "{0}_ik_master_crv".format(prefix), 1, 3)
    pm.skinCluster(masterJnts, masterCrv, n="{0}_ik_master_skc".format(prefix), mi=2, dr=1)
    masterCrv.setParent(ikAuxGrp)

    # ---------------------------------------------------------------------
    # build sub ctrl system
    subJnts = []
    subCtrlNum = ibtSubCtrlNum+1
    ratio1 = 1.0/(subCtrlNum*(masterCtrlNum-1))
    ratio2 = 1.0/subCtrlNum
    for i in range(masterCtrlNum):
         for j in range(subCtrlNum if i<masterCtrlNum-1 else 1):
            id = i*subCtrlNum+j
            subCtrl = mayautils.createCtrl("{0}_ik_sub_{1:0>2d}_ctrl".format(prefix, id), "locator", 0.5, "green", None, [0,0,90])
            subCtrl.message.connect(ikTopGrp.ctrl, na=1)
            subCtrlOrg = pm.createNode("transform", n="{0}_ik_sub_{1:0>2d}_ctrl_org".format(prefix, id)) #utils.createParentTransform("grp", subCtrl)
            subCtrlOrg.setParent(ikCtrlGrp)
            subCtrlOff = mayautils.createParentTransform("off", subCtrl)
            subCtrlRef = pm.createNode("transform", n="{0}_ik_sub_{1:0>2d}_ref".format(prefix, id))
            mayautils.matchObject(subCtrlOff, subCtrlRef)
            subCtrlRef.setParent(subCtrlOrg)
            subCtrlOff.setParent(subCtrlOrg)

            # subCtrl position
            poci = pm.createNode("pointOnCurveInfo", n="{0}_ik_sub_{1:0>2d}_poci".format(prefix, id))
            vecp = pm.createNode("vectorProduct", n="{0}_ik_sub_{1:0>2d}_vecp".format(prefix, id))
            masterCrv.worldSpace[0].connect(poci.inputCurve)
            param = ratio1*id
            poci.parameter.set(param)
            poci.turnOnPercentage.set(1)
            vecp.operation.set(4)
            poci.position.connect(vecp.input1)
            subCtrlOff.parentInverseMatrix[0].connect(vecp.matrix)
            vecp.output.connect(subCtrlOff.translate)

            # subCtrl orientation
            if j==0:
                pm.orientConstraint(masterJnts[i], subCtrlRef)
            else:
                oriCst = pm.orientConstraint(masterJnts[i], masterJnts[i+1], subCtrlRef)
                oriCst.interpType.set(2)
                weightAttrs = pm.orientConstraint(oriCst, q=1, wal=1)
                weight = min(1, max(ratio2*j, 0))
                pm.setAttr(weightAttrs[0], 1-weight)
                pm.setAttr(weightAttrs[1], weight)
            subCtrlTanCst = pm.tangentConstraint(masterCrv, subCtrlOff, wut=2)
            subCtrlRef.worldMatrix[0].connect(subCtrlTanCst.worldUpMatrix)

            # subCtrl visibility
            metaCtrl.ikSubCtrlVis.connect(subCtrl.visibility)

            # build subJoints
            subJnt = pm.createNode("joint", n="{0}_ik_sub_{1:0>2d}_jnt".format(prefix, id))
            pm.addAttr(subJnt, ln="pociParam", at="float", k=0, dv=param)
            subJnts.append(subJnt)
            subJntOrg = mayautils.createParentTransform("org", subJnt)
            subJntOrg.setParent(ikAuxGrp)
            pm.parentConstraint(subCtrl, subJntOrg, mo=0)
            # utils.connectChannels(subCtrl, subJnt, 'tr')
            # utils.connectChannels(subCtrlOff, subJntOrg, 'tr')

    subCrv = createCurveFromJoint(subJnts, "{0}_ik_sub_crv".format(prefix), 1, 3)
    subCrvSkc = pm.skinCluster(subJnts, subCrv, n="{0}_ik_sub_skc".format(prefix), mi=2, dr=1)
    subCrv.setParent(ikAuxGrp)

    # ---------------------------------------------------------------------
    # length preservation
    # compute restArcLength/currentArcLength ratio to determine where to detach the curve
    if preserveLength:
        subCrvRbc = pm.rebuildCurve(subCrv, rpo=1, end=1, kr=0, rt=0, d=7, ch=1, s=64)[1]
        rLenMdl = pm.createNode("multDoubleLinear", n="{0}_restLength_mdl".format(prefix))
        rLenMdl.input1.set(pm.arclen(subCrv))
        globalScalePlug.connect(rLenMdl.input2)
        subCrvInfo = pm.createNode("curveInfo", n="{0}_subCrv_cinfo".format(prefix))
        subCrvRbc.outputCurve.connect(subCrvInfo.inputCurve)
        lenRatioMd = pm.createNode("multiplyDivide", n="{0}_lenRatio_md".format(prefix))
        lenRatioMd.operation.set(2)
        subCrvInfo.arcLength.connect(lenRatioMd.input2X)
        rLenMdl.output.connect(lenRatioMd.input1X)
        lenRatioMdl = pm.createNode("multDoubleLinear", n="{0}_lenRatio_mdl".format(prefix))
        lenRatioMd.outputX.connect(lenRatioMdl.input1)
        metaCtrl.preserveLength.connect(lenRatioMdl.input2)
        preservelenRev = pm.createNode("reverse", n="{0}_preserveLen_rev".format(prefix))
        metaCtrl.preserveLength.connect(preservelenRev.inputX)
        lenRatioAdl = pm.createNode("addDoubleLinear", n="{0}_lenRatio_adl".format(prefix))
        lenRatioMdl.output.connect(lenRatioAdl.input1)
        preservelenRev.outputX.connect(lenRatioAdl.input2)
        lenClp = pm.createNode("clamp", n="{0}_preserveLen_clp".format(prefix))
        lenClp.minR.set(0.0)
        lenClp.maxR.set(1.0)
        lenRatioAdl.output.connect(lenClp.inputR)
        detachCrv = pm.createNode("detachCurve", n="{0}_preserveLen_dtc".format(prefix))
        subCrvRbc.outputCurve.connect(detachCrv.inputCurve)
        lenClp.outputR.connect(detachCrv.parameter[0])
        detachCrv.outputCurve[0].connect(subCrv.create, f=1)

    # ---------------------------------------------------------------------
    # build ik aim joint chain
    aimJnts = buildJointChain("{0}_ik_aim".format(prefix), "jnt", startPos, endPos, jointNum)#[]
    aimRefs = []
    ratio= 1.0/(jointNum-1.0)
    ratio2 = subCtrlNum*(masterCtrlNum-1.0)/(jointNum-1.0)
    aimJntGrp = pm.createNode("transform", n="{0}_ik_aim_jnt_grp".format(prefix))
    aimRefGrp = pm.createNode("transform", n="{0}_ik_aim_ref_grp".format(prefix))
    aimRefGrp.setParent(ikAuxGrp)
    aimJntGrp.inheritsTransform.set(0)
    aimJntGrp.setParent(ikJntGrp)
    for i in range(jointNum):
        aimJntRef = pm.createNode("transform", n="{0}_ik_aim_{1:0>2d}_ref".format(prefix, i))
        aimJntRef.setParent(aimRefGrp)
        aimRefs.append(aimJntRef)

        poci = pm.createNode("pointOnCurveInfo", n="{0}_ik_aim_{1:0>2d}_poci".format(prefix, id))
        poci.turnOnPercentage.set(1)
        subCrv.worldSpace[0].connect(poci.inputCurve)
        param = ratio*i
        poci.parameter.set(param)

        vecp = pm.createNode("vectorProduct", n="{0}_ik_aim_{1:0>2d}_vecp".format(prefix, id))
        vecp.operation.set(4)
        poci.position.connect(vecp.input1)
        aimJntRef.parentInverseMatrix[0].connect(vecp.matrix)
        vecp.output.connect(aimJntRef.translate)

        subJntId = int(i*ratio2)
        if i == jointNum-1:
            pm.orientConstraint(subJnts[subJntId], aimJntRef)
        else:
            oriCst = pm.orientConstraint(subJnts[subJntId], subJnts[subJntId+1], aimJntRef)
            oriCst.interpType.set(2)
            weight = min(1, max(0, (param-subJnts[subJntId].pociParam.get())
                    /(subJnts[subJntId+1].pociParam.get()-subJnts[subJntId].pociParam.get())))
            weightAttrs = pm.orientConstraint(oriCst, q=1, wal=1)
            pm.setAttr(weightAttrs[0], weight)
            pm.setAttr(weightAttrs[1], 1-weight)


        aimJnt = aimJnts[i]
        # aimJnt = pm.createNode("joint", n="{0}_ik_aim_{1:0>2d}_jnt".format(prefix, i))
        # aimJnts.append(aimJnt)
        if i==0:
            aimJnt.setParent(aimJntGrp)
        else:
            aimJnt.setParent(aimJnts[i-1])
            aimCst = pm.aimConstraint(aimJntRef, aimJnts[i-1], wut=2)
            aimRefs[i-1].worldMatrix[0].connect(aimCst.worldUpMatrix)
        if i == jointNum-1:
            pm.orientConstraint(aimJntRef, aimJnts[i])
        pm.pointConstraint(aimJntRef, aimJnt)

    # build ik joint chain
    retJntGrp = pm.createNode("transform", n="{0}_ik_ret_jnt_grp".format(prefix))
    retJntGrp.setParent(ikJntGrp)
    mayautils.connectChannels(aimJntGrp, retJntGrp, 'trs')
    # ikJnts = []
    # for aimJnt in aimJnts:
        # ikJnt = pm.joint(n=aimJnt.name().replace("aim", "ret"))
        # utils.connectChannels(aimJnt, ikJnt, "tr")
        # ikJnts.append(ikJnt)
    ikJnts = buildJointChain("{0}_ik_ret".format(prefix), "jnt", startPos, endPos, jointNum)
    for i in range(jointNum):
        mayautils.connectChannels(aimJnts[i], ikJnts[i], "tr")
        globalScalePlug.connect(ikJnts[i].scaleY)
        globalScalePlug.connect(ikJnts[i].scaleZ)
        ikJnts[i].message.connect(ikTopGrp.resultJnt, na=1)
    ikJnts[0].setParent(retJntGrp)
    # ---------------------------------------------------------------------
    # TODO volume preservation


    # TODO bind proxy geo to validate building result
    #
    return ikTopGrp


def buildRegularFKSystem(joints, prefix, ctrlNum):
    pass

def buildVariableFKSystem(joints, prefix, ctrlNum, metaCtrl=None):
    """
    Build variable fk contrl on the given joint chain.
    :param joints: `list` joints in the target joint chain
    :param prefix: `string` prefix added to the related nodes
    :param ctrlNum: `int` number of fk controls
    :param metaCtrl: `PyNode` meta ctrl node. will be created if not given.
    :return: `PyNode` top node of the system hierarchy
    """
    if not metaCtrl:
        metaCtrl = mayautils.createCtrl("{0}_ik_meta_ctrl".format(prefix))

    # create groups
    fkTopGrp = pm.createNode("transform", n="{0}_fk_grp".format(prefix))
    fkCtrlGrp = pm.createNode("transform", n="{0}_fk_ctrl_grp".format(prefix))
    fkJntGrp = pm.createNode("transform", n="{0}_fk_jnt_grp".format(prefix))
    fkAuxGrp = pm.createNode("transform", n="{0}_fk_aux_grp".format(prefix))
    fkAuxGrp.inheritsTransform.set(0)
    fkJntGrp.visibility.set(0)
    fkAuxGrp.visibility.set(0)
    for node in [fkCtrlGrp, fkJntGrp, fkAuxGrp]:
        node.setParent(fkTopGrp)
    fkTopGrp.setParent(metaCtrl)
    fkTopAttrList = [
        {"ln": "ctrl", "at":"message", "m":1, "im":0},
        {"ln": "resultJnt", "at":"message", "m":1, "im":0}
    ]
    mayautils.addAttributes(fkTopGrp, fkTopAttrList)

    # create fk joint chain
    fkJnts = pm.duplicate(joints, n="{0}_fk_00_jnt".format(prefix))
    fkJnts[0].setParent(fkJntGrp)
    for i, jnt in enumerate(fkJnts):
        jnt.rename("{0}_fk_{1:0>2d}_jnt".format(prefix, i))
        jnt.message.connect(fkTopGrp.resultJnt, na=1)

    # build surface from joints, one span for each joint
    # bind surface to joints
    auxSurf = createSurfaceFromJoints(fkJnts)
    auxSurf.rename("{0}_fk_aux_surf".format(prefix))
    auxSurf.setParent(fkAuxGrp)
    pm.skinCluster(fkJnts, auxSurf, n="{0}_fk_aux_skc".format(prefix))
    # TODO weigh 100% of each span to each joint

    # evenly distribute ctrlNum follicles on surface
    # create fk ctrls and constrain to follicles
    # follicle position(VParam) is driven by fkCtrl.position
    fkCtrls = []
    for i in range(ctrlNum):
        folParams = [0.5, 1.0/(ctrlNum+1)*(i+1)]
        follicle = createFollicle(auxSurf,folParams, "{0}_fk_{1:0>2d}_fol".format(prefix, i))
        follicle.setParent(fkAuxGrp)
        # follicle.rename("{0}_fk_{1:0>2d}_fol".format(prefix, i))
        ctrl = mayautils.createCtrl("{0}_fk_{1:0>2d}_ctrl".format(prefix, i), "circle", 1, "yellow")
        ctrl.message.connect(fkTopGrp.ctrl, na=1)
        ctrl.setParent(fkCtrlGrp)
        fkCtrls.append(ctrl)

        # TODO match orientation to closest joint
        mayautils.matchObject(fkJnts[0], ctrl, 'r')
        mayautils.matchObject(follicle, ctrl, 't')

        ctrlGrp = mayautils.createParentTransform("off", ctrl)
        pm.parentConstraint(follicle, ctrlGrp, mo=1)

        # set ctrl attributes
        ctrl.scaleX.lock()
        mayautils.disableChannels(ctrl, 't')
        pm.addAttr(ctrl, ln="position", at="float", dv=folParams[1], k=1, min=0, max=1)
        pm.addAttr(ctrl, ln="rotateFallOff", at="float", dv=0.2, k=1, min=0.001, max=1)
        pm.addAttr(ctrl, ln="scaleFallOff", at="float", dv=0.2, k=1, min=0.001, max=1)
        ctrl.position.connect(follicle.parameterV)


    # build variable fk system
    # the rotate and scale value of each joint is affected by all fkCtrls
    # joint.rotate = (1-clamp(dist(joint, ctrl1), 0, falloff)/falloff)*tweakParam*ctrl1.rotate
    #               + (1-clamp(dist(joint, ctrl2), 0, falloff)/falloff)*tweakParam*ctrl2.rotate
    #               + (1-clamp(dist(joint, ctrl3), 0, falloff)/falloff)*tweakParam*ctrl3.rotate + ...

    cpos = pm.createNode("closestPointOnSurface")
    auxSurf.worldSpace.connect(cpos.inputSurface)
    for i, jnt in enumerate(fkJnts):
        # calculate joint position on surface and store in attribute
        cpos.inPosition.set(jnt.getTranslation(space="world"))
        pm.addAttr(jnt, ln="posOnSurface", at="float", dv=cpos.parameterV.get())

        # build rotate/scale parameter network
        rotPma = pm.createNode("plusMinusAverage", n="{0}_fk_{1:0>2d}_rot_pma".format(prefix,i))
        rotPma.operation.set(1)
        rotPma.output3D.connect(jnt.rotate)
        scalePma = pm.createNode("plusMinusAverage", n="{0}_fk_{1:0>2d}_scale_pma".format(prefix,i))
        scalePma.operation.set(1)
        scalePma.input3D[0].set([1,1,1])
        scalePma.output3D.connect(jnt.scale)
        for j in range(ctrlNum):
            # calculate absolute distance from joint to ctrl
            fkCtrl = fkCtrls[j]
            nodePrefix = "{0}_fk_{1:0>2d}_{2:0>2d}".format(prefix, i, j)
            distPma = pm.createNode("plusMinusAverage", n="{0}_dist_pma".format(nodePrefix))
            distPma.operation.set(2)
            fkCtrl.position.connect(distPma.input1D[0])
            jnt.posOnSurface.connect(distPma.input1D[1])
            absMd1 = pm.createNode("multiplyDivide", n="{0}_dist_abs1_md".format(nodePrefix))
            absMd1.operation.set(3)
            absMd1.input2X.set(2)
            absMd2 = pm.createNode("multiplyDivide", n="{0}_dist_abs1_md".format(nodePrefix))
            absMd2.operation.set(3)
            absMd2.input2X.set(0.5)
            distPma.output1D.connect(absMd1.input1X)
            absMd1.output.connect(absMd2.input1)

            # clamp to (0, falloff)
            distClamp = pm.createNode("clamp", n="{0}_dist_cla".format(nodePrefix))
            distClamp.minR.set(0)
            distClamp.minG.set(0)
            fkCtrl.rotateFallOff.connect(distClamp.maxR)
            fkCtrl.scaleFallOff.connect(distClamp.maxG)
            absMd2.outputX.connect(distClamp.inputR)
            absMd2.outputX.connect(distClamp.inputG)

            # calculate rotation/scale multiplier ratio
            ratioMd = pm.createNode("multiplyDivide", n="{0}_ratio_md".format(nodePrefix))
            ratioMd.operation.set(2)
            distClamp.outputR.connect(ratioMd.input1X)
            distClamp.outputG.connect(ratioMd.input1Y)
            fkCtrl.rotateFallOff.connect(ratioMd.input2X)
            fkCtrl.scaleFallOff.connect(ratioMd.input2Y)
            ratioRev = pm.createNode("reverse", n="{0}_ratio_rev".format(nodePrefix))
            ratioMd.output.connect(ratioRev.input)

            # calculate rotation value
            rotTweak = pm.createNode("multDoubleLinear", n="{0}_rot_tweak_md".format(nodePrefix))
            ratioRev.outputX.connect(rotTweak.input1)
            rotTweak.input2.set(1)
            rotMd = pm.createNode("multiplyDivide", n="{0}_rot_md".format(nodePrefix))
            rotMd.operation.set(1)
            rotTweak.output.connect(rotMd.input2X)
            rotTweak.output.connect(rotMd.input2Y)
            rotTweak.output.connect(rotMd.input2Z)
            fkCtrl.rotate.connect(rotMd.input1)
            rotMd.output.connect(rotPma.input3D[j])

            # calculate scale value
            scalePrePma = pm.createNode("plusMinusAverage", n="{0}_scale_pma".format(nodePrefix))
            scalePrePma.operation.set(2)
            fkCtrl.scale.connect(scalePrePma.input3D[0])
            scalePrePma.input3D[1].set([1,1,1])
            scaleTweak = pm.createNode("multDoubleLinear", n="{0}_scale_tweak_md".format(nodePrefix))
            ratioRev.outputY.connect(scaleTweak.input1)
            scaleTweak.input2.set(1)
            scaleMd = pm.createNode("multiplyDivide", n="{0}_scale_md".format(nodePrefix))
            scaleMd.operation.set(1)
            scaleTweak.output.connect(scaleMd.input2X)
            scaleTweak.output.connect(scaleMd.input2Y)
            scaleTweak.output.connect(scaleMd.input2Z)
            scalePrePma.output3D.connect(scaleMd.input1)
            scaleMd.output.connect(scalePma.input3D[j+1])

    pm.delete(cpos)
    return fkTopGrp



def buildDynamicSystem(prefix, joints, metaCtrl=None, hairSystem=None):
    """
    Build dynamic system based on the given joint chain.
    :param joints: `list` joints in the target joint chain
    :param prefix: `string` prefix added to the related nodes
    :param metaCtrl: `PyNode` meta ctrl node. will be created if not given.
    :return: `PyNode` top node of the system hierarchy
    """
    # add dynamic related attr to meta_ctrl
    if not metaCtrl:
        metaCtrl = mayautils.createCtrl("{0}_dyn_meta_ctrl".format(prefix))
    attrList = [
        {"ln":"dynamicSwitch", "dv":1, "at":"bool", "keyable":0, "cb":1},
        {"ln":"startFrame", "dv":1, "at":"long", "keyable":0, "cb":1},
        {"ln":"animationAttract", "dv":0, "at":"float", "keyable":1, "cb":0},
        {"ln":"animationBlend", "dv":0, "at":"float", "keyable":1, "cb":0}
    ]
    mayautils.addBreakLine(metaCtrl, "dynamic")
    mayautils.addAttributes(metaCtrl, attrList)

    # create groups
    dynTopGrp = pm.createNode("transform", n="{0}_dyn_grp".format(prefix))
    dynJntGrp = pm.createNode("transform", n="{0}_dyn_jnt_grp".format(prefix))
    dynAuxGrp = pm.createNode("transform", n="{0}_dyn_aux_grp".format(prefix))
    dynCtrlGrp = pm.createNode("transform", n="{0}_dyn_ctrl_grp".format(prefix))
    # dynJntGrp.inheritsTransform.set(0)
    dynAuxGrp.inheritsTransform.set(0)
    for node in [dynCtrlGrp, dynJntGrp, dynAuxGrp]:
        node.setParent(dynTopGrp)
    dynTopGrp.setParent(metaCtrl)
    dynTopAttrList = [
        {"ln": "ctrl", "at":"message", "m":1, "im":0},
        {"ln": "resultJnt", "at":"message", "m":1, "im":0}
    ]
    mayautils.addAttributes(dynTopGrp, dynTopAttrList)

    # create dynamic system
    animCrv = createCurveFromJoint(joints, "{0}_anim_crv".format(prefix))
    dynSys = makeCurveDynamic(animCrv, hairSystem)
    dynCrv = dynSys["outCurve"]
    dynCrv.setParent(dynAuxGrp)
    pm.skinCluster(joints, animCrv, n="{0}_anim_crv_skc".format(prefix), mi=2, dr=1)
    animCrvBS = pm.blendShape(animCrv, dynCrv, n="{0}_anim_blend_blendshape".format(prefix), w=(0, 1))[0]
    dynSwitchBS = pm.blendShape(animCrv, dynCrv, n="{0}_dynSwitch_blendshape".format(prefix), w=(0, 1))[0]
    dynSys["follicle"].rename("{0}_dyn_fol".format(prefix))
    dynSys["follicle"].setParent(dynAuxGrp)

    # if not using a shared hair system, organize the hair system setup
    # into rig hierarchy and connect metactrl dynamic attributes
    if not hairSystem:
        dynSys["hairSystem"].rename("{0}_dyn_hairSystem".format(prefix))
        dynSys["nucleus"].rename("{0}_dyn_nucleus".format(prefix))
        dynSys["hairSystem"].setParent(dynAuxGrp)
        dynSys["nucleus"].setParent(dynAuxGrp)

        metaCtrl.dynamicSwitch.connect(dynSys["nucleus"].enable)
        metaCtrl.startFrame.connect(dynSys["nucleus"].startFrame)
        metaCtrl.animationAttract.connect(dynSys["hairSystem"].getShape().startCurveAttract)

    dynRev = pm.createNode("reverse")
    metaCtrl.dynamicSwitch.connect(dynRev.inputX)
    dynRev.outputX.connect(dynSwitchBS.envelope)
    metaCtrl.animationBlend.connect(animCrvBS.envelope)

    # create dynamic joints
    dynJoints = duplicateJointChain(joints[0], ["base_jnt", "dyn_jnt"], None)
    dynJoints[0].setParent(dynJntGrp)
    ikh = pm.ikHandle(n="{0}_dyn_ikHandle".format(prefix), sj=dynJoints[0],
                      ee=dynJoints[-1], c=dynCrv, sol="ikSplineSolver", roc=1, ccv=0, pcv=0)[0]
    ikh.setParent(dynAuxGrp)

    for dynJnt in dynJoints:
        dynJnt.message.connect(dynTopGrp.resultJnt, na=1)

    # # create secondary control on dynamic curve
    # ratio = 1.0/(secondaryCtrlNum-1.0)
    # secJnts = []
    # for i in range(secondaryCtrlNum):
    #     secCtrl = utils.createCtrl("{0}_dynik_{1:0>2d}_ctrl".format(prefix, i), "locator", 0.5, "blue")
    #     secCtrlOff = utils.createParentTransform("off", secCtrl)
    #
    #     poci = pm.createNode("pointOnCurveInfo", n="{0}_dynik_{1:0>2d}_poci".format(prefix, i))
    #     vecp = pm.createNode("vectorProduct", n="{0}_dynik_{1:0>2d}_vecp".format(prefix, i))
    #     dynCrv.worldSpace[0].connect(poci.inputCurve)
    #     poci.parameter.set(ratio*i)
    #     poci.turnOnPercentage.set(1)
    #     vecp.operation.set(4)
    #     poci.position.connect(vecp.input1)
    #     secCtrlOff.parentInverseMatrix[0].connect(vecp.matrix)
    #     vecp.output.connect(secCtrlOff.translate)
    #     pm.tangentConstraint(dynCrv, secCtrlOff)
    #
    #     # build subJoints
    #     secJnt = pm.createNode("joint", n="{0}_dynik_{1:0>2d}_jnt".format(prefix, i))
    #     secJnts.append(secJnt)
    #     utils.matchObject(secCtrl, secJnt, 'trs')
    #     secJnt.setParent(secCtrl)
    #
    # secCrv = pm.duplicate(dynCrv, n="{0}_tweak_crv".format(prefix))[0]
    # secCrvSkc = pm.skinCluster(secJnts, secCrv, n="{0}_dynik_skc".format(prefix), mi=2, dr=1, bm=0, nw=1, wd=0)
    # pm.ikHandle(sj=dynJoints[0], ee=dynJoints[-1], c=secCrv, sol="ikSplineSolver", roc=1, ccv=0, pcv=0)

    return dynTopGrp















def createFollicle(target=None, param=[0.5,0.5], name="follicle"):
    """
    Create follicle.
    :param target: `PyNode` target that the follicle connected to
    :param param: `list` [u, v] follicle uv parameter
    :param name: `string` follicle name
    :return: `PyNode` follicle ransform node
    """
    follicle = pm.createNode("follicle")
    follicle.parameterU.set(param[0])
    follicle.parameterV.set(param[1])

    if target:
        targetShape = target.getShape()
        targetShape.worldMatrix.connect(follicle.inputWorldMatrix)
        if targetShape.nodeType() == "nurbsSurface":
            targetShape.local.connect(follicle.inputSurface)
        elif targetShape.nodeType() == "mesh":
            targetShape.outMesh.connect(follicle.inputMesh)

    folTransform = follicle.getParent()
    follicle.outRotate.connect(folTransform.rotate)
    follicle.outTranslate.connect(folTransform.translate)
    pm.rename(folTransform, name)
    return folTransform


def createCurveFromJoint(joints, name="curve", ibtCVNum=0, degree=3):
    """
    Create a nurbs curve along the given joints
    :param joints: `list` list of joint nodes
    :param name: `string` name of the built surface
    :param ibtCVNum: `int` number of cv points added inbetween the joint position
    :param degree: `int` nurbs surface degree
    :return: `PyNode` result curve
    """
    jntPos = [jnt.getTranslation(space="world") for jnt in joints]
    cvPos = []
    if ibtCVNum>0:
        for i in range(len(jntPos)-1):
            cvPos.append(jntPos[i])
            ratio = (jntPos[i+1]-jntPos[i])/(ibtCVNum+1.0)
            for j in range(1, ibtCVNum+1):
                cvPos.append(jntPos[i]+ratio*j)
        cvPos.append(jntPos[-1])
    else:
        cvPos = jntPos
    auxCrv = pm.curve(p=cvPos, d=degree, n=name)
    pm.rebuildCurve(auxCrv, ch=0, rpo=1, rt=0, end=1, kep=1, kr=0, kcp=0,
                    kt=0, s=len(cvPos)-1, d=degree)
    pm.parent(auxCrv, w=1)
    return auxCrv


def createSurfaceFromJoints(joints, name="surface", ibtCVNum=0, degree=3):
    """
    Create a nurbs surface along the given joints.
    nurbs CV position is defined by joint position.
    :param joints: `list` list of joint nodes
    :param name: `string` name of the built surface
    :param ibtCVNum: `int` number of cv points added inbetween the joint position
    :param degree: `int` nurbs surface degree
    :return: `PyNode` result surface
    """
    # build surface from joints, one span for each joint
    auxCrv = createCurveFromJoint(joints, name+"_crv", ibtCVNum, degree)
    startPos = joints[0].getTranslation(space="world")
    endPos = joints[-1].getTranslation(space="world")

    offDir = (om.MVector(*(startPos-endPos))^om.MVector(0,1,0)).normal()
    if offDir.length() == 0: offDir = om.MVector(0,0,-1)

    print startPos, endPos, offDir[0], offDir[1], offDir[2]
    buildCrv1 = pm.duplicate(auxCrv)
    pm.move(offDir.x*0.5, offDir.y*0.5, offDir.z*0.5, buildCrv1, r=1)
    buildCrv2 = pm.duplicate(auxCrv)
    pm.move(offDir.x*-0.5, offDir.y*-0.5, offDir.z*-0.5, buildCrv2, r=1)
    auxSurf = pm.loft(buildCrv1, buildCrv2, n=name, ch=0, u=1, d=degree)[0]
    pm.rebuildSurface(auxSurf, ch=0, su=1, du=1, dv=degree, sv=0)
    pm.delete(auxCrv, buildCrv1, buildCrv2)
    # auxSurf.setParent(0)
    return auxSurf


def buildJointChain(prefix, suffix, startPos, endPos, jointNum, orientJoint="xyz", saoType="yup"):
    """
    Build a straight joint chain defined by start and end position.
    :param prefix: `string` prefix string in joint name
    :param suffix: `string` suffix string in joint name
    :param startPos: `list` [x,y,z] start position in the world space
    :param endPos: `list` [x,y,z] end position in the world space
    :param jointNum: number of joints in the joint chain
    :param orientJoint: `string` orient joint flag
    :param saoType: `string` secondary axis orient flag
    :return: `list` list of joint nodes in the joint chain. sorted by hierarchy.
    """
    pm.select(d=1)
    step = (om.MVector(*endPos)-om.MVector(*startPos))/(jointNum-1.0)
    jnts = []
    for i in range(jointNum):
        crtPos = om.MVector(*startPos)+step*i
        crtSuffix = suffix#suffix[1] if i==jointNum-1 else suffix[0]
        jnts.append(pm.joint(p=(crtPos.x, crtPos.y, crtPos.z), n="{0}_{1:0>2d}_{2}".format(prefix, i, crtSuffix)))
    pm.joint(jnts, e=True, oj=orientJoint, sao=saoType)
    return jnts


def duplicateJointChain(rootJoint, replace=None, suffix=None):
    """
    Duplicate the given joint chain.
    :param rootJoint: `PyNode` root joint of the given joint chain
    :param replace: `tuple` or `list` (old string, new string)
                    rename the duplicated joint chain by replacing string in given joint name
    :param suffix: `string` rename the duplicated joint chain by adding suffix to the given joint name
    :return: `list` list of joints in the duplicated joint chain. ordered by hierarchy
    """
    srcJnts = getJointsInChain(rootJoint)
    dupJnts = []
    if not replace and not suffix:
        raise ValueError("Please rename the duplicated joint chain.")
    for i, srcJnt in enumerate(srcJnts):
        newName = srcJnt.name()
        if replace:
            newName = newName.replace(replace[0], replace[1])
        if suffix:
            newName = "{0}_{1}".format(newName, suffix)
        dupJnt = pm.duplicate(srcJnt, n=newName, po=1)[0]
        dupJnts.append(dupJnt)
        for attr in ['t', 'r', 's', 'jointOrient']:
            pm.setAttr("{0}.{1}".format(dupJnt.name(), attr), pm.getAttr("{0}.{1}".format(srcJnt.name(), attr)))
        if i>0:
            dupJnt.setParent(dupJnts[i-1])
    #
    # for i, srcJnt in enumerate(srcJnts):
    #     if i==0: continue
    #     srcPar = pm.listRelatives(srcJnt, p=1)
    #     if srcPar:
    #         dupJnts[i].setParent(srcPar[0].name().replace(replace[0], replace[1]))
    return dupJnts


def buildJointChainFromCurve(curve, jointNum, prefix, suffix, rebuildCurve=False, orientJoint="xyz", saoType="yup"):
    """
    Build joint chain along the curve.
    :param curve: `PyNode` curve that defines the joint position
    :param jointNum: `int` number of joints in the chain
    :param prefix: `string` prefix string in joint name
    :param suffix: `string` suffix string in joint name
    :param rebuildCurve: `bool` if true, rebuild the input curve to make sure the joints are evenly positioned,
                        but can't guarantee the joints lands exacly on the input curve
    :param orientJoint: `string` orient joint flag
    :param saoType: `string` secondary axis orient flag
    :return: `list` list of joint nodes in the joint chain. sorted by hierarchy.
    """
    if rebuildCurve:
        curve = pm.rebuildCurve(curve, rpo=0, end=1, kr=0, rt=0, d=7, ch=0, s=64)[0]
    poci = pm.createNode("pointOnCurveInfo")
    poci.turnOnPercentage.set(1)
    curve.worldSpace[0].connect(poci.inputCurve)

    joints = []
    ratio = 1.0/(jointNum-1.0)
    pm.select(d=1)
    for i in range(jointNum):
        poci.parameter.set(ratio*i)
        joint = pm.joint(n="{0}_{1:0>2d}_{2}".format(prefix, i, suffix), p=poci.position.get())
        joints.append(joint)
    pm.joint(joints, oj=orientJoint, sao=saoType)
    return joints


def getJointsInChain(rootJoint):
    """
    get all the joints in the joint chain. sorted by hierarchy.
    :param rootJoint: `PyNode` root joint of the joint chain
    :return: `list` list of joint nodes
    """
    joints = [rootJoint]
    crtJnt = rootJoint
    while True:
        childJnt = pm.listRelatives(crtJnt, c=1, typ="joint")
        if childJnt:
            joints.append(childJnt[0])
            crtJnt = childJnt[0]
        else:
            break
    return joints

def makeCurveDynamic(inputCurve, hairSys=None):
    """
    Make the input curve dynamic.
    :param inputCurve: `PyNode` input curve that is used as the start curve in dynamic system
    :param hairSys: `PyNode` which hair system to assign the curve to,
                            if None, new hair system will be created
    :return: `Dict`
            "outCurve" : dynamic ouput curve
            "follicle" : follicle transform node
            "hairSystem": hair system transform node
            "nucleus": nucleus node
    """
    if inputCurve.nodeType() != "nurbsCurve":
        inputCurve = inputCurve.getShape()
    if not hairSys:
        hairSys = pm.createNode("hairSystem")
        pm.select(hairSys, r=1)
        pm.mel.assignNSolver("")
    follicle = pm.mel.createHairCurveNode(hairSys.name(), "", 0, 0, 0, True,
               True, False, False, inputCurve.name(), 0, [0], "", "", 1)
    follicle = pm.PyNode(follicle)
    nucleus = hairSys.currentState.connections()[0]
    outCurve = follicle.outCurve.connections()[0]
    return {"outCurve": outCurve, "follicle": follicle, "hairSystem":hairSys.getParent(), "nucleus":nucleus}

#
# def makeCurveDynamic(inputCurve, outputCurve, hairSys=None):
#     """
#     Create dynamic system, take the input curve as start curve,
#     and write the dynamic result to the output curve.
#     :param inputCurve: `PyNode` input curve that is used as the start curve in dynamic system
#     :param outputCurve: `PyNode` output curve of the dynamic system
#     :return: `Dict`
#             "follicle" : follicle transform node
#             "hairSystem": hair system transform node
#             "nucleus": nucleus node
#     """
#     if not hairSys:
#         time = None
#         # nucleus = pm.ls(type="nucleus")
#         # if nucleus:
#         #     nucleus = nucleus[0]
#         #     time = nucleus.currentTime.connections()[0]
#         # else:
#         nucleus = pm.createNode("nucleus")
#         time = pm.ls(type="time")[0]
#         time.outTime.connect(nucleus.currentTime)
#         hairSys = pm.createNode("hairSystem")
#         hairSys.active.set(1)
#         # print time
#         time.outTime.connect(hairSys.currentTime)
#         # print hairSys, nucleus
#         # pm.select(hairSys)
#         # pm.mel.eval('assignNSolver {0}'.format(nucleus.name()))
#         hairSys.currentState.connect(nucleus.inputActive[0])
#         hairSys.startState.connect(nucleus.inputActiveStart[0])
#         nucleus.startFrame.connect(hairSys.startFrame)
#         nucleus.outputObjects[0].connect(hairSys.nextState)
#
#
#     fol = createFollicle(None, [0,0])
#     folShape = fol.getShape()
#     folShape.restPose.set(1)
#     folShape.startDirection.set(1)
#     inputCurve.setParent(fol)
#     inputCurve.worldMatrix[0].connect(folShape.startPositionMatrix)
#     inputCurve.getShape().local.connect(folShape.startPosition)
#     folShape.outCurve.connect(outputCurve.getShape().create)
#
#     folShape.outHair.connect(hairSys.inputHair[0])
#     # idxCnt = len(hairSys.outputHair.get())
#     hairSys.outputHair[0].connect(folShape.currentPosition)
#
#     return {"follicle": fol, "hairSystem":hairSys.getParent(), "nucleus":nucleus}
#



    # def buildIKSystemFromJoints(self, prefix, joints, masterCtrlNum, ibtSubCtrlNum, metaCtrl=None):
    #
    #     jointNum = len(joints)
    #     # create groups
    #     ikCtrlGrp = pm.createNode("transform", n="{0}_ik_ctrl_grp".format(prefix))
    #     ikJntGrp = pm.createNode("transform", n="{0}_ik_jnt_grp".format(prefix))
    #     ikAuxGrp = pm.createNode("transform", n="{0}_ik_aux_grp".format(prefix))
    #     ikJntGrp.inheritsTransform.set(0)
    #     ikAuxGrp.inheritsTransform.set(0)
    #
    #     # ---------------------------------------------------------------------
    #     # create meta ctrls
    #     # add ik related attr to meta_ctrl
    #     if not metaCtrl:
    #         metaCtrl = utils.createCtrl("{0}_meta_ctrl".format(prefix))
    #     attrList = [
    #         {"ln": "preserveLength", "dv": 1, "at": "bool", "keyable": 1, "cb": 0},
    #         {"ln": "ikSubCtrlVis", "dv": 1, "at": "bool", "keyable": 1, "cb": 0},
    #         {"ln": "preserveVolume", "dv": 1, "at": "bool", "keyable": 1, "cb": 0},
    #     ]
    #     for attr in attrList:
    #         pm.addAttr(metaCtrl, ln=attr["ln"], dv=attr["dv"], at=attr["at"])
    #         pm.setAttr("{0}.{1}".format(metaCtrl, attr["ln"]), keyable=attr["keyable"], cb=attr["cb"])
    #
    #     # ---------------------------------------------------------------------
    #     # build top/bottom ctrl
    #     endJntDict = {"top": joints[0].getTranslation(space="world"),
    #                   "bot": joints[-1].getTranslation(space="world")}
    #     endJnts = []
    #     for name, pos in endJntDict.iteritems():
    #         jnt = pm.createNode("joint", n="{0}_{1}_jnt".format(prefix, name))
    #         jnt.translate.set(pos)
    #         ctrl = utils.createCtrl("{0}_{1}_ctrl".format(prefix, name), "cube", 1, "yellow")
    #         ctrlOrg = utils.createParentTransform("org", ctrl)
    #         ctrlOrg.setParent(ikCtrlGrp)
    #         utils.matchObject(jnt, ctrlOrg)
    #         pm.parent(jnt, ctrl)
    #         endJnts.append(jnt)
    #     auxSurf = utils.createSurfaceFromJoints(joints, "{0}_ik_base_surf".format(prefix), 0, 1)
    #     pm.skinCluster(endJnts, auxSurf, n="{0}_ik_base_skc".format(prefix), mi=2, dr=1)
    #     auxSurf.setParent(ikAuxGrp)
    #
    #
    #     # ---------------------------------------------------------------------
    #     # build master ctrl system
    #     masterJnts = []
    #     ratio = 1.0 / (masterCtrlNum - 1)
    #     for i in range(masterCtrlNum):
    #         vParam = ratio * i
    #         masterFol = utils.createFollicle(auxSurf, [0.5, vParam], "{0}_ik_master_{1:0>2d}_fol".format(prefix, i))
    #         masterCtrlRef = pm.createNode("transform", n="{0}_master_ref".format(prefix))
    #         utils.matchObject(masterFol, masterCtrlRef, 'trs')
    #         masterCtrlRef.setParent(masterFol)
    #         masterCtrlRef.rotate.set(90,0,90)
    #         masterFol.setParent(ikAuxGrp)
    #         masterCtrl = utils.createCtrl("{0}_ik_master_{1:0>2d}_ctrl".format(prefix, i), "locator", 1, "yellow")
    #         masterCtrlOrg = utils.createParentTransform("org", masterCtrl)
    #         utils.matchObject(masterFol, masterCtrlOrg)
    #         masterCtrlOrg.setParent(ikCtrlGrp)
    #         masterCtrlOff = utils.createParentTransform("off", masterCtrl)
    #         pm.parentConstraint(masterCtrlRef, masterCtrlOff, mo=0)
    #         masterJnt = pm.createNode("joint", n="{0}_ik_master_{1:0>2d}_jnt".format(prefix, i))
    #         masterJntOrg = utils.createParentTransform("org", masterJnt)
    #         masterJntOrg.setParent(ikAuxGrp)
    #         pm.parentConstraint(masterCtrl, masterJntOrg)
    #         masterJnts.append(masterJnt)
    #
    #     masterCrv = utils.createCurveFromJoint(masterJnts, "{0}_ik_master_crv".format(prefix), 1, 3)
    #     pm.skinCluster(masterJnts, masterCrv, n="{0}_ik_master_skc".format(prefix), mi=2, dr=1)
    #     masterCrv.setParent(ikAuxGrp)
    #
    #     # ---------------------------------------------------------------------
    #     # build sub ctrl system
    #     subJnts = []
    #     subCtrlNum = ibtSubCtrlNum + 1
    #     ratio1 = 1.0 / (subCtrlNum * (masterCtrlNum - 1))
    #     ratio2 = 1.0 / subCtrlNum
    #     for i in range(masterCtrlNum):
    #         for j in range(subCtrlNum if i < masterCtrlNum - 1 else 1):
    #             id = i * subCtrlNum + j
    #             subCtrl = utils.createCtrl("{0}_ik_sub_{1:0>2d}_ctrl".format(prefix, id), "locator", 0.5, "green")
    #             subCtrlOrg = pm.createNode("transform", n="{0}_ik_sub_{1:0>2d}_ctrl_org".format(prefix,
    #                                                                                             id))  # utils.createParentTransform("grp", subCtrl)
    #             subCtrlOrg.setParent(ikCtrlGrp)
    #             subCtrlOff = utils.createParentTransform("off", subCtrl)
    #             subCtrlRef = pm.createNode("transform", n="{0}_ik_sub_{1:0>2d}_ref".format(prefix, id))
    #             utils.matchObject(subCtrlOff, subCtrlRef)
    #             subCtrlRef.setParent(subCtrlOrg)
    #             subCtrlOff.setParent(subCtrlOrg)
    #
    #             # subCtrl position
    #             poci = pm.createNode("pointOnCurveInfo", n="{0}_ik_sub_{1:0>2d}_poci".format(prefix, id))
    #             vecp = pm.createNode("vectorProduct", n="{0}_ik_sub_{1:0>2d}_vecp".format(prefix, id))
    #             masterCrv.worldSpace[0].connect(poci.inputCurve)
    #             param = ratio1 * id
    #             poci.parameter.set(param)
    #             poci.turnOnPercentage.set(1)
    #             vecp.operation.set(4)
    #             poci.position.connect(vecp.input1)
    #             subCtrlOff.parentInverseMatrix[0].connect(vecp.matrix)
    #             vecp.output.connect(subCtrlOff.translate)
    #
    #             # subCtrl orientation
    #             if j == 0:
    #                 pm.orientConstraint(masterJnts[i], subCtrlRef)
    #             else:
    #                 oriCst = pm.orientConstraint(masterJnts[i], masterJnts[i + 1], subCtrlRef)
    #                 oriCst.interpType.set(2)
    #                 weightAttrs = pm.orientConstraint(oriCst, q=1, wal=1)
    #                 weight = min(1, max(0, ratio2*j))
    #                 pm.setAttr(weightAttrs[0], 1 - weight)
    #                 pm.setAttr(weightAttrs[1], weight)
    #             subCtrlTanCst = pm.tangentConstraint(masterCrv, subCtrlOff, wut=2)
    #             subCtrlRef.worldMatrix[0].connect(subCtrlTanCst.worldUpMatrix)
    #
    #             # build subJoints
    #             subJnt = pm.createNode("joint", n="{0}_ik_sub_{1:0>2d}_jnt".format(prefix, id))
    #             pm.addAttr(subJnt, ln="pociParam", at="float", k=0, dv=param)
    #             subJnts.append(subJnt)
    #             subJntOrg = utils.createParentTransform("org", subJnt)
    #             subJntOrg.setParent(ikAuxGrp)
    #             pm.parentConstraint(subCtrl, subJntOrg, mo=0)
    #
    #     subCrv = utils.createCurveFromJoint(subJnts, "{0}_ik_sub_crv".format(prefix), 1, 3)
    #     subCrvSkc = pm.skinCluster(subJnts, subCrv, n="{0}_ik_sub_skc".format(prefix), mi=2, dr=1)
    #     subCrv.setParent(ikAuxGrp)
    #
    #     # ---------------------------------------------------------------------
    #     # length preservation
    #     # compute restArcLength/currentArcLength ratio to determine where to detach the curve
    #     subCrvRbc = pm.rebuildCurve(subCrv, rpo=1, end=1, kr=0, rt=0, d=7, ch=1, s=64)[1]
    #     rLenMdl = pm.createNode("multDoubleLinear", n="{0}_restLength_mdl".format(prefix))
    #     rLenMdl.input1.set(pm.arclen(subCrv))
    #     rLenMdl.input2.set(1)
    #     ############TODO
    #     self.globalCtrl.globalScale.connect(rLenMdl.input2)
    #     subCrvInfo = pm.createNode("curveInfo", n="{0}_subCrv_cinfo".format(prefix))
    #     subCrvRbc.outputCurve.connect(subCrvInfo.inputCurve)
    #     lenRatioMd = pm.createNode("multiplyDivide", n="{0}_lenRatio_md".format(prefix))
    #     lenRatioMd.operation.set(2)
    #     subCrvInfo.arcLength.connect(lenRatioMd.input2X)
    #     rLenMdl.output.connect(lenRatioMd.input1X)
    #     lenRatioMdl = pm.createNode("multDoubleLinear", n="{0}_lenRatio_mdl".format(prefix))
    #     lenRatioMd.outputX.connect(lenRatioMdl.input1)
    #     metaCtrl.preserveLength.connect(lenRatioMdl.input2)
    #     preservelenRev = pm.createNode("reverse", n="{0}_preserveLen_rev".format(prefix))
    #     metaCtrl.preserveLength.connect(preservelenRev.inputX)
    #     lenRatioAdl = pm.createNode("addDoubleLinear", n="{0}_lenRatio_adl".format(prefix))
    #     lenRatioMdl.output.connect(lenRatioAdl.input1)
    #     preservelenRev.outputX.connect(lenRatioAdl.input2)
    #     lenClp = pm.createNode("clamp", n="{0}_preserveLen_clp".format(prefix))
    #     lenClp.minR.set(0.0)
    #     lenClp.maxR.set(1.0)
    #     lenRatioAdl.output.connect(lenClp.inputR)
    #     detachCrv = pm.createNode("detachCurve", n="{0}_preserveLen_dtc".format(prefix))
    #     subCrvRbc.outputCurve.connect(detachCrv.inputCurve)
    #     lenClp.outputR.connect(detachCrv.parameter[0])
    #     detachCrv.outputCurve[0].connect(subCrv.create, f=1)
    #
    #     # ---------------------------------------------------------------------
    #     # build ik aim joint chain
    #     aimJnts = utils.duplicateJointChain(joints[0], ("joint", "aimjoint"))
    #     aimRefs = []
    #     ratio = 1.0 / (jointNum - 1.0)
    #     ratio2 = subCtrlNum * (masterCtrlNum - 1.0) / (jointNum - 1.0)
    #     aimJntGrp = pm.createNode("transform", n="{0}_ik_aim_jnt_grp".format(prefix))
    #     aimRefGrp = pm.createNode("transform", n="{0}_ik_aim_ref_grp".format(prefix))
    #     aimRefGrp.setParent(ikAuxGrp)
    #     aimJntGrp.inheritsTransform.set(0)
    #     aimJntGrp.setParent(ikJntGrp)
    #     for i in range(jointNum):
    #         aimJntRef = pm.createNode("transform", n="{0}_ik_aim_{1:0>2d}_ref".format(prefix, i))
    #         aimJntRef.setParent(aimRefGrp)
    #         aimRefs.append(aimJntRef)
    #
    #         poci = pm.createNode("pointOnCurveInfo", n="{0}_ik_aim_{1:0>2d}_poci".format(prefix, id))
    #         poci.turnOnPercentage.set(1)
    #         subCrv.worldSpace[0].connect(poci.inputCurve)
    #         param = ratio * i
    #         poci.parameter.set(param)
    #
    #         vecp = pm.createNode("vectorProduct", n="{0}_ik_aim_{1:0>2d}_vecp".format(prefix, id))
    #         vecp.operation.set(4)
    #         poci.position.connect(vecp.input1)
    #         aimJntRef.parentInverseMatrix[0].connect(vecp.matrix)
    #         vecp.output.connect(aimJntRef.translate)
    #
    #         subJntId = int(i * ratio2)
    #         if i == jointNum - 1:
    #             pm.orientConstraint(subJnts[subJntId], aimJntRef)
    #         else:
    #             oriCst = pm.orientConstraint(subJnts[subJntId], subJnts[subJntId + 1], aimJntRef)
    #             oriCst.interpType.set(2)
    #             weight = min(1, max((param - subJnts[subJntId].pociParam.get()) / (
    #             subJnts[subJntId + 1].pociParam.get() - subJnts[subJntId].pociParam.get()), 0))
    #             weightAttrs = pm.orientConstraint(oriCst, q=1, wal=1)
    #             pm.setAttr(weightAttrs[0], weight)
    #             pm.setAttr(weightAttrs[1], 1 - weight)
    #
    #         aimJnt = aimJnts[i]
    #         if i == 0:
    #             aimJnt.setParent(aimJntGrp)
    #         else:
    #             aimJnt.setParent(aimJnts[i - 1])
    #             aimCst = pm.aimConstraint(aimJntRef, aimJnts[i - 1], wut=2)
    #             aimRefs[i - 1].worldMatrix[0].connect(aimCst.worldUpMatrix)
    #         if i == jointNum - 1:
    #             pm.orientConstraint(aimJntRef, aimJnts[i])
    #         pm.pointConstraint(aimJntRef, aimJnt)
    #     #
    #     # # build ik joint chain
    #     retJntGrp = pm.createNode("transform", n="{0}_ik_ret_jnt_grp".format(prefix))
    #     retJntGrp.setParent(ikJntGrp)
    #     utils.connectChannels(aimJntGrp, retJntGrp, 'trs')
    #     ikJnts = utils.duplicateJointChain(joints[0], ("joint", "ikjoint"))
    #     for i in range(jointNum):
    #         pm.parentConstraint(aimJnts[i], ikJnts[i], mo=1)
    #         self.globalCtrl.globalScale.connect(ikJnts[i].scaleY)
    #         self.globalCtrl.globalScale.connect(ikJnts[i].scaleZ)
    #     ikJnts[0].setParent(retJntGrp)
    #
    #     # ---------------------------------------------------------------------
    #     # TODO volume preservation
    #
    #
    #     # TODO bind proxy geo to validate building result
    #
    #
    #     return {"topCtrlGrp": ikCtrlGrp, "topJntGrp": ikJntGrp, "topAuxGrp": ikAuxGrp, "resultJnts": ikJnts}
    #