########################################################################
# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/WorkloadManagementSystem/Service/JobMonitoringHandler.py,v 1.29 2009/06/13 22:23:28 atsareg Exp $
########################################################################

""" JobMonitoringHandler is the implementation of the JobMonitoring service
    in the DISET framework

    The following methods are available in the Service interface



"""

__RCSID__ = "$Id: JobMonitoringHandler.py,v 1.29 2009/06/13 22:23:28 atsareg Exp $"

from types import *
from DIRAC.Core.DISET.RequestHandler import RequestHandler
from DIRAC import gLogger, gConfig, S_OK, S_ERROR
from DIRAC.WorkloadManagementSystem.DB.JobDB import JobDB
from DIRAC.WorkloadManagementSystem.DB.TaskQueueDB import TaskQueueDB
from DIRAC.WorkloadManagementSystem.DB.JobLoggingDB import JobLoggingDB
import DIRAC.Core.Utilities.Time as Time

# These are global instances of the DB classes
jobDB = False
jobLoggingDB = False
proxyRepository = False
taskQueueDB = False

SUMMARY = ['JobType','Site','JobName','Owner','SubmissionTime',
           'LastUpdateTime','Status','MinorStatus','ApplicationStatus']
SUMMARY = []
PRIMARY_SUMMARY = []

def initializeJobMonitoringHandler( serviceInfo ):

  global jobDB, jobLoggingDB, taskQueueDB
  jobDB = JobDB()
  jobLoggingDB = JobLoggingDB()
  taskQueueDB = TaskQueueDB()
  return S_OK()

class JobMonitoringHandler( RequestHandler ):


##############################################################################
  types_getApplicationStates = []
  def export_getApplicationStates (self):
    """ Return Distict Values of ApplicationStatus job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'ApplicationStatus' )

##############################################################################
  types_getJobTypes = []
  def export_getJobTypes (self):
    """ Return Distict Values of JobType job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'JobType' )

##############################################################################
  types_getOwners = []
  def export_getOwners (self):
    """
    Return Distict Values of Owner job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'Owner' )

##############################################################################
  types_getProductionIds = []
  def export_getProductionIds (self):
    """
    Return Distict Values of ProductionId job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'JobGroup' )

##############################################################################
  types_getJobGroups = []
  def export_getJobGroups(self):
    """
    Return Distict Values of ProductionId job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'JobGroup' )

##############################################################################
  types_getSites = []
  def export_getSites (self):
    """
    Return Distict Values of Site job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'Site' )

##############################################################################
  types_getStates = []
  def export_getStates (self):
    """
    Return Distict Values of Status job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'Status' )

 ##############################################################################
  types_getMinorStates = []
  def export_getMinorStates (self):
    """
    Return Distinct Values of Minor Status job Attribute in WMS
    """
    return jobDB.getDistinctJobAttributes( 'MinorStatus' )

##############################################################################
  types_getJobs = []
  def export_getJobs (self, attrDict=None, cutDate=None):
    """
    Return list of JobIds matching the condition given in attrDict
    """
    queryDict = {}

    #if attrDict:
    #  if type ( attrDict ) != DictType:
    #    return S_ERROR( 'Argument must be of Dict Type' )
    #  for attribute in self.queryAttributes:
    #    # Only those Attribute in self.queryAttributes can be used
    #    if attrDict.has_key(attribute):
    #      queryDict[attribute] = attrDict[attribute]

    print attrDict

    return jobDB.selectJobs( attrDict, newer=cutDate)

##############################################################################
  types_getCounters = [ ListType ]
  def export_getCounters( self, attrList, attrDict={}, cutDate=''):
    """
    Retrieve list of distinct attributes values from attrList
    with attrDict as condition.
    For each set of distinct values, count number of occurences.
    Return a list. Each item is a list with 2 items, the list of distinct
    attribute values and the counter
    """

    # Check that Attributes in attrList and attrDict, they must be in
    # self.queryAttributes.

    #for attr in attrList:
    #  try:
    #    self.queryAttributes.index(attr)
    #  except:
    #    return S_ERROR( 'Requested Attribute not Allowed: %s.' % attr )
    #
    #for attr in attrDict:
    #  try:
    #    self.queryAttributes.index(attr)
    #  except:
    #    return S_ERROR( 'Condition Attribute not Allowed: %s.' % attr )


    cutdate = str(cutDate)

    return jobDB.getCounters( 'Jobs',attrList, attrDict, newer=cutDate, timeStamp='LastUpdateTime')

##############################################################################
  types_getJobStatus = [ IntType ]
  def export_getJobStatus (self, jobID ):

    return jobDB.getJobAttribute(jobID, 'Status')

##############################################################################
  types_getJobOwner = [ IntType ]
  def export_getJobOwner (self, jobID ):

    return jobDB.getJobAttribute(jobID,'Owner')

##############################################################################
  types_getJobSite = [ IntType ]
  def export_getJobSite (self, jobID ):

    return jobDB.getJobAttribute(jobID, 'Site')

##############################################################################
  types_getJobJDL = [ IntType ]
  def export_getJobJDL (self, jobID ):

    result = jobDB.getJobJDL(jobID)
    return result

##############################################################################
  types_getJobLoggingInfo = [ IntType ]
  def export_getJobLoggingInfo(self, jobID):

    return jobLoggingDB.getJobLoggingInfo(jobID)

##############################################################################
  types_getJobsStatus = [ ListType ]
  def export_getJobsStatus (self, jobIDs):

    return jobDB.getAttributesForJobList( jobIDs, ['Status'] )

##############################################################################
  types_getJobsMinorStatus = [ ListType ]
  def export_getJobsMinorStatus (self, jobIDs):

    return jobDB.getAttributesForJobList( jobIDs, ['MinorStatus'] )

##############################################################################
  types_getJobsApplicationStatus = [ ListType ]
  def export_getJobsApplicationStatus (self, jobIDs):

    return jobDB.getAttributesForJobList( jobIDs, ['ApplicationStatus'] )

##############################################################################
  types_getJobsSites = [ ListType ]
  def export_getJobsSites (self, jobIDs):

    return jobDB.getAttributesForJobList( jobIDs, ['Site'] )

##############################################################################
  types_getJobSummary = [ IntType ]
  def export_getJobSummary(self, jobID):
    return jobDB.getJobAttributes(jobID, SUMMARY)

##############################################################################
  types_getJobPrimarySummary = [ IntType ]
  def export_getJobPrimarySummary(self, jobID ):
    return jobDB.getJobAttributes(jobID, PRIMARY_SUMMARY)

##############################################################################
  types_getJobsSummary = [ ListType ]
  def export_getJobsSummary(self, jobIDs):

    if not jobIDs:
      return S_ERROR('JobMonitoring.getJobsSummary: Received empty job list')

    result = jobDB.getAttributesForJobList( jobIDs, SUMMARY )
    #return result
    restring = str(result['Value'])
    return S_OK(restring)

##############################################################################
  types_getJobPageSummaryWeb = [DictType, ListType, IntType, IntType]
  def export_getJobPageSummaryWeb(self, selectDict, sortList, startItem, maxItems):
    """ Get the summary of the job information for a given page in the
        job monitor in a generic format
    """

    resultDict = {}
    startDate = selectDict.get('FromDate',None)
    if startDate:
      del selectDict['FromDate']
    # For backward compatibility
    startDate = selectDict.get('LastUpdate',None)
    if startDate:
      del selectDict['LastUpdate']
    # For backward compatibility  
    endDate = selectDict('ToDate')
    if endDate:
      del selectDict['FromDate']  

    # Sorting instructions. Only one for the moment.
    if sortList:
      orderAttribute = sortList[0][0]+":"+sortList[0][1]
    else:
      orderAttribute = None

    result = jobDB.selectJobs(selectDict, orderAttribute=orderAttribute, 
                              newer=startDate, older=endDate )
    if not result['OK']:
      return S_ERROR('Failed to select jobs: '+result['Message'])

    jobList = result['Value']
    nJobs = len(jobList)
    resultDict['TotalRecords'] = nJobs
    if nJobs == 0:
      return S_OK(resultDict)

    iniJob = startItem
    lastJob = iniJob + maxItems
    if iniJob >= nJobs:
      return S_ERROR('Item number out of range')

    if lastJob > nJobs:
      lastJob = nJobs

    summaryJobList = jobList[iniJob:lastJob]
    result = jobDB.getAttributesForJobList(summaryJobList,SUMMARY)
    if not result['OK']:
      return S_ERROR('Failed to get job summary: '+result['Message'])

    summaryDict = result['Value']

    # Evaluate last sign of life time
    for jobID, jobDict in summaryDict.items():
      if jobDict['HeartBeatTime'] == 'None':
        jobDict['LastSignOfLife'] = jobDict['LastUpdateTime']
      else:
        lastTime = Time.fromString(jobDict['LastUpdateTime'])
        hbTime = Time.fromString(jobDict['HeartBeatTime'])
        if (hbTime-lastTime) > (lastTime-lastTime) or jobDict['Status'] == "Stalled":
          jobDict['LastSignOfLife'] = jobDict['HeartBeatTime']
        else:
          jobDict['LastSignOfLife'] = jobDict['LastUpdateTime']
    
    tqDict = {}      
    result = taskQueueDB.getTaskQueueForJobs(summaryJobList)
    if result['OK']:
      tqDict = result['Value']      
      
    # prepare the standard structure now
    key = summaryDict.keys()[0]
    paramNames = summaryDict[key].keys()

    records = []
    for jobID, jobDict in summaryDict.items():
      jParList = []
      for pname in paramNames:
        jParList.append(jobDict[pname])
      if tqDict and tqDict.has_key(jobID):
        jParList.append(tqDict[jobID])
      else:
        jParList.append(0)    
      records.append(jParList)

    resultDict['ParameterNames'] = paramNames + ['TaskQueueID']   
    resultDict['Records'] = records
    
    statusDict = {}
    result = jobDB.getCounters('Jobs',['Status'],selectDict,
                               newer=last_update,
                               timeStamp='LastUpdateTime')
    if result['OK']:
      for stDict,count in result['Value']:
         statusDict[stDict['Status']] = count
    resultDict['Extras'] = statusDict

    return S_OK(resultDict)


##############################################################################
  types_getJobsPrimarySummary = [ ListType ]
  def export_getJobsPrimarySummary (self, jobIDs):
    return jobDB.getAttributesForJobList( jobIDs, PRIMARY_SUMMARY )

##############################################################################
  types_getJobParameter = [ [IntType,LongType] , StringType ]
  def export_getJobParameter( self, jobID, parName ):
    return jobDB.getJobParameters( jobID, [parName] )

##############################################################################
  types_getJobParameters = [ [IntType,LongType] ]
  def export_getJobParameters( self, jobID ):
    return jobDB.getJobParameters( jobID )
  
##############################################################################
  types_getAtticJobParameters = [ [IntType,LongType] ]
  def export_getAtticJobParameters( self,jobID,parameters=[],rescheduleCycle=-1 ):
    return jobDB.getAtticJobParameters( jobID,parameters,rescheduleCycle )      

##############################################################################
  types_getJobAttributes = [ IntType ]
  def export_getJobAttributes( self, jobID ):
    return jobDB.getJobAttributes( jobID )

##############################################################################
  types_getSiteSummary = [ ]
  def export_getSiteSummary( self ):
    return jobDB.getSiteSummary()

##############################################################################
  types_getJobHeartBeatData = [ IntType ]
  def export_getJobHeartBeatData( self, jobID ):
    return jobDB.getHeartBeatData( jobID )

##############################################################################
  types_getInputData = [ [IntType, LongType] ]
  def export_getInputData( self, jobID ):
    """ Get input data for the specified jobs
    """
    return  jobDB.getInputData(jobID)
