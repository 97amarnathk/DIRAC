#!/usr/bin/env python
########################################################################
# $HeadURL$
# File :   dirac-proxy-init.py
# Author : Adrian Casajus
########################################################################
__RCSID__   = "$Id$"
__VERSION__ = "$Revision: 1.10 $"

import sys
import os.path
import DIRAC
from DIRAC.Core.Base import Script
from DIRAC.Core.Utilities.NTP import getClockDeviation


class Params:

  proxyLoc = False
  checkExists = False
  vomsEnabled = True
  csEnabled = True
  steps = False
  checkValid = False
  checkClock = True

  def showVersion( self, arg ):
    print "Version:"
    print " ", __RCSID__
    print " ", __VERSION__
    sys.exit(0)
    return DIRAC.S_OK()

  def setProxyLocation( self, arg ):
    self.proxyLoc = arg
    return DIRAC.S_OK()

  def checkExists( self, arg ):
    self.checkExists = True
    return DIRAC.S_OK()

  def disableVOMS( self, arg ):
    self.vomsEnabled = False
    return DIRAC.S_OK()

  def disableCS( self, arg ):
    self.csEnabled = False
    return DIRAC.S_OK()

  def showSteps( self, arg ):
    self.steps = True
    return DIRAC.S_OK()

  def validityCheck( self, arg ):
    self.checkValid = True
    return DIRAC.S_OK()

  def disableClockCheck( self, arg ):
    self.checkClock = False
    return DIRAC.S_OK()

params = Params()

Script.registerSwitch( "f:", "file=", "File to use as user key", params.setProxyLocation )
Script.registerSwitch( "i", "version", "Print version", params.showVersion )
Script.registerSwitch( "n", "novoms", "Disable VOMS", params.disableVOMS )
Script.registerSwitch( "v", "checkvalid", "Return error if the proxy is invalid", params.validityCheck )
Script.registerSwitch( "x", "nocs", "Disable CS", params.disableCS )
Script.registerSwitch( "e", "steps", "Show steps info", params.showSteps )
Script.registerSwitch( "j", "noclockcheck", "Disable checking if time is ok", params.disableClockCheck )

Script.disableCS()
Script.parseCommandLine()

if params.csEnabled:
  retVal = Script.enableCS()
  if not retVal[ 'OK' ]:
    print "Cannot contact CS to get user list"

from DIRAC.Core.Security.Misc import *
from DIRAC.Core.Security import CS, VOMS

if params.checkClock:
  result = getClockDeviation()
  if not result[ 'OK' ]:
    print "Error: %s" % result[ 'Message' ]
  else:
    deviation = result[ 'Value' ]
    if deviation > 600:
      print "Error: Your host clock seems to be off by more than TEN MINUTES! Thats really bad."
    elif deviation > 180:
      print "Error: Your host clock seems to be off by more than THREE minutes! Thats bad."
    elif deviation > 60:
      print "Error: Your host clock seems to be off by more than a minute! Thats not good."


result = getProxyInfo( params.proxyLoc, not params.vomsEnabled )
if not result[ 'OK' ]:
  print "Error: %s" % result[ 'Message' ]
  sys.exit(1)
infoDict = result[ 'Value' ]
print formatProxyInfoAsString( infoDict )

if params.steps:
  print "== Steps extended info =="
  chain = infoDict[ 'chain' ]
  stepInfo = getProxyStepsInfo( chain )[ 'Value' ]
  print formatProxyStepsInfoAsString( stepInfo )

def invalidProxy( msg ):
  print "[INVALID] %s" % msg
  sys.exit(1)


if params.checkValid:
  if infoDict[ 'secondsLeft' ] == 0:
    invalidProxy( "Proxy is expired" )
  if not infoDict[ 'validGroup' ]:
    invalidProxy( "Group %s is not valid" % infoDict[ 'group' ] )
  if 'hasVOMS' in infoDict and infoDict[ 'hasVOMS' ]:
    requiredVOMS = CS.getVOMSAttributeForGroup( infoDict[ 'group' ] )
    if 'VOMS' not in infoDict or not infoDict[ 'VOMS' ]:
      pinvalidProxy( "Unable to retrieve VOMS extension" )
    if len( infoDict[ 'VOMS' ] ) > 1:
      invalidProxy( "More than one voms attribute found" )
    if requiredVOMS not in infoDict[ 'VOMS' ]:
      invalidProxy( "Unexpected VOMS extension %s. Extension expected for DIRAC group is %s" % (
                                                                                 infoDict[ 'VOMS' ][0],
                                                                                 requiredVOMS ) )
    result = VOMS.VOMS().getVOMSProxyInfo( infoDict[ 'chain' ], 'actime' )
    if not result[ 'OK' ]:
      invalidProxy( "Cannot determine life time of VOMS attributes: %s" % result[ 'Message' ] )
    if int( result[ 'Value' ].strip() ) == 0:
      invalidProxy( "VOMS attributes are expired" )

sys.exit(0)