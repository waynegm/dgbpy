#
# (C) dGB Beheer B.V.; (LICENSE) http://opendtect.org/OpendTect_license.txt
# AUTHOR   : Arnaud
# DATE     : November 2018
#
# tools for reading hdf5 files for NN training
#

from os import path
import random
import json
import numpy as np
import h5py

import odpy.hdf5 as odhdf5
from odpy.common import std_msg

from dgbpy import dgbscikit
from dgbpy.keystr import *

hdf5ext = 'h5'

def getGroupNames( filenm ):
  h5file = h5py.File( filenm, 'r' )
  ret = list()
  for groupnm in h5file.keys():
    if isinstance( h5file[groupnm], h5py.Group ):
      ret.append( groupnm )
  h5file.close()
  return ret

def getInputNames( filenm ):
  h5file = h5py.File( filenm, 'r' )
  info = getInfo( filenm )
  ret = list(info[inputdictstr].keys())
  h5file.close()
  return ret

def getNrGroups( filenm ):
  return len(getGroupNames(filenm))

def getNrInputs( filenm ):
  return len(getInputNames(filenm))

def getInputID( info, inpnm ):
  return info[inputdictstr][inpnm]['id']

def getCubeLetNames( info, groupnms, inputs ):
  ret = {}
  for groupnm in groupnms:
    ret.update({groupnm: getCubeLetNamesByGroup(info,inputs,groupnm)} )
  return ret

def getCubeLetNamesByGroup( info, inputs, groupnm ):
  ret = {}
  for inp in inputs:
    ret.update({inp: getCubeLetNamesByGroupByInput(info,groupnm,inp)})
  return ret

def getCubeLetNamesByGroupByInput( info, groupnm, input ):
  h5file = h5py.File( info[filedictstr], 'r' )
  if not groupnm in h5file:
    return {}
  group = h5file[groupnm]
  dsetnms = list(group.keys())
  if xdatadictstr in dsetnms:
    ret = np.arange(len(group[xdatadictstr]))
  else:
    dsetwithinp = np.chararray.startswith( dsetnms, str(getInputID(info,input))+':' )
    ret = np.extract( dsetwithinp, dsetnms )
  h5file.close()
  return np.ndarray.tolist(ret)

def getGroupSize( filenm, groupnm ):
  h5file = h5py.File( filenm, 'r' )
  group = h5file[groupnm]
  size = len(group)
  h5file.close()
  return size

def get_nr_attribs( info, subkey=None ):
  try:
    inputinfo = info[inputdictstr]
  except KeyError:
    raise
  ret = 0
  for groupnm in inputinfo:
    if subkey != None and groupnm != subkey:
      continue
    groupinfo = inputinfo[groupnm]
    try:
      nrattrib = len(groupinfo[attribdictstr])
    except KeyError:
      try:
        nrattrib = len(groupinfo[logdictstr])
      except KeyError:
        return 0
    if nrattrib == 0:
      continue
    if ret == 0:
      ret = nrattrib
    elif nrattrib != ret:
      raise ValueError
  return ret

def get_np_shape( step, nrpts=None, nrattribs=None ):
  ret = ()
  if nrpts != None:
    ret += (nrpts,)
  if nrattribs != None:
    ret += (nrattribs,)
  if isinstance( step, int ):
    ret += ( 1,1,step*2+1, )
    return ret
  for i in step:
    ret += (i*2+1,)
  return ret

def getCubeLets( infos, datasets, groupnm ):
  survnm = groupnm.replace( ' ', '_' )
  fromwells = survnm in infos[inputdictstr]
  attribsel = None
  if fromwells:
    attribsel = survnm
  nrattribs = get_nr_attribs( infos, attribsel )
  stepout = infos[stepoutdictstr]
  isclass = infos[classdictstr]
  outdtype = np.float32
  if isclass:
    outdtype = np.uint8
  h5file = h5py.File( infos[filedictstr], 'r' )
  group = h5file[groupnm]
  dsetnms = list(group.keys())
  hasdata = None
  if xdatadictstr in dsetnms and ydatadictstr in dsetnms:
    x_data = group[xdatadictstr]
    y_data = group[ydatadictstr]
    allcubelets = list()
    alloutputs = list()
    for inputnm in datasets:
      dsetnms = datasets[inputnm]
      nrpts = len(dsetnms)
      shape = get_np_shape(stepout,nrpts,nrattribs)
      if len(x_data) == nrpts and len(y_data) == nrpts:
        cubelets = np.resize( x_data, shape ).astype( np.float32 )
        output = np.resize( y_data, (nrpts,infos[nroutdictstr]) ).astype( outdtype )
      else:
        cubelets = np.empty( shape, np.float32 )
        output = np.empty( (nrpts,infos[nroutdictstr]), outdtype )
        idx = 0
        for dsetnm in dsetnms:
          dset = x_data[dsetnm]
          odset = y_data[dsetnm]
          cubelets[idx] = np.resize(dset,cubelets[idx].shape)
          output[idx] = np.asarray( odset )
          idx += 1
      if nrpts > 0:
        allcubelets.append( cubelets )
        alloutputs.append( output )
    if len(allcubelets) > 0:
      cubelets = np.concatenate( allcubelets )
      hasdata = True
    if len(alloutputs) > 0:
      output = np.concatenate( alloutputs )
  else:
    allcubelets = list()
    alloutputs = list()
    for inputnm in datasets:
      dsetnms = datasets[inputnm]
      nrpts = len(dsetnms)
      shape = get_np_shape(stepout,nrpts,nrattribs)
      cubelets = np.empty( shape, np.float32 )
      output = np.empty( (nrpts,infos[nroutdictstr]), outdtype )
      idx = 0
      for dsetnm in dsetnms:
        dset = group[dsetnm]
        cubelets[idx] = np.resize(dset,cubelets[idx].shape)
        if isclass :
          output[idx] = odhdf5.getIArray( dset, valuestr )
        else:
          output[idx] = odhdf5.getDArray( dset, valuestr )
        idx += 1
      if nrpts > 0:
        allcubelets.append( cubelets )
        alloutputs.append( output )
    if len(allcubelets) > 0:
      cubelets = np.concatenate( allcubelets )
      hasdata = True
    if len(alloutputs) > 0:
      output = np.concatenate( alloutputs )
  h5file.close()
  if not hasdata:
    return {}
  return {
    xtraindictstr: cubelets,
    ytraindictstr: output
  }

def getDatasets_( infos, datasets, fortrain ):
  dictkeys = list()
  if fortrain:
    dictkeys.append( xtraindictstr )
    dictkeys.append( ytraindictstr )
  else:
    dictkeys.append( xvaliddictstr )
    dictkeys.append( yvaliddictstr )
  ret = {}
  cubelets = list()
  for groupnm in datasets:
    cubes = getCubeLets(infos,datasets[groupnm],groupnm)
    if len(cubes) > 0:
      cubelets.append( cubes )
  allx = list()
  ally = list()
  for cubelet in cubelets:
    allx.append( cubelet[xtraindictstr] )
    ally.append( cubelet[ytraindictstr] )
  if len(allx) > 0:
    ret.update({dictkeys[0]: np.concatenate( allx )})
    ret.update({dictkeys[1]: np.concatenate( ally )})
  return ret

def getDatasets( infos, dsetsel=None, train=True, validation=True ):
  ret = {}
  if dsetsel == None:
    datasets = infos[datasetdictstr]
  else:
    datasets = dsetsel
  if train:
    if traindictstr in datasets:
      traindsets = datasets[traindictstr]
    else:
      traindsets = datasets
    trainret = getDatasets_( infos, traindsets, True )
    if len(trainret) > 0:
      for ex in trainret:
        ret.update({ex: trainret[ex]})
  if validation and validdictstr in datasets:
    validret = getDatasets_( infos, datasets[validdictstr], False )
    if len(validret) > 0:
      for ex in validret:
        ret.update({ex: validret[ex]})
  return ret

def validInfo( info ):
  try:
    type = odhdf5.getText(info,typestr)
  except KeyError:
    std_msg("No type found. Probably wrong type of hdf5 file")
    return False
  return True

def getInfo( filenm ):
  h5file = h5py.File( filenm, 'r' )
  info = odhdf5.getInfoDataSet( h5file )
  if not validInfo( info ):
    h5file.close()
    return {}

  type = odhdf5.getText(info,typestr)
  if odhdf5.hasAttr(info,"Trace.Stepout"):
    stepout = odhdf5.getIStepInterval(info,"Trace.Stepout") 
  elif odhdf5.hasAttr(info,"Depth.Stepout"):
    stepout = odhdf5.getIStepInterval(info,"Depth.Stepout")
  classification = True
  ex_sz = odhdf5.getIntValue(info,"Examples.Size") 
  idx = 0
  nroutputs = 1
  examples = {}
  while idx < ex_sz:
    namestr = "Examples."+str(idx)+".Name"
    logstr = "Examples."+str(idx)+".Log"
    if odhdf5.hasAttr( info, logstr ):
      exname = logstr
      extype = "Logs"
    elif odhdf5.hasAttr( info, namestr ):
      exname = namestr
      extype = "Point-Sets"
    else:
      raise KeyError
    grouplbl = odhdf5.getText( info, exname )
    if idx == 0 and exname == logstr and isinstance( grouplbl, list ):
      nroutputs = len(grouplbl)
    example = {}
    example_sz = odhdf5.getIntValue(info,"Examples."+str(idx)+".Size")
    idy = 0
    while idy < example_sz:
      exyname = odhdf5.getText(info,"Examples."+str(idx)+".Name."+str(idy))
      exidstr = odhdf5.getText(info,"Examples."+str(idx)+".ID."+str(idy))
      exstruct = {namedictstr: exyname, iddictstr: idy, dbkeydictstr: exidstr}
      survstr = "Examples."+str(idx)+".Survey."+str(idy)
      if odhdf5.hasAttr( info, survstr ):
        exstruct.update({locationdictstr: odhdf5.getText(info,survstr)})
      example = {extype: exstruct}
      idy += 1
    example.update({iddictstr: idx})
    surveystr = "Examples."+str(idx)+".Survey"
    if odhdf5.hasAttr( info, surveystr ):
      surveyfp = path.split( odhdf5.getText(info, surveystr ) )
      surveynm = odhdf5.getText(info, "Examples."+str(idx)+".Name" )
      grouplbl = surveynm
      example.update({
        targetdictstr: odhdf5.getText( info, exname ),
        pathdictstr: surveyfp[0]
        })

    examples.update({grouplbl: example})
    idx += 1

  inp_sz = odhdf5.getIntValue(info,"Input.Size")
  idx = 0
  input = {}
  while idx < inp_sz:
    surveyfp = path.split( odhdf5.getText(info,"Input."+str(idx)+".Survey") )
    inp = {
      pathdictstr: surveyfp[0],
      iddictstr: idx
    }
    logsstr = "Input."+str(idx)+".Logs"
    inpp_sz = 0
    if odhdf5.hasAttr( info, logsstr ):
      inp.update({logdictstr: odhdf5.getText(info, logsstr )})
      inpp_sz = len( inp[logdictstr] )
    else:
      inpsizestr = 'Input.'+str(idx)+'.Size'
      if odhdf5.hasAttr( info, inpsizestr ):
        inpp_sz = odhdf5.getIntValue(info,inpsizestr)
    if inpp_sz > 0:
      idy = 0
      attriblist = list()
      scales = list()
      means = list()
      while idy < inpp_sz:
        attribinp = {}
        dsnamestr = 'Input.'+str(idx)+'.Name.'+str(idy)
        if odhdf5.hasAttr( info, dsnamestr ):
          attribinp.update({ namedictstr: odhdf5.getText(info,dsnamestr) })
        dbkeystr = 'Input.'+str(idx)+'.ID.'+str(idy)
        if odhdf5.hasAttr( info, dbkeystr ):
          attribinp.update({ dbkeydictstr: odhdf5.getText(info,dbkeystr) })
        if len(attribinp.keys()) > 0:
          attribinp.update({ iddictstr: idy })
        if len(attribinp.keys()) > 0:
          attriblist.append( attribinp )
        scalekey = "Input."+str(idx)+".Stats."+str(idy)
        if odhdf5.hasAttr(info,scalekey):
          scale = odhdf5.getDInterval(info,scalekey)
          means.append( scale[0] )
          scales.append( scale[1] )
        idy += 1
      if len(attriblist) > 0:
        inp.update({attribdictstr: attriblist} )
      if len(scales) > 0:
        inp.update({scaledictstr: dgbscikit.getNewScaler(means,scales) })

    input.update({surveyfp[1]: inp})
    idx += 1

  retinfo = {
    typedictstr: type,
    stepoutdictstr: stepout,
    classdictstr: True,
    nroutdictstr: nroutputs,
    interpoldictstr: odhdf5.getBoolValue(info,"Edge extrapolation"),
    exampledictstr: examples,
    inputdictstr: input,
    filedictstr: filenm
  }

  retinfo.update({
    datasetdictstr: getCubeLetNames( retinfo, examples.keys(), input.keys() )
  })
  if odhdf5.hasAttr(info,'Model.Type' ):
    retinfo.update({plfdictstr: odhdf5.getText(info,'Model.Type')})
  if  odhdf5.hasAttr(info,versionstr):
    retinfo.update({versiondictstr: odhdf5.getText(info,versionstr)})
  h5file.close()

  if type == loglogtypestr or type == seisproptypestr:
    return getWellInfo( retinfo, filenm )
  elif type == seisclasstypestr:
    return getAttribInfo( retinfo, filenm )

  std_msg( "Unrecognized dataset type: ", type )
  raise KeyError

def getAttribInfo( info, filenm ):
  if not info[classdictstr]:
    return info

  info.update( {classesdictstr: getClassIndices(info)} )
  return info

def getWellInfo( info, filenm ):
  h5file = h5py.File( filenm, 'r' )
  infods = odhdf5.getInfoDataSet( h5file )
  info[classdictstr] = odhdf5.hasAttr(infods,'Target Value Type') and odhdf5.getText(infods,'Target Value Type') == "ID"
  zstep = odhdf5.getDValue(infods,"Z step") 
  marker = (odhdf5.getText(infods,"Top marker"),
            odhdf5.getText(infods,"Bottom marker"))
  h5file.close()
  info.update({
    zstepdictstr: zstep,
    rangedictstr: marker,
  })
  return info

modeloutstr = 'Model.Output.'
def modelIdxStr( idx ):
  return modeloutstr + str(idx) + '.Name'

def addInfo( inpfile, plfnm, infos, filenm ):
  h5filein = h5py.File( inpfile, 'r' )
  h5fileout = h5py.File( filenm, 'r+' )
  dsinfoin = odhdf5.getInfoDataSet( h5filein )
  dsinfoout = odhdf5.ensureHasDataset( h5fileout )
  attribman = dsinfoin.attrs
  for attribkey in attribman:
    dsinfoout.attrs[attribkey] = attribman[attribkey]
  h5filein.close()
  odhdf5.setAttr( dsinfoout, versionstr, str(1) )
  odhdf5.setAttr( dsinfoout, 'Model.Type', plfnm )
  outps = getOutputs( inpfile )
  nrout = len(outps)
  odhdf5.setAttr( dsinfoout, modeloutstr+'Size', str(nrout) )
  for idx in range(nrout):
    odhdf5.setAttr( dsinfoout, modelIdxStr(idx), outps[idx] )

  from odpy.common import log_msg
  inp = infos[inputdictstr]
  for inputnm in inp:
    input = inp[inputnm]
    if not scaledictstr in input:
      continue
    scale = input[scaledictstr]
    keyval = 'Input.' + str(input[iddictstr]) + '.Stats.'
    for i in range(len(scale.scale_)):
      odhdf5.setAttr( dsinfoout, keyval+str(i), str(scale.mean_[i])+'`'+str(scale.scale_[i]) )

  h5fileout.close()

def getClassIndices( info, filternms=None ):
  ret = []
  for groupnm in info[exampledictstr]:
    if filternms==None or groupnm in filternms:
      ret.append( info[exampledictstr][groupnm][iddictstr] )
  return np.sort( ret )

def getOutputs( inpfile ):
  info = getInfo( inpfile )
  ret = list()
  type = info[typedictstr]
  isclassification = info[classdictstr]
  if isclassification:
    ret.append( classvalstr )
    if type == seisclasstypestr:
      ret.extend( getGroupNames(inpfile) )
    ret.append( confvalstr )
  elif type == loglogtypestr or type == seisproptypestr:
    firsttarget = next(iter(info[exampledictstr]))
    targets = info[exampledictstr][firsttarget][targetdictstr]
    if isinstance(targets,list):
      ret.extend(targets)
    else:
      ret.append(targets)

  return ret

def getOutputNames( filenm, indices ):
  h5file = h5py.File( filenm, 'r' )
  info = odhdf5.getInfoDataSet( h5file )
  ret = list()
  for idx in indices:
    ret.append( odhdf5.getText(info,modelIdxStr(idx)) )
  h5file.close()
  return ret
