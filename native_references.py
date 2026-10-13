"""Native string references that OpenVSP 3.52.2 does not expose as API setters.

Keys follow FeaLayer/FeaBC/FeaConnection/FeaFixPoint EncodeXml in the matching official
FeaStructure.cpp. All writes are to a transactional native file and reloaded
by OpenVSP; material and constraint math remain in the native engine.
"""
from pathlib import Path
import uuid
import os
import xml.etree.ElementTree as ET


class ReloadRequired(Exception):
    """Reopen the edited native document in a fresh engine process."""
    def __init__(self,request=None):
        super().__init__()
        self.request=request


def document(v):
    path=Path.cwd()/('reference-'+uuid.uuid4().hex+'.vsp3')
    filename=v.GetVSPFileName()
    try:
        v.WriteVSPFile(str(path),v.SET_ALL)
        return path,ET.parse(path)
    finally:
        v.SetVSP3FileName(filename)


def references(v):
    path,tree=document(v)
    result={}
    for tag,keys in [('FeaPropertyInfo',['FeaMaterialID']),('FeaLayerInfo',['FeaLaminaID']),('FeaBCInfo',['PartID','SubSurfID']),
                     ('Connection',['StartFixPtID','StartStructID','EndFixPtID','EndStructID']),
                     ('FeaPartInfo',['ParentFeaPartID','OtherGeomID'])]:
        for node in tree.findall('.//'+tag):
            cid=node.findtext('ParmContainer/ID')
            if not cid:continue
            parent=node.find('ParmContainer') if tag in ('FeaBCInfo','FeaPartInfo') else node
            result[cid]={key:parent.findtext(key,'') for key in keys}
            if tag=='FeaPartInfo':result[cid].update({key:node.findtext(key,'') for key in ('FeaPropertyID','CapFeaPropertyID')})
    for node in tree.findall('.//SubSurface')+tree.findall('.//FeaSubSurface'):
        cid=node.findtext('ParmContainer/ID')
        if cid:result[cid]=dict(regionType=int(node.findtext('SubSurfaceInfo/Type')),IntersectID=node.findtext('IntersectID',''),**{key:node.findtext(key,'') for key in ('FeaPropertyID','CapFeaPropertyID')})
    for node in tree.findall('.//SubSurface')+tree.findall('.//FeaSubSurface'):
        cid=node.findtext('ParmContainer/ID');curve=node.find('XSecCurve')
        if cid and curve is not None:
            result.setdefault(cid,{}).update(regionType=int(node.findtext('SubSurfaceInfo/Type')),curveID=curve.findtext('ParmContainer/ID'),curveType=int(curve.findtext('XSecCurve/Type')))
    for node in tree.findall('.//Geom'):
        curve=node.find('Geom/Auxiliary/XSecCurve');cid=node.findtext('ParmContainer/ID')
        if cid and curve is not None:
            choices=curve.findtext('XSecCurve/XSecCurveDriverGroup/ChoiceVec','')
            result.setdefault(cid,{}).update(curveID=curve.findtext('ParmContainer/ID'),curveType=int(curve.findtext('XSecCurve/Type')),curveDrivers=[int(x.strip()) for x in choices.split(',') if x.strip()])
            values=[float(x.strip()) for x in node.findtext('Geom/Auxiliary/CCEFilePnts','').split(',') if x.strip()]
            result[cid]['ccePoints']=[values[i:i+3] for i in range(0,len(values),3)]
    for node in tree.findall('.//Geom'):
        curve=node.find('XSecCurve');cid=node.findtext('ParmContainer/ID')
        if cid and curve is not None:
            choices=curve.findtext('XSecCurve/XSecCurveDriverGroup/ChoiceVec','')
            result.setdefault(cid,{}).update(curveID=curve.findtext('ParmContainer/ID'),curveType=int(curve.findtext('XSecCurve/Type')),curveDrivers=[int(x.strip()) for x in choices.split(',') if x.strip()])
    for node in tree.findall('.//GeometryAnalysis'):
        cid=node.findtext('ParmContainer/ID')
        if cid:result[cid]=dict(**{k:node.findtext(k,'') for k in ['PrimaryModeID','PrimaryGeomID','SecondaryGeomID','DirectionGeomID']},cutouts=[n.text or '' for n in node.findall('CutoutSS_List/CutoutSS/cutoutSS_ID')])
    for node in tree.findall('.//CFDMeshSettings'):
        cid=node.findtext('ParmContainer/ID')
        if cid:result[cid]=dict(ModeID=node.findtext('ModeID',''),FarGeomID=node.findtext('FarGeomID',''))
    for node in tree.findall('.//WaveDragMgr'):
        cid=node.findtext('ParmContainer/ID')
        if cid:result[cid]=dict(ReferenceGeomID=node.findtext('ReferenceGeomID',''),ModeID=node.findtext('ModeID',''),flowFaces=[n.findtext('flowSS_ID','') for n in node.findall('FlowSS_List/FlowSS')])
    for node in tree.findall('.//ParasiteDragMgr'):
        cid=node.findtext('ParmContainer/ID')
        if cid:result[cid]={key:node.findtext(key,'') for key in ('ReferenceGeomID','ModeID')}
    for node in tree.findall('.//VSPAEROSettings/Rotor'):
        cid=node.findtext('ParmContainer/ID')
        if cid:
            choices=node.findtext('DriverGroup/ChoiceVec','')
            result[cid]=dict(propDrivers=[int(x.strip()) for x in choices.split(',') if x.strip()],rotorParent=node.findtext('ParentID',''),rotorSurface=int(node.findtext('SurfIndex','-1')))
    path.unlink()
    return result


def set_reference(v,cid,tag,key,value):
    return set_references(v,cid,tag,{key:value})


def set_references(v,cid,tag,values):
    filename=v.GetVSPFileName()
    path,tree=document(v)
    try:
        matches=[n for n in tree.findall('.//'+tag) if n.findtext('ParmContainer/ID')==cid]
        if len(matches)!=1:raise ValueError('The native reference owner no longer exists.')
        for key,value in values.items():
            node=matches[0].find('ParmContainer') if tag=='FeaBCInfo' or (tag=='FeaPartInfo' and key not in ('FeaPropertyID','CapFeaPropertyID')) else matches[0]
            target=node.find(key)
            if target is None:target=ET.SubElement(node,key)
            target.text=value
        tree.write(path,encoding='utf-8',xml_declaration=True)
        os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    # Reading a second document in the same engine can remap layer IDs. A fresh
    # native process validates the reference and returns stable persisted IDs.
    raise ReloadRequired()
