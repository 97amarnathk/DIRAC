#!/usr/bin/env python
########################################################################
# $HeadURL$
########################################################################
__RCSID__ = "$Id$"
import sys, os
import DIRAC
from DIRAC import gLogger
from DIRAC.Core.Base import Script

unit = 'GB'
Script.registerSwitch( "u:", "Unit=", "   Unit to use [%s] (MB,GB,TB,PB)" % unit )
Script.parseCommandLine( ignoreErrors = False )
for switch in Script.getUnprocessedSwitches():
  if switch[0].lower() == "u" or switch[0].lower() == "unit":
    unit = switch[1]
scaleDict = { 'MB' : 1000 * 1000.0,
              'GB' : 1000 * 1000 * 1000.0,
              'TB' : 1000 * 1000 * 1000 * 1000.0,
              'PB' : 1000 * 1000 * 1000 * 1000 * 1000.0}
if not unit in scaleDict.keys():
  gLogger.error( "Unit must be one of MB,GB,TB,PB" )
  DIRAC.exit( 2 )
scaleFactor = scaleDict[unit]

args = Script.getPositionalArgs()
lfns = []
for inputFileName in args:
  if os.path.exists( inputFileName ):
    inputFile = open( inputFileName, 'r' )
    string = inputFile.read()
    inputFile.close()
    lfns.extend( string.splitlines() )
  else:
    lfns.append( inputFileName )

from DIRAC.DataManagementSystem.Client.ReplicaManager import ReplicaManager
rm = ReplicaManager()

res = rm.getCatalogFileSize( lfns )
if not res['OK']:
  gLogger.error( "Failed to get size of data", res['Message'] )
  DIRAC.exit( -2 )
for lfn, reason in res['Value']['Failed'].items():
  gLogger.error( "Failed to get size for %s" % lfn, reason )
totalSize = 0
totalFiles = 0
for lfn, size in res['Value']['Successful'].items():
  totalFiles += 1
  totalSize += size
gLogger.info( '-' * 30 )
gLogger.info( '%s|%s' % ( 'Files'.ljust( 15 ), ( 'Size (%s)' % unit ).rjust( 15 ) ) )
gLogger.info( '-' * 30 )
gLogger.info( '%s|%s' % ( str( totalFiles ).ljust( 15 ), str( '%.1f' % ( totalSize / scaleFactor ) ).rjust( 15 ) ) )
gLogger.info( '-' * 30 )
DIRAC.exit( 0 )
