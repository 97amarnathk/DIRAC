#! /usr/bin/env python

import DIRAC
from DIRAC.Core.Base                                         import Script

Script.registerSwitch( "H:", "host=", "BDII host" )

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

from DIRAC.Interfaces.API.DiracAdmin                         import DiracAdmin

def usage():
  print 'Usage: %s ce' %(Script.scriptName)
  DIRAC.exit(2)

if not len(args)==1:
  usage()

ce = args[0]

host = None

for unprocSw in Script.getUnprocessedSwitches():
  if unprocSw[0] in ( "h", "host" ):
        host = unprocSw[1]

diracAdmin = DiracAdmin()

result = diracAdmin.getBDIICE(ce, host=host)
if not ['OK']:
  print test['Message']
  DIRAC.exit(2)  

ces = result['Value']
for ce in ces:
  print "CE: %s {"%ce.get('GlueSubClusterName','Unknown')
  for item in ce.iteritems():
    print "%s: %s"%item
  print "}"


