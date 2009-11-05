#!/usr/bin/env python
########################################################################
# $HeadURL$
# File :   dirac-admin-get-pilot-logging-info.py
# Author : Stuart Paterson
########################################################################
__RCSID__   = "$Id$"
__VERSION__ = "$Revision: 1.1 $"
from DIRACEnvironment import DIRAC
from DIRAC.Core.Base import Script
from DIRAC.Interfaces.API.DiracAdmin                         import DiracAdmin

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

def usage():
  print 'Usage: %s <Grid pilot reference> [<Grid pilot reference>]' %(Script.scriptName)
  DIRAC.exit(2)

if len(args) < 1:
  usage()

diracAdmin = DiracAdmin()
exitCode = 0
errorList = []

for gridID in args:

  result = diracAdmin.getPilotLoggingInfo(gridID)
  if not result['OK']:
    errorList.append( ( gridID, result['Message']) )
    exitCode = 2
  else:
    print 'Pilot Reference: %s', gridID
    print result['Value']
    print

for error in errorList:
  print "ERROR %s: %s" % error

DIRAC.exit(exitCode)