#! /usr/bin/env python
########################################################################
# $HeadURL$
# File :    dirac-admin-bdii-ce-state
# Author :  Adria Casajus
########################################################################
"""
  Check info on BDII for CE state
"""
__RCSID__ = "$Id$"
import DIRAC
from DIRAC.Core.Base                                         import Script
from DIRAC.ConfigurationSystem.Client.Helpers                import getVO

Script.registerSwitch( "H:", "host=", "BDII host" )
Script.registerSwitch( "V:", "vo=", "vo" )
Script.setUsageMessage( '\n'.join( [ __doc__.split( '\n' )[1],
                                     'Usage:',
                                     '  %s [option|cfgfile] ... CE' % Script.scriptName,
                                     'Arguments:',
                                     '  CE:       Name of the CE(ie: ce111.cern.ch)'] ) )

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

from DIRAC.Interfaces.API.DiracAdmin                         import DiracAdmin

if not len( args ) == 1:
  Script.showHelp()

ce = args[0]

host = None
vo = getVO( 'lhcb' )
for unprocSw in Script.getUnprocessedSwitches():
  if unprocSw[0] in ( "H", "host" ):
        host = unprocSw[1]
  if unprocSw[0] in ( "V", "vo" ):
        vo = unprocSw[1]

diracAdmin = DiracAdmin()

result = diracAdmin.getBDIICEState( ce, useVO = vo, host = host )
if not result['OK']:
  print test['Message']
  DIRAC.exit( 2 )


ces = result['Value']
for ce in ces:
  print "CE: %s {" % ce.get( 'GlueCEUniqueID', 'Unknown' )
  for item in ce.iteritems():
    print "%s: %s" % item
  print "}"


