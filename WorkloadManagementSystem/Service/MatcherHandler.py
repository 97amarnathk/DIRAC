########################################################################
# $Id$
########################################################################
"""
Matcher class. It matches Agent Site capabilities to job requirements.
It also provides an XMLRPC interface to the Matcher

"""

__RCSID__ = "$Id$"

import re, os, sys, time
import string
import signal, fcntl, socket
import getopt
from   types import *
import threading

from DIRAC.Core.DISET.RequestHandler                   import RequestHandler
from DIRAC.Core.Utilities.ClassAd.ClassAdLight         import ClassAd
from DIRAC                                             import gConfig, gLogger, S_OK, S_ERROR
from DIRAC.WorkloadManagementSystem.DB.JobDB           import JobDB
from DIRAC.WorkloadManagementSystem.DB.JobLoggingDB    import JobLoggingDB
from DIRAC.WorkloadManagementSystem.DB.TaskQueueDB     import TaskQueueDB
from DIRAC                                             import gMonitor
from DIRAC.Core.Utilities.ThreadScheduler              import gThreadScheduler

DEBUG = 0

gMutex = threading.Semaphore()
gTaskQueues = {}
jobDB = False
jobLoggingDB = False
taskQueueDB = False

def initializeMatcherHandler( serviceInfo ):
  """  Matcher Service initialization
  """

  global jobDB
  global jobLoggingDB
  global taskQueueDB

  jobDB = JobDB()
  jobLoggingDB = JobLoggingDB()
  taskQueueDB = TaskQueueDB()

  gMonitor.registerActivity( 'matchTime', "Job matching time", 'Matching', "secs" , gMonitor.OP_MEAN, 300 )
  gMonitor.registerActivity( 'matchTaskQueues', "Task queues checked per job", 'Matching', "task queues" , gMonitor.OP_MEAN, 300 )
  gMonitor.registerActivity( 'matchesDone', "Job Matches", 'Matching', "matches" , gMonitor.OP_MEAN, 300 )
  gMonitor.registerActivity( 'numTQs', "Number of Task Queues", 'Matching', "tqsk queues" , gMonitor.OP_MEAN, 300 )

  taskQueueDB.recalculateTQSharesForAll()
  gThreadScheduler.addPeriodicTask( 120, taskQueueDB.recalculateTQSharesForAll )
  gThreadScheduler.addPeriodicTask( 120, sendNumTaskQueues )

  sendNumTaskQueues()

  return S_OK()

def sendNumTaskQueues():
  result = taskQueueDB.getNumTaskQueues()
  if result[ 'OK' ]:
    gMonitor.addMark( 'numTQs', result[ 'Value' ] )
  else:
    gLogger.error( "Cannot get the number of task queues", result[ 'Message' ] )

class MatcherHandler( RequestHandler ):

  def initialize( self ):

    self.siteJobLimits = self.getCSOption( "SiteJobLimits", False )
    self.checkPilotVersion = self.getCSOption( "CheckPilotVersion", True )
    self.setup = gConfig.getValue( '/DIRAC/Setup', '' )
    self.vo = gConfig.getValue( '/DIRAC/VirtualOrganization', '' )
    self.pilotVersion = gConfig.getValue( '/Operations/%s/%s/Versions/PilotVersion' % ( self.vo, self.setup ), '' )

  def selectJob( self, resourceDescription ):
    """ Main job selection function to find the highest priority job
        matching the resource capacity
    """

    startTime = time.time()

    # Check and form the resource description dictionary
    resourceDict = {}
    if type( resourceDescription ) in StringTypes:
      classAdAgent = ClassAd( resourceDescription )
      if not classAdAgent.isOK():
        return S_ERROR( 'Illegal Resource JDL' )
      gLogger.verbose( classAdAgent.asJDL() )

      for name in taskQueueDB.getSingleValueTQDefFields():
        if classAdAgent.lookupAttribute( name ):
          if name == 'CPUTime':
            resourceDict[name] = classAdAgent.getAttributeInt( name )
          else:
            resourceDict[name] = classAdAgent.getAttributeString( name )

      for name in taskQueueDB.getMultiValueMatchFields():
        if classAdAgent.lookupAttribute( name ):
          resourceDict[name] = classAdAgent.getAttributeString( name )

      # Check if a JobID is requested
      if classAdAgent.lookupAttribute( 'JobID' ):
        resourceDict['JobID'] = classAdAgent.getAttributeInt( 'JobID' )

      if classAdAgent.lookupAttribute( 'DIRACVersion' ):
        resourceDict['DIRACVersion'] = classAdAgent.getAttributeString( 'DIRACVersion' )

    else:
      for name in taskQueueDB.getSingleValueTQDefFields():
        if resourceDescription.has_key( name ):
          resourceDict[name] = resourceDescription[name]

      for name in taskQueueDB.getMultiValueMatchFields():
        if resourceDescription.has_key( name ):
          resourceDict[name] = resourceDescription[name]

      if resourceDescription.has_key( 'JobID' ):
        resourceDict['JobID'] = resourceDescription['JobID']
      if resourceDescription.has_key( 'DIRACVersion' ):
        resourceDict['DIRACVersion'] = resourceDescription['DIRACVersion']

    # Check the pilot DIRAC version
    if self.checkPilotVersion:
      if 'DIRACVersion' in resourceDict:
        if resourceDict['DIRACVersion'] != self.pilotVersion:
          return S_ERROR( 'Pilot version does not match the production version %s:%s' % \
                         ( resourceDict['DIRACVersion'], self.pilotVersion ) )

    # Get common site mask and check the agent site
    result = jobDB.getSiteMask( siteState = 'Active' )
    if result['OK']:
      maskList = result['Value']
    else:
      return S_ERROR( 'Internal error: can not get site mask' )

    if not 'Site' in resourceDict:
      return S_ERROR( 'Missing Site Name in Resource JDL' )

    siteName = resourceDict['Site']
    if resourceDict['Site'] not in maskList:
      if 'GridCE' in resourceDict:
        del resourceDict['Site']
      else:
        return S_ERROR( 'Site not in mask and GridCE not specified' )

    resourceDict['Setup'] = self.serviceInfoDict['clientSetup']

    if DEBUG:
      print "Resource description:"
      for k, v in resourceDict.items():
        print k.rjust( 20 ), v

    # Check if Job Limits are imposed onto the site
    extraConditions = {}
    if self.siteJobLimits:
      result = self.getExtraConditions( siteName )
      if not result['OK']:
        return result
      extraConditions = result['Value']
    if extraConditions:
      gLogger.info( 'Job Limits for site %s are: %s' % ( siteName, str( extraConditions ) ) )

    result = taskQueueDB.matchAndGetJob( resourceDict, extraConditions = extraConditions )

    if DEBUG:
      print result

    if not result['OK']:
      return result
    result = result['Value']
    if not result['matchFound']:
      return S_ERROR( 'No match found' )

    jobID = result['jobId']
    resAtt = jobDB.getJobAttributes( jobID, ['OwnerDN', 'OwnerGroup', 'Status'] )
    if not resAtt['OK']:
      return S_ERROR( 'Could not retrieve job attributes' )
    if not resAtt['Value']:
      return S_ERROR( 'No attributes returned for job' )
    if not resAtt['Value']['Status'] == 'Waiting':
      gLogger.error( 'Job %s matched by the TQ is not in Waiting state' % str( jobID ) )
      result = taskQueueDB.deleteJob( jobID )

    result = jobDB.setJobStatus( jobID, status = 'Matched', minor = 'Assigned' )
    result = jobLoggingDB.addLoggingRecord( jobID,
                                           status = 'Matched',
                                           minor = 'Assigned',
                                           source = 'Matcher' )

    result = jobDB.getJobJDL( jobID )
    if not result['OK']:
      return S_ERROR( 'Failed to get the job JDL' )

    resultDict = {}
    resultDict['JDL'] = result['Value']
    resultDict['JobID'] = jobID

    matchTime = time.time() - startTime
    gLogger.info( "Match time: [%s]" % str( matchTime ) )
    gMonitor.addMark( "matchTime", matchTime )

    # Get some extra stuff into the response returned
    resOpt = jobDB.getJobOptParameters( jobID )
    if resOpt['OK']:
      for key, value in resOpt['Value'].items():
        resultDict[key] = value
    resAtt = jobDB.getJobAttributes( jobID, ['OwnerDN', 'OwnerGroup'] )
    if not resAtt['OK']:
      return S_ERROR( 'Could not retrieve job attributes' )
    if not resAtt['Value']:
      return S_ERROR( 'No attributes returned for job' )

    resultDict['DN'] = resAtt['Value']['OwnerDN']
    resultDict['Group'] = resAtt['Value']['OwnerGroup']
    return S_OK( resultDict )

  def getExtraConditions( self, site ):
    """ Get extra conditions allowing site throttling
    """
    # Find Site job limits
    grid, siteName, country = site.split( '.' )
    siteSection = '/Resources/Sites/%s/%s' % ( grid, site )
    result = gConfig.getSections( '%s/JobLimits' % siteSection )
    if not result['OK']:
      return result
    sections = result['Value']
    limitDict = {}
    resultDict = {}
    if sections:
      for section in sections:
        result = gConfig.getOptionsDict( '%s/JobLimits/%s' % ( siteSection, section ) )
        if not result['OK']:
          return result
        optionDict = result['Value']
        if optionDict:
          limitDict[section] = []
          for k, v in optionDict.items():
            limitDict[section].append( ( k, int( v ) ) )
    if not limitDict:
      return S_OK( {} )
    # Check if the site exceeding the given limits
    fields = limitDict.keys()
    for field in fields:
      for key, value in limitDict[field]:
        result = jobDB.getCounters( 'Jobs', ['Status'], {'Site':site, field:key} )
        if not result['OK']:
          return result
        count = 0
        if result['Value']:
          for countDict, number in result['Value']:
            if countDict['Status'] == "Running":
              count = number
              break
        if count > value:
          if not resultDict.has_key( field ):
            resultDict[field] = []
          resultDict[field].append( key )

    return S_OK( resultDict )

##############################################################################
  types_requestJob = [ [StringType, DictType] ]
  def export_requestJob( self, resourceDescription ):
    """ Serve a job to the request of an agent which is the highest priority
        one matching the agent's site capacity
    """

    result = self.selectJob( resourceDescription )
    gMonitor.addMark( "matchesDone" )
    return result

##############################################################################
  types_getActiveTaskQueues = []
  def export_getActiveTaskQueues( self ):
    """ Return all task queues
    """
    return taskQueueDB.retrieveTaskQueues()

##############################################################################
  types_getMatchingTaskQueues = [ DictType ]
  def export_getMatchingTaskQueues( self, resourceDict ):
    """ Return all task queues
    """
    return taskQueueDB.retrieveTaskQueuesThatMatch( resourceDict )

