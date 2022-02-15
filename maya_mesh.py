"""
I needed custom meshes, so here's a quick exporter.
I lifted this from another project and I recall there was something
wrong with the bind poses so do not rely on the skinning too much.

u8[3]: ascii file type "MSH"
u8: binary file verison (starts at 0, may get bumped in the future)
u8[4]: ascii exporter identifier (like "MAYA" for the Maya exporter, or "CONV" for the Assimp converter)
u32: mesh count
for each mesh:
  u32: name length
  u8[name length]: utf8 encoded name
  u32: material name length
  u8[material name length]: utf8 encoded name
  u32: attribute count
  for each attribute:
    u32: semantic ID (see semantics below)
    u32: number of floats for this attribute (must be 1, 2, 3 or 4)
  u32: number of floats in the interleaved vertex buffer
  u32: number of ints in the index buffer, we only support triangle data so this must be divisible by 3
  f32[]: all vertex data, each vertex is packed together floats in the order as the attributes were specified
  u32[]: all index data

Semantics are "magic numbers" that we agree to use in vertex shaders using layout syntax:
layout(location=0) vec3 aPosition;

Valid semantics are defined in the VertexAttribute.Semantic class in mesh.py:

Note that colors can go on indefinitely, for any additional data
that needs to be stored. They can have different meanings per shader
and are left open like this so you can create advanced effects with
specific data encoded in the model.

BLENDWEIGHTS are joint weights, each vertex can be smooth-skinned to
a maximum of 4 joints. Weights should be sorted high-to-low and normalized
(the shaders will not do any normalization, and if weight[0] == 0 skinning
is skipped).

BLENDINDICES are joint ids, the matrices at these indices will be used
when weighting the nvertices. If a joint is unused, set the id to 0 (or don't
add this attribute if the mesh is not skinned).
"""

import uuid
import os
import struct
import json
import enum

from maya import cmds
from maya.api.OpenMaya import MGlobal, MSpace, MItMeshPolygon, MFnMesh, MColor
from maya.api.OpenMayaAnim import MFnSkinCluster


# Copied from mesh.py because else Maya needs to install PyOpenGL OR I need to fix my imports
class VertexAttribute:
    class Semantic(enum.Enum):
        POSITION = 0
        NORMAL = 1
        TANGENT = 2
        TEXCOORD0 = 3
        TEXCOORD1 = 4
        TEXCOORD2 = 5
        TEXCOORD3 = 6
        TEXCOORD4 = 7
        TEXCOORD5 = 8
        TEXCOORD6 = 9
        TEXCOORD7 = 10
        BLENDINDICES = 11
        BLENDWEIGHT = 12
        COLOR0 = 13
        # COLOR# = COLOR0 + i


def getJointIndexMap(inSkinCluster):
    inConns = cmds.listConnections('%s.matrix' % inSkinCluster, s=1, d=0, c=1, type="joint")
    indices = []
    _connectDict = {}
    for i in inConns[::2]:
        indices.append(int(i[i.index("[") + 1: -1]))
    for index, conn in enumerate(inConns[1::2]):
        _connectDict[cmds.ls(conn, sl=0, l=1)[0]] = indices[index]
    return _connectDict


def getJointBindPoses(joints):
    _skinMap = {}
    matrices = []
    for joint in joints:
        # sk = cmds.listConnections(joint, s=0, d=1, type="skinCluster") or None
        # if sk[0] not in _skinMap.keys():
        #     _skinMap[sk[0]] = getJointIndexMap(sk[0])
        # worldInvMatrix = cmds.getAttr("%s.bindPreMatrix[%s]" % (sk[0], _skinMap[sk[0]][joint]))
        worldInvMatrix = cmds.getAttr("%s.worldInverseMatrix[0]" % joint)
        matrices.append(worldInvMatrix)
    return matrices


def exportSkeleton(target):
    skinnedJoints = []

    allJoints = cmds.ls(type="joint", l=True) or []
    for joint in allJoints:
        if not cmds.listConnections(joint, s=False, d=True, type="skinCluster"):
            continue
        skinnedJoints.append(joint)
    # Export bind pose
    matrices = getJointBindPoses(skinnedJoints)
    # TODO [low priority]: I'm in doubt if we shouldn't just import the serialization logic and use a Document instead
    # Set up default skeleton asset
    skeletonPath = os.path.splitext(target)[0] + '.json'
    skeletonData = {
        '_': 'Skeleton',
        'metaPosition': [0.0, 0.0],
        'name': os.path.splitext(os.path.basename(skeletonPath))[0],
        'uuid': str(uuid.uuid4())
    }
    # Sync it with whatever is on disk (if anything)
    if os.path.exists(skeletonPath):
        with open(skeletonPath, 'r') as fh:
            existingData = fh.read()
        if existingData:
            skeletonData.update(json.loads(existingData)[0])
    # Set the data we wish to write
    skeletonData['debugNames'] = skinnedJoints
    skeletonData['bindPose'] = matrices
    # Save the skeleton bind-pose
    with open(skeletonPath, 'w') as fh:
        json.dump([skeletonData], fh)

    return {joint: i for i, joint in enumerate(skinnedJoints)}


def skinClusterData(skinCluster, meshPath, component):
    # now if we have a skincluster lets fill in the blanks we had before
    selectionList2 = MGlobal.getSelectionListByName(skinCluster[0])
    skinObj = selectionList2.getDependNode(0)
    skinFn = MFnSkinCluster(skinObj)
    indexMap = {y: x for x, y in getJointIndexMap(skinCluster[0]).items()}
    jointWeights = skinFn.getWeights(meshPath, component)[0]
    return indexMap, jointWeights


def exportAllMeshes(source, target, isSkinned=False):
    if source:
        cmds.file(source, open=True, force=True)

    if isSkinned:
        skinnedJoints = exportSkeleton(target)
    else:
        skinnedJoints = []

    with open(target, 'wb') as fh:
        # write version
        fh.write(b'MSH\0MAYA')

        meshes = cmds.ls(type='mesh', ni=True, l=True)

        # write mesh count
        fh.write(struct.pack('<I', len(meshes)))

        for mesh in meshes:
            # write mesh name
            name = mesh.encode('utf8')
            fh.write(struct.pack('<I', len(name)))
            fh.write(name)

            # write material name
            try:
                lambert = \
                cmds.listConnections(cmds.listConnections(mesh, type='shadingEngine'), d=False, s=True, type='lambert')[
                    0]
            except:
                lambert = ''
            material = lambert.encode('utf8')
            fh.write(struct.pack('<I', len(material)))
            fh.write(material)

            # get API handles to object name
            selectionList = MGlobal.getSelectionListByName(mesh)
            dagPath = selectionList.getDagPath(0)
            polyIterator = MItMeshPolygon(dagPath)
            meshFn = MFnMesh(dagPath)

            jointWeights = []
            logicalIndexMap = {}
            physicalToLogicalMap = {}

            if isSkinned:
                # if we flag the mesh as skinned lets have a look if we have a skincluster
                # some of these values are predetermined so if it turns out not to be skinned then we leave it alone
                skinCluster = cmds.ls(cmds.listHistory(mesh), type="skinCluster")
                if skinCluster:
                    meshPath, component = selectionList.getComponent(0)
                    logicalIndexMap, jointWeights = skinClusterData(skinCluster, meshPath, component)
                    physicalToLogicalMap = {physicalIndex: logicalIndex for (physicalIndex, logicalIndex) in
                                            enumerate(logicalIndexMap.keys())}
                else:
                    isSkinned = False

            # extract mesh data in 1 go, uses more memory but faster to execute and I assume a duplicate of 1 mesh will fit in memory
            normals = meshFn.getNormals(MSpace.kWorld)
            tangents = meshFn.getTangents(MSpace.kWorld)
            uvSetNames = meshFn.getUVSetNames()
            colorSetNames = meshFn.getColorSetNames()

            # write attribute layout now we know all the attributes
            floatsPerVertex = 3 + 3 + 3 + len(uvSetNames) * 2 + len(colorSetNames) * 4 + int(isSkinned) * 8

            # num attributes
            fh.write(struct.pack('<I', 3 + len(uvSetNames) + len(colorSetNames) + int(isSkinned) * 2))
            # write position, normal and tangent attributes: semantic & nr of floats
            fh.write(struct.pack('<II', VertexAttribute.Semantic.POSITION.value, 3))
            fh.write(struct.pack('<II', VertexAttribute.Semantic.NORMAL.value, 3))
            fh.write(struct.pack('<II', VertexAttribute.Semantic.TANGENT.value, 3))

            for i, n in enumerate(uvSetNames):
                assert i < 8, 'We currently only anticipated 8 texcoords, please use a color set instead.'
                fh.write(struct.pack('<II', VertexAttribute.Semantic.TEXCOORD0.value + i, 2))

            for i, n in enumerate(colorSetNames):
                fh.write(struct.pack('<II', VertexAttribute.Semantic.COLOR0.value + i, 4))

            if isSkinned:
                fh.write(struct.pack('<II', VertexAttribute.Semantic.BLENDINDICES.value, 4))
                fh.write(struct.pack('<II', VertexAttribute.Semantic.BLENDWEIGHT.value, 4))

            # storage
            vertexDataHashes = {}
            vertexData = []
            indexData = []

            # pre-alloc
            uvSets = [None] * len(uvSetNames)
            colorSets = [None] * len(colorSetNames)
            vertexChunk = [0.0] * floatsPerVertex

            # walk mesh faces
            while not polyIterator.isDone():
                positions, vertexIndices = polyIterator.getTriangles(MSpace.kWorld)
                # get colors and uvs for this face
                for index, n in enumerate(uvSetNames):
                    u, v = polyIterator.getUVs(n)
                    uvSets[index] = (u, v, n)
                for index, n in enumerate(colorSetNames):
                    c = polyIterator.getColors(n)
                    colorSets[index] = (c, n)
                # itr.getNormals(normals, MSpace.kWorld)
                untriangulatedVertexIndices = polyIterator.getVertices()
                localVertexIndices = {j: i for i, j in enumerate(untriangulatedVertexIndices)}

                # walk face triangulation
                for i in range(len(vertexIndices)):
                    localVertexIndex = localVertexIndices[vertexIndices[i]]
                    # build vertex data for this face-vertex
                    P = positions[i]
                    N = normals[polyIterator.normalIndex(localVertexIndex)]
                    T = tangents[polyIterator.tangentIndex(localVertexIndex)]
                    vertexChunk[:9] = P.x, P.y, P.z, N.x, N.y, N.z, T.x, T.y, T.z
                    j = 9

                    for u, v, n in uvSets:
                        vertexChunk[j] = u[localVertexIndex]
                        vertexChunk[j + 1] = v[localVertexIndex]
                        j += 2

                    for c, n in colorSets:
                        C = c[localVertexIndex]
                        vertexChunk[j] = C.r
                        vertexChunk[j + 1] = C.g
                        vertexChunk[j + 2] = C.b
                        vertexChunk[j + 3] = C.a
                        j += 4

                    if isSkinned:
                        jointCount = len(logicalIndexMap)
                        weightRange = list(
                            jointWeights[vertexIndices[i] * jointCount:(vertexIndices[i] + 1) * jointCount])
                        highToLow = sorted(enumerate(weightRange), key=lambda pair: -pair[1])

                        MAX_INDICES = 4
                        padded = highToLow[:MAX_INDICES] + [(0, 0.0)] * (MAX_INDICES - len(highToLow))
                        factor = sum(pair[1] for pair in padded)
                        if factor:
                            factor = 1.0 / factor

                        for index, (jointId, weight) in enumerate(padded):
                            # this jointId is local to this skin-cluster,
                            # use the indexMap to extract the name and then map it to a global jointId
                            logicalIndex = physicalToLogicalMap[jointId]
                            index = logicalIndexMap[logicalIndex]
                            vertexChunk[j + index] = skinnedJoints.get(index, 0)
                            vertexChunk[j + MAX_INDICES + index] = weight * factor  # normalized

                        j += MAX_INDICES * 2

                    vertex = tuple(vertexChunk)
                    hsh = hash(vertex)
                    # reuse vertex data if possible
                    n = len(vertexDataHashes)
                    vertexId = vertexDataHashes.setdefault(hsh, n)
                    if vertexId == n:
                        vertexData.append(vertex)
                    # build index buffer
                    indexData.append(vertexId)
                polyIterator.next()

            # write buffer sizes
            fh.write(struct.pack('<II', len(vertexData) * floatsPerVertex, len(indexData)))
            # write mesh data
            for vertex in vertexData:
                fh.write(struct.pack('<%if' % floatsPerVertex, *vertex))
            fh.write(struct.pack('<%iI' % len(indexData), *indexData))


def exportAllMeshesAuto(skin=False):
    sn = cmds.file(q=True, sn=True)
    if not sn:
        cmds.error('Must save the scene first!')
        return
    exportAllMeshes(None, sn, skin)


if __name__ == '__main__':
    import os
    from maya import standalone

    standalone.initialize('Python')

    if __name__ == '__main__':
        source = 'shitori.ma'
        target = 'shitori.mesh'

        exportAllMeshes(source, target)
