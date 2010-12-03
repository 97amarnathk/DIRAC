#! /usr/bin/env python
########################################################################
# $HeadURL$
# File :    dirac-admin-bdii-ce-voview
# Author :  Adria Casajus
########################################################################
"""
  Check info on BDII for VO view of CE
"""
__RCSID__ = "$Id$"
import DIRAC
from DIRAC.Core.Base                                         import Script

Script.registerSwitch( "H:", "host=", "BDII host" )
Script.registerSwitch( "V:", "vo=", "vo" )
Script.setUsageMessage( '\n'.join( [ __doc__.split( '\n' )[1],
                                     'Usage:',
                                     '  %s [option|cfgfile] ... CE' % Script.scriptName,
                                     'Arguments:',
                                     '  CE: Name of the CE(ie: ce111.cern.ch)'] ) )

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

from DIRAC.Interfaces.API.DiracAdmin                         import DiracAdmin
from DIRAC.ConfigurationSystem.Client.Helpers                import getVO

def usage():
  Script.showHelp()
  DIRAC.exit( 2 )

if not len( args ) == 1:
  usage()

ce = args[0]

host = None
vo = getVO( 'lhcb' )
for unprocSw in Script.getUnprocessedSwitches():
  if unprocSw[0] in ( "H", "host" ):
        host = unprocSw[1]
  if unprocSw[0] in ( "V", "vo" ):
        vo = unprocSw[1]

diracAdmin = DiracAdmin()

result = diracAdmin.getBDIICEVOView( ce, useVO = vo, host = host )
if not ['OK']:
  print test['Message']
  DIRAC.exit( 2 )


ces = result['Value']
for ce in ces:
  print "CEVOView: %s {" % ce.get( 'GlueChunkKey', 'Unknown' )
  for item in ce.iteritems():
    print "%s: %s" % item
  print "}"


