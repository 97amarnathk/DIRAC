#!/usr/bin/env python
########################################################################
# $HeadURL$
# File :    dirac-admin-submit-pilot-for-job
# Author :  Ricardo Graciani
########################################################################
__RCSID__ = "$Id$"
import DIRAC
from DIRAC.Core.Base import Script

Script.parseCommandLine( ignoreErrors = True )
args = Script.getPositionalArgs()

def usage():
  print 'Usage: %s [<options>] <JobID> [<JobID>]' % ( Script.scriptName )
  print ' Submit 1 dirac pilot for each <JobID>'
  DIRAC.exit( 2 )

if len( args ) < 1:
  usage()

from DIRAC.WorkloadManagementSystem.Agent.TaskQueueDirector import taskQueueDB, gLitePilotDirector

result = taskQueueDB.retrieveTaskQueues()
if not result['OK']:
  DIRAC.gLogger.error( 'Can not retrieve TaskQueue Definititions', result['Message'] )
  DIRAC.exit( 1 )

taskQueueDict = result['Value']

director = None
pilots = 0

for jobID in args:
  DIRAC.gLogger.info( 'Retrieving info for Job', jobID )
  result = taskQueueDB.getTaskQueueForJob( jobID )
  if not result['OK']:
    DIRAC.gLogger.error( 'Can not retrieve TaskQueue for Job', result['Message'] )
    continue
  tqID = result['Value']
  if not tqID in taskQueueDict:
    DIRAC.gLogger.error( 'Can not retrieve TaskQueue for Job' )
    continue
  taskQueueDict[tqID]['TaskQueueID'] = tqID
  if not director:
    director = gLitePilotDirector( 'gLite' )
    director.configure( '/', 'gLite' )

  result = director.submitPilots( taskQueueDict[tqID], 1 )

  if not result['OK']:
    DIRAC.gLogger.error( result['Message'] )
    continue

  pilots += result['Value']

  DIRAC.gLogger.info( 'Pilot Submitted' )

DIRAC.gLogger.info( '%s Pilots Submitted' % pilots )

DIRAC.exit()
