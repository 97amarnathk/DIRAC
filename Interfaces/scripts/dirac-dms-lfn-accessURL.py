#!/usr/bin/env python
########################################################################
# $HeadURL$
# File :   dirac-dms-lfn-accessURL
# Author : Stuart Paterson
########################################################################
__RCSID__   = "$Id$"
__VERSION__ = "$Revision: 1.1 $"
from DIRACEnvironment import DIRAC
from DIRAC.Core.Base import Script
from DIRAC.Interfaces.API.Dirac                         import Dirac

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

def usage():
  print 'Usage: %s <LFN> <SE>' %(Script.scriptName)
  DIRAC.exit(2)

if len(args) < 2:
  usage()

if len(args) > 2:
  print 'Only one LFN SE pair will be considered'

dirac = Dirac()
exitCode = 0
errorList = []

result = dirac.getAccessURL(args[0],args[1],printOutput=True)
if not result['OK']:
  errorList.append( (args[0], result['Message']) )
  exitCode = 2

for error in errorList:
  print "ERROR %s: %s" % error

DIRAC.exit(exitCode)