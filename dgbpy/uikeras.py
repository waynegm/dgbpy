#__________________________________________________________________________
#
# (C) dGB Beheer B.V.; (LICENSE) http://opendtect.org/OpendTect_license.txt
# Author:        A. Huck
# Date:          Apr 2019
#
# _________________________________________________________________________

from functools import partial

import numpy as np
from enum import Enum

from bokeh.layouts import column
from bokeh.models.widgets import CheckboxGroup, Div, Select, Slider, RadioGroup

from odpy.common import log_msg
from dgbpy.dgbkeras import *
from dgbpy.transforms import hasOpenCV
from dgbpy import uibokeh

info = None

def getPlatformNm( full=False ):
  if full:
    return platform
  return getMLPlatform()

def getSizeStr( sizeinbytes ):
  ret = 'Size: '
  try:
    import humanfriendly
    ret += humanfriendly.format_size( sizeinbytes )
  except Exception as e:
    ret += str(int(sizeinbytes)) + ' bytes'
  return ret

def getUiModelTypes( learntype, classification, ndim ):
  ret = ()
  for model in getModelsByType( learntype, classification, ndim ):
    ret += ((model,),)

  return dgbkeys.getNames( ret )

def getUiPars(uipars=None):
  dict = keras_dict
  learntype = info[dgbkeys.learntypedictstr]
  if isinstance(info[dgbkeys.inpshapedictstr], int):
    ndim = 1
  else:
    ndim = len(info[dgbkeys.inpshapedictstr])
  modeltypes = getUiModelTypes( learntype, info[dgbkeys.classdictstr], ndim )
  if len(modeltypes)==0:
    divfld = Div(text="""No Keras models found for this workflow.""")
    parsgrp = column(divfld)
    return {'grp': parsgrp,
            'uiobjects':{
              'divfld': divfld
            }
           }
  defmodel = modeltypes[0]
  defbatchsz = keras_dict['batch']
  estimatedsz = info[dgbkeys.estimatedsizedictstr]
  isCrossVal = dgbhdf5.isCrossValidation(info)
  if kc.UserModel.isImg2Img( defmodel ):
      defbatchsz = 4
  uiobjs = {}
  if not uipars:
    uiobjs = {
      'modeltypfld': Select(title='Type', options=modeltypes),
      'validfld' : Slider(start=1,end=1000, title='Number of input for validation', visible = False),
      'batchfld': Select(title='Batch Size',options=cudacores),
      'epochfld': Slider(start=1,end=1000, title='Epochs'),
      'patiencefld': Slider(start=1,end=100, title='Patience'),
      'lrfld': Slider(start=-10,end=-1,step=1, title='Initial Learning Rate (1e)'),
      'edfld': Slider(start=1,end=100, title='Epoch drop (%)', step=0.1),
      'sizefld': Div( text='Size: Unknown' ),
      'dodecimatefld': CheckboxGroup( labels=['Decimate input']),
      'chunkfld': Slider(start=1,end=100, title='Number of Chunks'),
      'rundevicefld': CheckboxGroup( labels=['Train on GPU'], visible=can_use_gpu())
    }
    if isCrossVal:
      uiobjs['validfld'].visible = True
      uiobjs['validfld'].end = dgbhdf5.getNrGroupInputs(info)
    if estimatedsz:
      uiobjs['sizefld'] = Div( text=getSizeStr( estimatedsz ) )
    uiobjs['dodecimatefld'].on_click(partial(decimateCB,chunkfld=uiobjs['chunkfld'],sizefld=uiobjs['sizefld']))
    try:
      uiobjs['chunkfld'].on_change('value_throttled',partial(chunkfldCB, uiobjs['sizefld']))
    except AttributeError:
      log_msg( '[WARNING] Bokeh version too old, consider updating it.' )
      pass
    parsgrp = column(*list(uiobjs.values()))
    uipars = {'grp': parsgrp, 'uiobjects': uiobjs}
  else:
    uiobjs = uipars['uiobjects']
    
  uiobjs['modeltypfld'].value = defmodel
  uiobjs['batchfld'].value = str(defbatchsz)
  uiobjs['epochfld'].value = dict['epochs']
  uiobjs['patiencefld'].value = dict['patience']
  uiobjs['lrfld'].value = np.log10(dict['learnrate'])
  uiobjs['edfld'].value = 100*dict['epochdrop']/uiobjs['epochfld'].value
  if estimatedsz:
    uiobjs['sizefld'].text = getSizeStr(estimatedsz)
  if isCrossVal:
    uiobjs['validfld'].visible = True
    uiobjs['validfld'].value = 1
  uiobjs['dodecimatefld'].active = []
  uiobjs['chunkfld'].value = dict['nbchunk']
  uiobjs['rundevicefld'].active = [0]
  decimateCB( uiobjs['dodecimatefld'].active,uiobjs['chunkfld'],uiobjs['sizefld'] )
  return uipars

def getAdvancedUiPars(uipars=None):
  dict = keras_dict
  uiobjs={}
  if not uipars:
    uiobjs = {
      'tensorboardfld': CheckboxGroup(labels=['Enable Tensorboard'], visible=True, margin=(5, 5, 0, 5)),
      'cleartensorboardfld': CheckboxGroup(labels=['Clear Tensorboard log files'], visible=True, margin=(5, 5, 0, 5))
    }

    if not dgbhdf5.isLogOutput(info):
      aug_labels = ['Random Flip', 'Random Gaussian Noise', 'Random Polarity Flip']
      if hasOpenCV(): aug_labels.append('Random Rotation')
      if dgbhdf5.isSeisClass(info): aug_labels.append('Random Translation')
      transformUi = {
        'scalingheadfld' :Div(text="""<strong>Data Scaling</strong>""", height = 10),
        'scalingfld': RadioGroup(labels=[dgbkeys.globalstdtypestr, dgbkeys.localstdtypestr, dgbkeys.normalizetypestr, dgbkeys.minmaxtypestr],
                                active=0, margin = [5, 5, 5, 25]),
        'augmentheadfld': Div(text="""<strong>Data Augmentation</strong>""", height = 10),
        'augmentfld': CheckboxGroup(labels=aug_labels, visible=True, margin=(5, 5, 5, 25)),
        }
      uiobjs = {**transformUi, **uiobjs}

    parsgrp = column(*list(uiobjs.values()))
    uipars = {'grp':parsgrp, 'uiobjects':uiobjs}
  else:
    uiobjs=uipars['uiobjects']

  if 'augmentfld' in uiobjs:
    setDefaultTransforms = []
    for transform in dict['transform']:
      setDefaultTransforms.append(uiTransform[transform].value)
    uiobjs['augmentfld'].active = setDefaultTransforms
  uiobjs['tensorboardfld'].active = [] if not dict['withtensorboard'] else [0]
  uiobjs['cleartensorboardfld'].active = []
  return uipars

def chunkfldCB(sizefld,attr,old,new):
  size = info[dgbkeys.estimatedsizedictstr]
  if sizefld and size:
    sizefld.text = getSizeStr( size/new )

def getUiTransforms(advkerasgrp):
  transforms = []
  if 'augmentfld' in advkerasgrp:
    selectedkeys = advkerasgrp['augmentfld'].active
    for key in selectedkeys:
      transforms.append(uiTransform(key).name)
  return transforms

def getUiScaler(advkerasgrp):
  scalers = (dgbkeys.globalstdtypestr, dgbkeys.localstdtypestr, dgbkeys.normalizetypestr, dgbkeys.minmaxtypestr)
  selectedOption = 0
  if 'scalinfld' in advkerasgrp:
    selectedOption = advkerasgrp['scalingfld'].active
  return scalers[selectedOption]

def getUiParams( keraspars, advkeraspars ):
  kerasgrp = keraspars['uiobjects']
  advkerasgrp = advkeraspars['uiobjects']
  nrepochs = kerasgrp['epochfld'].value
  epochdroprate = kerasgrp['edfld'].value / 100
  epochdrop = int(nrepochs*epochdroprate)
  validation_split = 0.2
  if dgbhdf5.isCrossValidation(info):
    validation_split = kerasgrp['validfld'].value
  if epochdrop < 1:
    epochdrop = 1
  runoncpu = not kerasgrp['rundevicefld'].visible or \
             not isSelected( kerasgrp['rundevicefld'] )
  scale = getUiScaler(advkerasgrp)
  transform = getUiTransforms(advkerasgrp)
  withtensorboard = True if len(advkerasgrp['tensorboardfld'].active)!=0 else False
  return getParams( dodec=isSelected(kerasgrp['dodecimatefld']), \
                             nbchunk=kerasgrp['chunkfld'].value, \
                             epochs=kerasgrp['epochfld'].value, \
                             batch=int(kerasgrp['batchfld'].value), \
                             patience=kerasgrp['patiencefld'].value, \
                             learnrate= 10 ** kerasgrp['lrfld'].value, \
                             epochdrop=epochdrop, \
                             validation_split = validation_split, \
                             nntype=kerasgrp['modeltypfld'].value, \
                             prefercpu=runoncpu, scale=scale, transform=transform, \
                             withtensorboard=withtensorboard)

def isSelected( fldwidget, index=0 ):
  return uibokeh.integerListContains( fldwidget.active, index )

def decimateCB( widgetactivelist,chunkfld,sizefld ):
  decimate = uibokeh.integerListContains( widgetactivelist, 0 )
  chunkfld.visible = decimate
  size = info[dgbkeys.estimatedsizedictstr]
  if sizefld and size:
    if decimate:
      size /= chunkfld.value
  sizefld.text = getSizeStr( size )

class uiTransform(Enum):
  RandomFlip = 0
  RandomGaussianNoise = 1
  RandomTranslation = 2
  RandomPolarityFlip = 3
  RandomRotation = 4
