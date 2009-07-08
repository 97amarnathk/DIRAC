########################################################################
# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/StagerSystem/Agent/SiteMonitor.py,v 1.18 2009/07/08 09:13:06 acsmith Exp $
# File :   SiteMonitor.py
# Author : Stuart Paterson
########################################################################

"""  The SiteMonitor base-class monitors staging requests for a given site.
"""

__RCSID__ = "$Id: SiteMonitor.py,v 1.18 2009/07/08 09:13:06 acsmith Exp $"

from DIRAC.StagerSystem.Client.StagerClient                import StagerClient
from DIRAC.DataManagementSystem.Client.StorageElement      import StorageElement
from DIRAC.DataManagementSystem.Client.FileCatalog import FileCatalog
from DIRAC.Core.Utilities.SiteSEMapping                    import getSEsForSite
from DIRAC                                                 import S_OK, S_ERROR, gConfig, gLogger
import os, sys, re, string, time
from threading import Thread
from DIRAC.AccountingSystem.Client.Types.DataOperation import DataOperation
from DIRAC.AccountingSystem.Client.DataStoreClient import gDataStoreClient
from DIRAC.Core.Utilities import Time
class SiteMonitor(Thread):

  #############################################################################
  def __init__(self,configPath,siteName):
    """ Constructor for SiteMonitor
    """
    logSiteName = string.split(siteName,'.')[1]
    self.log = gLogger.getSubLogger(logSiteName)
    self.site = siteName
    self.configSection = configPath
    self.pollingTime = gConfig.getValue(self.configSection+'/PollingTime',60) #Seconds
    self.fileSelectLimit = gConfig.getValue(self.configSection+'/FileSelectLimit',1000)
    self.stageRepeatTime = gConfig.getValue(self.configSection+'/StageRepeatTime',21600) # e.g. 6hrs
    self.stageRetryMax = gConfig.getValue(self.configSection+'/StageRetryMax',4) # e.g. after 4 * 6 hrs
    self.taskSelectLimit = gConfig.getValue(self.configSection+'/TaskSelectLimit',100) # e.g. after 24hrs
    self.stagerClient = StagerClient()
    self.fc = FileCatalog()
    Thread.__init__(self)
    self.setDaemon( True )

  #############################################################################
  def run(self):
    """ The run method of the SiteMonitor thread
    """
    while True:
      self.pollingTime = gConfig.getValue(self.configSection+'/PollingTime',60) #Seconds
      self.log.info( 'Waking up SiteMonitor thread for %s' %(self.site))
      try:
        result = self.__pollSite()
        if not result['OK']:
          self.log.warn(result['Message'])
      except Exception,x:
        self.log.warn('Site thread failed with exception, will restart...')
        self.log.warn(str(x))

      time.sleep(self.pollingTime)

  #############################################################################
  def __pollSite(self):
    """ This method starts the monitoring loop for a given site thread.
    """
    self.log.verbose('Checking for tasks that are completed at %s' %(self.site))
    result = self.__updateCompletedTasks()
    self.log.verbose('Monitoring files for status "New" at %s' %(self.site))
    result = self.__monitorStageRequests('New')
    self.log.verbose('Checking for tasks that are completed at %s' %(self.site))
    result = self.__updateCompletedTasks()
    self.log.verbose('Monitoring files for status "Submitted" at %s' %(self.site))
    result = self.__monitorStageRequests('Submitted')
    self.log.verbose('Checking for tasks that are completed at %s' %(self.site))
    result = self.__updateCompletedTasks()
    self.log.verbose('Checking for tasks to retry at %s' %(self.site))
    result = self.__getTasksForRetry()
    return S_OK('Monitoring loop completed')

  #############################################################################
  def __monitorStageRequests(self,status):
    """ This method instantiates the StorageElement class and prestages the SURLs.
    """
    result = self.stagerClient.getFilesForState(self.site,status,limit=self.fileSelectLimit)
    if not result['OK']:
      return result

    replicas = result['Files']
    siteSEs = getSEsForSite(self.site)
    if not siteSEs['OK']:
      return S_ERROR('Could not determine SEs for site %s' %self.site)
    siteSEs = siteSEs['Value']

    seFilesDict = {}
    pfnLfnDict = {}
    for localSE in siteSEs:
      for lfn,reps in replicas.items():
        if reps.has_key(localSE):
          pfn = reps[localSE]
          if seFilesDict.has_key(localSE):
            currentFiles = seFilesDict[localSE]
            currentFiles.append(pfn)
            seFilesDict[localSE] = currentFiles
            pfnLfnDict[pfn]=lfn
          else:
            seFilesDict[localSE] = [pfn]
            pfnLfnDict[pfn]=lfn

    self.log.verbose('Files grouped by LocalSE for state "%s" are: \n%s' %(status,seFilesDict))
    if seFilesDict:
      result = self.__getStagedFiles(seFilesDict,pfnLfnDict)
      if not result['OK']:
        self.log.warn('Problem while getting file metadata:\n%s' %(result))

    return S_OK('Monitoring updated')

  #############################################################################
  def __getStagedFiles(self,seFilesDict,pfnLfnDict):
    """ Checks whether files are cached.
    """
    staged = []
    failed = []
    unstaged = []
    totalFiles = len(pfnLfnDict.keys())
    for se,pfnList in seFilesDict.items():
      storageElement = StorageElement(se)
      res = storageElement.isValid()
      if not res['OK']:
        return S_ERROR('%s SiteMonitor Failed to instantiate StorageElement for: %s' %(self.site,se))

      start = time.time()
      metadataRequest = storageElement.getFileMetadata(pfnList)
      timing = time.time()-start
      self.log.verbose(metadataRequest)
      self.log.info('Metadata request for %s files took %.1f secs' %(len(pfnList),timing))

      if not metadataRequest['OK']:
        self.log.warn('Metadata request failed for %s %s' %(self.site,se))
        return metadataRequest
      else:
        metadataRequest = metadataRequest['Value']

      self.log.verbose('Setting timing information for gfal.prestage at site %s for %s files' %(self.site,len(pfnList)))
      result = self.stagerClient.setTiming(self.site,'gfal.prestage',float(timing),len(pfnList))
      if not result['OK']:
        self.log.warn('Failed to enter timing information for site %s with error:\n%s' %(self.site,result))

      if metadataRequest.has_key('Failed'):
        for pfn,cause in metadataRequest['Failed'].items():
          self.log.warn('Metadata request for PFN %s failed with message: %s' %(pfn,cause))
          failed.append(pfnLfnDict[pfn])

      if metadataRequest.has_key('Successful'):
        for pfn,metadata in metadataRequest['Successful'].items():
          self.log.debug('Metadata call successful for PFN %s SE %s' %(pfn,se))
          if metadata.has_key('Cached'):
            if metadata['Cached']:
              staged.append(pfnLfnDict[pfn])
              self.log.verbose('PFN %s is staged' %(pfn))
            else:
              self.log.verbose('PFN %s is not yet staged' %(pfn))
              unstaged.append(pfnLfnDict[pfn])
          else:
            self.log.warn('Unexpected metadata result for PFN %s' %(pfn))
            self.log.warn(metadata)

    if staged:
      ##########################################
      # First get the start time information for the files that have prestage requests issued
      res = self.stagerClient.getStageSubmissionTiming(staged,self.site)
      if not res['OK']:
        self.log.warn('Accounting information will not be sent for %s files' % len(staged))
      else:
        submissionTiming = res['Value']
        ######################################
        # Update the file statuses so they are not monitored again by this agent
        result = self.stagerClient.setFilesState(staged,self.site,'ToUpdate')
        if not result['OK']:
          self.log.warn(result)
        else:
          #########################################
          # If they were successfully updated then send the accounting information
          res = self.fc.getFileSize(submissionTiming.keys())
          if not res['OK']:
            self.log.warn('Failed to get file sizes. Will assume file is of size 1 byte for all files.')
            fileSizes = {}
          else:
            fileSizes = res['Value']['Successful']

          for lfn in staged:
            submitTime = submissionTiming[lfn]
            oDataOperation = self.__initialiseAccountingObject(submitTime)
            if fileSizes.has_key(lfn):
              fileSize = fileSizes[lfn]
              oDataOperation.setValueByKey('TransferSize',fileSize)
            startTime = submitTime.utcnow()
            endTime = Time.dateTime()
            c = endTime-startTime
            stageTime = c.days * 86400 + c.seconds
            oDataOperation.setValueByKey('TransferTime',stageTime)
            gDataStoreClient.addRegister(oDataOperation)
          self.log.info('Attempting to send accounting message...')
          gDataStoreClient.commit()
          self.log.info('...sent.')

    self.log.info('Metadata query found: Staged=%s, UnStaged=%s, Failed=%s, out of Total=%s files' %(len(staged),len(unstaged),len(failed),totalFiles))
    return S_OK(staged)

  #############################################################################
  def __updateCompletedTasks(self):
    """ Checks for completed tasks and triggers the update of their status.
    """
    result = self.stagerClient.getJobsForState(self.site,'Staged',limit=self.taskSelectLimit)
    if not result['OK']:
      return result

    lfns = []
    jobIDs = result['JobIDs']
    result = self.stagerClient.getLFNsForJobs(jobIDs)
    if not result['OK']:
      self.log.warn('Problem getting LFNs with error:\n%s' % result['Message'])
    else:
      for jobID in jobIDs:
        for lfn in result[jobID]:
          lfns.append(lfn)

    if lfns:
      self.log.info('Updating %s LFNs to successful status' %(len(lfns)))
      result = self.stagerClient.setFilesState(lfns,self.site,'Successful')
      if not result['OK']:
        self.log.warn('Problem updating successful task:\n%s' %(result))
    else:
      self.log.verbose('No successfully staged tasks to update')

    return S_OK('Completed tasks updated')

  #############################################################################
  def __getTasksForRetry(self):
    """ Checks for failed tasks and triggers the update of their status.
    """
    result = self.stagerClient.getJobsForRetry(self.stageRetryMax,self.site)
    if not result['OK']:
      return result
    for jobID,lfns in result['JobIDs'].items():
      self.log.info('Updating %s LFNs to failed status for job %s' %(len(lfns),jobID))
      result = self.stagerClient.setFilesState(lfns,self.site,'Failed')
      if not result['OK']:
        self.log.warn('Problem updating failed task with ID %s:\n%s' %(jobID,result))

    return S_OK('Failed tasks updated')

  #############################################################################
  def __initialiseAccountingObject(self,submitTime):
    accountingDict = {}
    accountingDict['OperationType'] = 'Prestage'
    accountingDict['User'] = 'acsmith'
    accountingDict['Protocol'] = 'SRM'
    accountingDict['RegistrationTime'] = 0.0
    accountingDict['RegistrationOK'] = 0
    accountingDict['RegistrationTotal'] = 0
    accountingDict['TransferTotal'] = 1
    accountingDict['TransferSize'] = 1
    accountingDict['TransferOK'] = 1
    accountingDict['TransferTime'] = 0.0
    accountingDict['FinalStatus'] = 'Successful'
    accountingDict['Source'] = gConfig.getValue('/LocalSite/Site','Unknown')
    accountingDict['Destination'] = self.site
    oDataOperation = DataOperation()
    oDataOperation.setEndTime()
    oDataOperation.setStartTime(submitTime)
    oDataOperation.setValuesFromDict(accountingDict)
    return oDataOperation
