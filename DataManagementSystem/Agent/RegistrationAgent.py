########################################################################
# $HeadURL$
########################################################################

"""  RegistrationAgent takes register requests from the RequestDB and registers them
"""

from DIRAC  import gLogger, gConfig, gMonitor, S_OK, S_ERROR, rootPath
from DIRAC.Core.Base.AgentModule import AgentModule
from DIRAC.Core.Utilities.Pfn import pfnparse, pfnunparse
from DIRAC.Core.DISET.RPCClient import RPCClient
from DIRAC.Core.Utilities.Shifter import setupShifterProxyInEnv
from DIRAC.Core.Utilities.ThreadPool import ThreadPool,ThreadedJob
from DIRAC.RequestManagementSystem.Client.RequestClient import RequestClient
from DIRAC.RequestManagementSystem.Client.RequestContainer import RequestContainer
from DIRAC.DataManagementSystem.Client.ReplicaManager import ReplicaManager
from DIRAC.DataManagementSystem.Client.DataLoggingClient import DataLoggingClient
from DIRAC.Core.DISET.RPCClient import RPCClient
from DIRAC.RequestManagementSystem.Agent.RequestAgentMixIn import RequestAgentMixIn

import time,os
from types import *

__RCSID__ = "$Id$"

AGENT_NAME = 'DataManagement/RegistrationAgent'

class RegistrationAgent(AgentModule,RequestAgentMixIn):

  def __init__(self):
    """ Standard constructor
    """
    Agent.__init__(self,AGENT_NAME)

  def initialize(self):
    result = Agent.initialize(self)
    self.RequestDBClient = RequestClient()
    self.ReplicaManager = ReplicaManager()
    self.DataLog = DataLoggingClient()

    self.maxNumberOfThreads = gConfig.getValue(self.section+'/NumberOfThreads',1)
    self.threadPoolDepth = gConfig.getValue(self.section+'/ThreadPoolDepth',1)
    self.threadPool = ThreadPool(1,self.maxNumberOfThreads)

    self.useProxies = self.am_getOption('UseProxies','True').lower() in ( "y", "yes", "true" )
    self.proxyLocation = self.am_getOption('ProxyLocation', '' )
    if not self.proxyLocation:
      self.proxyLocation = False

    if self.useProxies:
      self.am_setModuleParam('shifter','DataManager')
      self.am_setModuleParam('shifterProxyLocation',self.proxyLocation)

    return S_OK()

  def execute(self):

    for i in range(self.threadPoolDepth):
      requestExecutor = ThreadedJob(self.executeRequest)
      self.threadPool.queueJob(requestExecutor)
    self.threadPool.processResults()
    return self.executeRequest()

  def executeRequest(self):
    ################################################
    # Get a request from request DB
    res = self.RequestDBClient.getRequest('register')
    if not res['OK']:
      gLogger.info("RegistrationAgent.execute: Failed to get request from database.")
      return S_OK()
    elif not res['Value']:
      gLogger.info("RegistrationAgent.execute: No requests to be executed found.")
      return S_OK()
    requestString = res['Value']['RequestString']
    requestName = res['Value']['RequestName']
    sourceServer = res['Value']['Server']
    try:
      jobID = int(res['Value']['JobID'])
    except:
      jobID = 0
    gLogger.info("RegistrationAgent.execute: Obtained request %s" % requestName)

    result = self.RequestDBClient.getCurrentExecutionOrder(requestName,sourceServer)
    if result['OK']:
      currentOrder = result['Value']
    else:
      return S_OK('Can not get the request execution order')

    oRequest = RequestContainer(request=requestString)

    ################################################
    # Find the number of sub-requests from the request
    res = oRequest.getNumSubRequests('register')
    if not res['OK']:
      errStr = "RegistrationAgent.execute: Failed to obtain number of transfer subrequests."
      gLogger.error(errStr,res['Message'])
      return S_OK()
    gLogger.info("RegistrationAgent.execute: Found %s sub requests." % res['Value'])

    ################################################
    # For all the sub-requests in the request
    modified = False
    for ind in range(res['Value']):
      gLogger.info("RegistrationAgent.execute: Processing sub-request %s." % ind)
      subRequestAttributes = oRequest.getSubRequestAttributes(ind,'register')['Value']
      subExecutionOrder = int(subRequestAttributes['ExecutionOrder'])
      subStatus = subRequestAttributes['Status']
      if subStatus == 'Waiting' and subExecutionOrder <= currentOrder:
        subRequestFiles = oRequest.getSubRequestFiles(ind,'register')['Value']
        operation = subRequestAttributes['Operation']

        ################################################
        #  If the sub-request is a register file operation
        if operation == 'registerFile':
          gLogger.info("RegistrationAgent.execute: Attempting to execute %s sub-request." % operation)
          diracSE = str(subRequestAttributes['TargetSE'])
          if diracSE == 'SE':
            # We do not care about SE, put any there
            diracSE = "CERN-FAILOVER" 
          catalog = subRequestAttributes['Catalogue']
          if catalog == "None":
            catalog = ''
          subrequest_done = True
          for subRequestFile in subRequestFiles:
            if subRequestFile['Status'] == 'Waiting':
              lfn = str(subRequestFile['LFN'])
              physicalFile = str(subRequestFile['PFN'])
              fileSize = int(subRequestFile['Size'])
              fileGuid = str(subRequestFile['GUID'])
              checksum = str(subRequestFile['Addler'])
              fileTuple = (lfn,physicalFile,fileSize,diracSE,fileGuid,checksum)
              res = self.ReplicaManager.registerFile(fileTuple,catalog)
              print res
              if not res['OK']:
                self.DataLog.addFileRecord(lfn,'RegisterFail',diracSE,'','RegistrationAgent')
                errStr = "RegistrationAgent.execute: Completely failed to register file."
                gLogger.error(errStr, res['Message'])
                subrequest_done = False
              elif lfn in res['Value']['Failed'].keys():
                self.DataLog.addFileRecord(lfn,'RegisterFail',diracSE,'','RegistrationAgent')
                errStr = "RegistrationAgent.execute: Completely failed to register file."
                gLogger.error(errStr, res['Value']['Failed'][lfn])
                subrequest_done = False
              else:
                self.DataLog.addFileRecord(lfn,'Register',diracSE,'','TransferAgent')
                oRequest.setSubRequestFileAttributeValue(ind,'transfer',lfn,'Status','Done')
                modified = True
            else:
              gLogger.info("RegistrationAgent.execute: File already completed.")
          if subrequest_done:
            oRequest.setSubRequestStatus(ind,'register','Done')

        ################################################
        #  If the sub-request is none of the above types
        else:
          gLogger.error("RegistrationAgent.execute: Operation not supported.", operation)

        ################################################
        #  Determine whether there are any active files
        if oRequest.isSubRequestEmpty(ind,'register')['Value']:
          oRequest.setSubRequestStatus(ind,'register','Done')

      ################################################
      #  If the sub-request is already in terminal state
      else:
        gLogger.info("RegistrationAgent.execute: Sub-request %s is status '%s' and  not to be executed." % (ind,subRequestAttributes['Status']))

    ################################################
    #  Generate the new request string after operation
    requestString = oRequest.toXML()['Value']
    res = self.RequestDBClient.updateRequest(requestName,requestString,sourceServer)

    if modified and jobID:
      result = self.finalizeRequest(requestName,jobID,sourceServer)

    return S_OK()
