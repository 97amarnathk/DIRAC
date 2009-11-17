########################################################################
# $Id$
########################################################################
""" DIRAC Transformation DB

    Transformation database is used to collect and serve the necessary information
    in order to automate the task of job preparation for high level transformations.
    This class is typically used as a base class for more specific data processing
    databases
"""

__RCSID__ = "$Id$"

import re,time,types,string

from DIRAC                                                             import gConfig, gLogger, S_OK, S_ERROR
from DIRAC.Core.Base.DB                                                import DB
from DIRAC.DataManagementSystem.Client.ReplicaManager                  import ReplicaManager
from DIRAC.Core.Utilities.List                                         import stringListToString, intListToString
from DIRAC.Core.DISET.RPCClient                                        import RPCClient

import threading
from types import *

MAX_ERROR_COUNT = 3

#############################################################################

class TransformationDB(DB):

  def __init__(self, dbname, dbconfig, maxQueueSize=10 ):
    """ The standard constructor takes the database name (dbname) and the name of the
        configuration section (dbconfig)
    """
    DB.__init__(self,dbname, dbconfig, maxQueueSize)
    self.lock = threading.Lock()
    self.dbname = dbname
    self.filters = self.__getFilters()
    self.rm = None

  def getTransformationWithStatus(self, status):
    """ Gets a list of the transformations with the supplied status
    """
    req = "SELECT TransformationID FROM Transformations WHERE Status = '%s';" % status
    res = self._query(req)
    if not res['OK']:
      return res
    transIDs = []  
    for tuple in res['Value']:
      transIDs.append(tuple[0])
    return S_OK(transIDs)

  def getTransformationID(self, name):
    """ Method returns ID of transformation with the name=<name>
        it checks type of the argument, and if it is string returns transformationID
        if not we assume that prodName is actually prodID

        Returns transformation ID if exists otherwise 0
        WARNING!! returned value is long !!
    """

    if isinstance(name, str):
      cmd = "SELECT TransformationID from Transformations WHERE TransformationName='%s';" % name
      result = self._query(cmd)
      if not result['OK']:
        gLogger.error("Failed to check if Transformation with name %s exists %s" % (name, result['Message']))
        return 0L # we do not terminate execution here but log error
      elif result['Value'] == ():
        gLogger.verbose("Transformation with name %s do not exists" % (name))
        return 0L # we do not terminate execution here
      return result['Value'][0][0]
    return name # it is actually number

  def transformationExists(self, transID):
    """ Method returns TRUE if transformation with the ID=<id> exists
    """
    cmd = "SELECT COUNT(*) from Transformations WHERE TransformationID='%s';" % transID
    result = self._query(cmd)
    if not result['OK']:
      gLogger.error("Failed to check if Transformation with ID %d exists %s" % (transID, result['Message']))
      return False
    elif result['Value'][0][0] > 0:
        return True
    return False

####################################################################################
#
#  This part contains the transformation manipulation methods
#
####################################################################################

  def getName(self):
    """  Get the database name
    """
    return self.dbname

  def addTransformation(self, name, description, longDescription, authorDN,
                        authorGroup, type_, plugin, agentType,fileMask,bkQuery={},
                        transformationGroup='',addFiles=True):
    """ Add new transformation definition including its input streams
    """

    # Add the Bookkeeping query if given
    bkQueryID = 0
    if bkQuery:
      result = self.addBookkeepingQuery(bkQuery)
      if not result['OK']:
        return result
      bkQueryID = result['Value']

    tGroup = 'General'
    if transformationGroup:
      tGroup =  transformationGroup

    self.lock.acquire()
    req = "INSERT INTO Transformations (TransformationName,Description,LongDescription,"
    req += "CreationDate,AuthorDN,AuthorGroup,Type,Plugin,AgentType,FileMask,Status,BkQueryID,TransformationGroup) "
    req += "VALUES ('%s','%s','%s',UTC_TIMESTAMP(),'%s','%s','%s','%s','%s','%s','New',%d,'%s');" % \
                             (name, description, longDescription,authorDN, authorGroup, type_,
                              plugin, agentType,fileMask,bkQueryID,tGroup)
    result = self._getConnection()
    if result['OK']:
      connection = result['Value']
    else:
      return S_ERROR('Failed to get connection to MySQL: '+result['Message'])
    res = self._update(req,connection)
    if not res['OK']:
      self.lock.release()
      return res
    req = "SELECT LAST_INSERT_ID();"
    res = self._query(req,connection)
    self.lock.release()
    if not res['OK']:
      return res
    transID = int(res['Value'][0][0])

    # For the PROCESSING type transformation add data processing table
    if fileMask or bkQuery:
      if fileMask:
        self.filters.append((transID,re.compile(fileMask)))
        # Add already existing files to this transformation if any
        if addFiles:
          result = self.__addExistingFiles(transID)
      result = self.__addTransformationTable(transID)

    return S_OK(transID)

  def modifyTransformation(self, transID, name, description, longDescription, authorDN, authorGroup, type_, plugin, agentType,fileMask):
    # Warnung method updateTransformation already exists and its updating files
    """ Updates transformation record
    """
    req = "UPDATE Transformations SET TransformationName='%s',Description='%s',LongDescription='%s',\
    AuthorDN='%s',AuthorGroup='%s',Type='%s',Plugin='%s',AgentType='%s',FileMask='%s',Status='%s' WHERE TransformationID=%d;"%\
    (name, description, longDescription, authorDN, authorGroup, type_, plugin, agentType, fileMask, transID)
    res = self._update(req)
    if not res['OK']:
      return res
    self.filters.append((transID,re.compile(fileMask)))
    result = self.__addTransformationTable(transID)
    # Add already existing files to this transformation if any
    result = self.__addExistingFiles(transID)
    return S_OK(transID)

  def updateTransformationLogging(self,transName,message,authorDN):
    """ Update the Transformation log table with any modifications (we know who you are!!)
    """
    transID = self.getTransformationID(transName)
    req = "INSERT INTO TransformationLog (TransformationID,Message,Author,MessageDate) \
    VALUES (%s,'%s','%s',UTC_TIMESTAMP());" % (transID,message,authorDN)
    res = self._update(req)
    return res

  def getTransformationLogging(self,transName):
    """ Get Transformation log table
        Works with TransformationID only
    """
    transID = self.getTransformationID(transName)
    req = "SELECT TransformationID, Message, Author, MessageDate FROM TransformationLog WHERE TransformationID=%s ORDER BY MessageDate;" % (transID)
    res = self._query(req)
    if not res['OK']:
      return res

    translist = []
    for transID, message, authorDN, messageDate in res['Value']:
      transdict = {}
      transdict['TransID'] = transID
      transdict['Message'] = message
      transdict['AuthorDN'] = authorDN
      transdict['MessageDate'] = messageDate
      translist.append(transdict)

    return S_OK(translist)

  def setTransformationStatus(self,transName,status):
    """ Set the status of the transformation specified by transID
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET Status='%s' WHERE TransformationID=%s;" % (status,transID)
    res = self._update(req)
    return res

  def addTransformationParameter(self,transName,paramName,paramValue):
    """ Add a parameter for the supplied transformations
    """

    transID = self.getTransformationID(transName)
    req = "SELECT TransformationID,ParameterName,ParameterValue FROM TransformationParameters"
    req += " WHERE TransformationID=%d AND ParameterName='%s'" % (transID,paramName)
    result = self._query(req)
    if not result['OK']:
      return result

    # If parameter name exists, remove it
    if result['Value']:
      req = "DELETE FROM TransformationParameters"
      req += " WHERE TransformationID=%d AND ParameterName='%s'" % (transID,paramName)
      result = self._update(req)
      if not result['OK']:
        return result

    req = "INSERT INTO TransformationParameters (TransformationID,ParameterName,ParameterValue) VALUES (%s,'%s','%s');" % (transID,paramName,paramValue)
    res = self._update(req)
    return res

  def setTransformationAgentType(self,transName,status):
    """ Set the submission status of the transformation specified by transID
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET AgentType='%s' WHERE TransformationID=%s;" % (status,transID)
    res = self._update(req)
    return res

  def setTransformationQuery(self,transName,queryID):
    """ Set the bookkeeping query ID of the transformation specified by transID
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET FileMask='', BkQueryID=%d WHERE TransformationID=%s;" % (int(queryID),transID)
    res = self._update(req)
    return res

  def setTransformationPlugin(self,transName,status):
    """ Set the Plugin the transformation specified by transID
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET Plugin='%s' WHERE TransformationID=%s;" % (status,transID)
    res = self._update(req)
    return res

  def setTransformationType(self,transName,status):
    """ Set the Plugin the transformation specified by transID
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET Type='%s' WHERE TransformationID=%s;" % (status,transID)
    res = self._update(req)
    return res

  def getTransformationStats(self,transName):
    """ Get number of files in Transformation Table for each status
    """

    transID = self.getTransformationID(transName)
    resultStats = self.getCounters('T_%s' % transID,['Status'],{})
    if not resultStats['OK']:
      return resultStats
    if not resultStats['Value']:
      return S_ERROR('No records found')

    statusList = {}
    total=0
    for attrDict,count in resultStats["Value"]:
      status = attrDict['Status']
      statusList[status]=count
      total += count
    statusList['Total']=total
    return S_OK(statusList)

  def getTransformation(self,transName):
    """Get Transformation definition
       Get the parameters of Transformation idendified by TransformationID
    """
    transID = self.getTransformationID(transName)
    if transID > 0:
      req = "SELECT TransformationID,TransformationName,Description,LongDescription,CreationDate,\
             AuthorDN,AuthorGroup,Type,Plugin,AgentType,Status,FileMask,BkQueryID,TransformationGroup FROM Transformations WHERE TransformationID=%d;"%transID
      res = self._query(req)
      if not res['OK']:
        return res
      if not res['Value']:
        return S_ERROR('Transformation %s not found' %str(transName))
      tr=res['Value'][0]
      transdict = {}
      transdict['TransID'] = tr[0]
      transdict['Name'] = tr[1]
      transdict['Description'] = tr[2]
      transdict['LongDescription'] = tr[3]
      transdict['CreationDate'] = tr[4]
      transdict['AuthorDN'] = tr[5]
      transdict['AuthorGroup'] = tr[6]
      transdict['Type'] = tr[7]
      transdict['Plugin'] = tr[8]
      transdict['AgentType'] = tr[9]
      transdict['Status'] = tr[10]
      transdict['FileMask'] = tr[11]
      transdict['BkQueryID'] = tr[12]
      transdict['TransformationGroup'] = tr[13]
      req = "SELECT ParameterName,ParameterValue FROM TransformationParameters WHERE TransformationID = %s;" % transID
      res = self._query(req)
      if res['OK']:
        if res['Value']:
          transdict['Additional'] = {}
          for parameterName,parameterValue in res['Value']:
            transdict['Additional'][parameterName] = parameterValue
      return S_OK(transdict)
    return S_ERROR('Transformation with id =%d not found'%transID)

  def getTransformations(self,transList):
    """ Get Transformation attributes for Transformations identified by transformation ID in the given list
    """

    transString = ','.join([str(x) for x in transList])
    paramList = ['TransformationID','TransformationName','Description','LongDescription',
                 'CreationDate','AuthorDN','AuthorGroup','Type','Plugin','AgentType','Status',
                 'FileMask','BkQueryID','TransformationGroup']
    paramString = ','.join(paramList)

    req = "SELECT %s FROM Transformations WHERE TransformationID in (%s);" % (paramString,transString)
    res = self._query(req)
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR('No Transformation found')

    resultDict = {}
    resultDict['ParameterNames'] = paramList
    resultList = []
    for raw in res['Value']:
      rList = []
      for item in raw:
        if type(item) not in [IntType,LongType]:
          rList.append(str(item))
        else:
          rList.append(item)
      resultList.append(rList)

    resultDict['Records'] = resultList

    return S_OK(resultDict)

  def getAllTransformations(self):
    """ Get parameters of all the Transformations
    """
    translist = []
    req = "SELECT TransformationID,TransformationName,Description,LongDescription,CreationDate,\
    AuthorDN,AuthorGroup,Type,Plugin,AgentType,Status,FileMask,BkQueryID,TransformationGroup \
    FROM Transformations;"
    res = self._query(req)
    if not res['OK']:
      return res
    for row in res['Value']:
      transdict = {}
      transdict['TransID'] = row[0]
      transID = row[0]
      transdict['Name'] = row[1]
      transdict['Description'] = row[2]
      transdict['LongDescription'] = row[3]
      transdict['CreationDate'] = row[4]
      transdict['AuthorDN'] = row[5]
      transdict['AuthorGroup'] = row[6]
      transdict['Type'] = row[7]
      transdict['Plugin'] = row[8]
      transdict['AgentType'] = row[9]
      transdict['Status'] = row[10]
      transdict['FileMask'] = row[11]
      transdict['BkQueryID'] = row[12]
      transdict['TransformationGroup'] = row[13]
      req = "SELECT ParameterName,ParameterValue FROM TransformationParameters WHERE TransformationID = %s;" % transID
      res = self._query(req)
      if res['OK']:
        if res['Value']:
          transdict['Additional'] = {}
          for parameterName,parameterValue in res['Value']:
            transdict['Additional'][parameterName] = parameterValue
      translist.append(transdict)
      gLogger.debug('Transformation dictionary',transdict)
    return S_OK(translist)

  def setTransformationMask(self,transName,fileMask):
    """ Modify the input stream definition for the given transformation identified by transformation
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET FileMask='%s' WHERE TransformationID=%s" % (fileMask,transID)
    res = self._update(req)
    if res['OK']: # we must update transformation
      res = self.__addExistingFiles(transID)
    return res

  def changeTransformationName(self,transName,newName):
    """ Change the transformation name
    """
    transID = self.getTransformationID(transName)
    req = "UPDATE Transformations SET TransformationName='%s' WHERE TransformationID=%s;" % (newName,transID)
    res = self._update(req)
    return res

  def getTransformationLFNStatus(self,transName,lfnList):
    """ Get dictionary of supplied LFNs with status for a given transformation.
    """
    transID = self.getTransformationID(transName)
    if not type(lfnList)==types.ListType:
      lfnList = [lfnList]
    lfnList = string.join(lfnList,'","')
    req = 'select DataFiles.LFN,T_%s.Status from T_%s,DataFiles where T_%s.FileID=DataFiles.FileID and DataFiles.LFN in ("%s")' %(transName,transName,transName,lfnList)
    result = self._query(req)
    if not result['OK']:
      return result
    lfnStatusDict = {}
    for lfn,status in result['Value']:
      lfnStatusDict[lfn]=status
    return S_OK(lfnStatusDict)
  
  def getTransformationLFNsJobs(self,transName,fileStatus):
    """ Select files with given status for a transformation and return dictionary
        of LFNs and JobIDs. 
    """
    transID = self.getTransformationID(transName)
    req = 'select DataFiles.LFN,T_%s.JobID from T_%s,DataFiles where T_%s.FileID=DataFiles.FileID and T_%s.Status in ("%s")' %(transName,transName,transName,transName,fileStatus)
    result = self._query(req)
    if not result['OK']:
      return result
    jobLFNDict = {}
    for lfn,job in result['Value']:
      if not job: job=0
      jobLFNDict[lfn]=job
      
    return S_OK(jobLFNDict)
      
  def getTransformationLFNs(self,transName,status='Unused'):
    """  Get input LFNs for the given transformation, only files
        with a given status which is defined for the file replicas.
    """
    transID = self.getTransformationID(transName)
    if not status:
      req = "SELECT D.LFN from T_%s as T LEFT JOIN DataFiles as D ON (T.FileID=D.FileID);" % (transID)
    else:
      req = "SELECT D.LFN FROM DataFiles AS D,T_%s AS T WHERE T.FileID=D.FileID and T.Status='%s';" % (transID,status)
    res = self._query(req)
    if not res['OK']:
      return res
    lfns = []
    for tuple in res['Value']:
      lfns.append(tuple[0]) 
    return S_OK(lfns)

  def getInputData(self,transName,status):
    """ Get input data for the given transformation, only files
        with a given status which is defined for the file replicas.
    """

    #print 'TransformationDB 1:',transName,status

    transID = self.getTransformationID(transName)
    req = "SELECT FileID from T_%s WHERE Status='Unused';" % (transID)
    res = self._query(req)

    if not res['OK']:
      if res['Message'].find('Table') != -1 and res['Message'].find("doesn't exist") != -1:
        return S_OK([])
      return res
    if not res['Value']:
      return S_OK([])
    ids = [ str(x[0]) for x in res['Value'] ]
    if not ids:
      return S_OK([])

    if status:
      req = "SELECT LFN,SE FROM Replicas,DataFiles WHERE Replicas.Status = '%s' AND \
      Replicas.FileID=DataFiles.FileID AND Replicas.FileID in (%s);" % (status,intListToString(ids))
    else:
      req = "SELECT LFN,SE FROM Replicas,DataFiles WHERE Replicas.Status = 'AprioriGood' AND \
      Replicas.FileID=DataFiles.FileID AND Replicas.FileID in (%s);" % intListToString(ids)
    res = self._query(req)
    if not res['OK']:
      return res
    replicaList = []
    for lfn,se in res['Value']:
      replicaList.append((lfn,se))
    return S_OK(replicaList)

  def getFilesForTransformation(self,transName,jobOrdered=False):
    """ Get files and their status for the given transformation
    """
    transID = self.getTransformationID(transName)
    req = "SELECT d.LFN,t.Status,t.JobID,t.TargetSE FROM DataFiles AS d,T_%s AS t WHERE t.FileID=d.FileID" % transID
    if jobOrdered:
      req = "%s ORDER by t.JobID;" % req
    else:
      req = "%s ORDER by LFN;" % req
    res = self._query(req)
    if not res['OK']:
      return res
    flist = []
    for lfn,status,jobid,usedse in res['Value']:
      fdict = {}
      fdict['LFN'] = lfn
      fdict['Status'] = status
      if jobid is None: jobid = 'No JobID assigned'
      fdict['JobID'] = jobid
      fdict['TargetSE'] = usedse
      flist.append(fdict)
    return S_OK(flist)

  def selectTransformations(self, condDict, older=None, newer=None, timeStamp='CreationDate',
                        orderAttribute=None, limit=None ):
    """ Select jobs matching the following conditions:
        - condDict dictionary of required Key = Value pairs;
        - with the last update date older and/or newer than given dates;

        The result is ordered by JobID if requested, the result is limited to a given
        number of jobs if requested.
    """

    condition = self.buildCondition(condDict, older, newer, timeStamp)

    if orderAttribute:
      orderType = None
      orderField = orderAttribute
      if orderAttribute.find(':') != -1:
        orderType = orderAttribute.split(':')[1].upper()
        orderField = orderAttribute.split(':')[0]
      condition = condition + ' ORDER BY ' + orderField
      if orderType:
        condition = condition + ' ' + orderType

    if limit:
      condition = condition + ' LIMIT ' + str(limit)

    cmd = 'SELECT TransformationID from Transformations ' + condition
    res = self._query( cmd )
    if not res['OK']:
      return res

    if not len(res['Value']):
      return S_OK([])
    return S_OK( map( self._to_value, res['Value'] ) )

  def getFileSummary(self,lfns,transName=''):
    """ Get file status summary in all the transformations
    """
    if transName:
      result = self.getTransformation(transName)
      if not result['OK']:
        return result
      transList = [result['Value']]
    else:
      result = self.getAllTransformations()
      if not result['OK']:
        return S_ERROR('Can not get transformations')
      transList = result['Value']

    resultDict = {}
    fileIDs = self.__getFileIDsForLfns(lfns)
    if not fileIDs:
      return S_ERROR('Files not found in the Transformation Database')

    failedDict = {}
    for lfn in lfns:
      if lfn not in fileIDs.values():
        failedDict[lfn] = True

    fileIDString = ','.join([ str(x) for x in fileIDs.keys() ])

    for transDict in transList:
      transID = transDict['TransID']
      transStatus = transDict['Status']

      req = "SELECT FileID,Status,TargetSE,UsedSE,JobID,ErrorCount,LastUpdate FROM T_%s \
             WHERE FileID in ( %s ) " % (transID,fileIDString)
      result = self._query(req)
      if not result['OK']:
        continue
      if not result['Value']:
        continue

      fileJobIDs = []

      for fileID,status,se,usedSE,jobID,errorCount,lastUpdate in result['Value']:
        lfn = fileIDs[fileID]
        if not resultDict.has_key(fileIDs[fileID]):
          resultDict[lfn] = {}
        if not resultDict[lfn].has_key(transID):
          resultDict[lfn][transID] = {}
        resultDict[lfn][transID]['FileStatus'] = status
        resultDict[lfn][transID]['TargetSE'] = se
        resultDict[lfn][transID]['UsedSE'] = usedSE
        resultDict[lfn][transID]['TransformationStatus'] = transStatus
        if jobID:
          resultDict[lfn][transID]['JobID'] = jobID
          fileJobIDs.append(jobID)
        else:
          resultDict[lfn][transID]['JobID'] = 'No JobID assigned'
        resultDict[lfn][transID]['JobStatus'] = 'Unknown'
        resultDict[lfn][transID]['FileID'] = fileID
        resultDict[lfn][transID]['ErrorCount'] = errorCount
        resultDict[lfn][transID]['LastUpdate'] = str(lastUpdate)

      if fileJobIDs:
        fileJobIDString = ','.join([ str(x) for x in fileJobIDs ])
        req = "SELECT T.FileID,J.WmsStatus from Jobs_%s as J, T_%s as T WHERE J.JobID in ( %s ) AND J.JobID=T.JobID" % (transID,transID,fileJobIDString)
        result = self._query(req)
        if not result['OK']:
          continue
        if not result['Value']:
          continue
        for fileID,jobStatus in result['Value']:
          # If the file was not requested then just ignore it
          if fileID in fileIDs.keys():
            lfn = fileIDs[fileID]
            resultDict[lfn][transID]['JobStatus'] = jobStatus

    return S_OK({'Successful':resultDict,'Failed':failedDict})

  def setFileSEForTransformation(self,transName,se,lfns):
    """ Set file SE for the given transformation identified by transID
        for files in the list of lfns
    """
    transID = self.getTransformationID(transName)
    fileIDs = self.__getFileIDsForLfns(lfns).keys()
    if not fileIDs:
      return S_ERROR('TransformationDB.setFileSEForTransformation: No files found.')
    else:
      req = "UPDATE T_%s SET UsedSE='%s' WHERE FileID IN (%s);" % (transID,se,intListToString(fileIDs))
      return self._update(req)

  def setFileTargetSEForTransformation(self,transName,se,lfns):
    """ Set file Target SE for the given transformation identified by transID
        for files in the list of lfns
    """
    transID = self.getTransformationID(transName)
    fileIDs = self.__getFileIDsForLfns(lfns).keys()
    if not fileIDs:
      return S_ERROR('TransformationDB.setFileSEForTransformation: No files found.')
    else:
      req = "UPDATE T_%s SET TargetSE='%s' WHERE FileID IN (%s);" % (transID,se,intListToString(fileIDs))
      return self._update(req)

  def setFileStatusForTransformation(self,transName,status,lfns):
    """ Set file status for the given transformation identified by transID
        for the given stream for files in the list of lfns
    """
    transID = self.getTransformationID(transName)
    result = self.getFileSummary(lfns,transID)

    if not result['OK']:
      return S_ERROR('Failed to contact the database')
    successful = {}
    failed = {}
    for lfn in result['Value']['Failed'].keys():
      failed[lfn] = 'File not found in the Transformation Database'
    lfnDict = result['Value']['Successful']
    fileIDs = []
    for lfn in lfnDict.keys():
      if lfnDict[lfn][transID]['FileStatus'] == "Processed" and status != "Processed":
        failed[lfn] = 'Can not change Processed status'
      elif lfnDict[lfn][transID]['ErrorCount'] >= MAX_ERROR_COUNT and status.lower() == 'unused':
        failed[lfn] = 'Max number of resets reached'
        req = "UPDATE T_%s SET Status='MaxReset', LastUpdate=UTC_TIMESTAMP() WHERE FileID=%s;" % (transID,lfnDict[lfn][transID]['FileID'])
        result = self._update(req)
      else:
        fileIDs.append((lfnDict[lfn][transID]['FileID'],lfn))

    for fileID,lfn in fileIDs:
      if status != lfnDict[lfn][transID]['FileStatus']:
        if status == "Unused":
          # Check that the status reset counter is not exceeding MAX_ERROR_COUNT
          newErrorCount = int(lfnDict[lfn][transID]['ErrorCount'])+1
          req = "UPDATE T_%s SET Status='%s', LastUpdate=UTC_TIMESTAMP(), " % (transID,status)
          req += "ErrorCount=%d WHERE FileID=%s;" % (newErrorCount,fileID)
        else:
          req = "UPDATE T_%s SET Status='%s', LastUpdate=UTC_TIMESTAMP() WHERE FileID=%s;" % (transID,status,fileID)
        result = self._update(req)
        if not result['OK']:
          failed[lfn] = result['Message']
        else:
          successful[lfn] = 'Status updated to %s' % status
      else:
        successful[lfn] = 'Status not changed'

    return S_OK({"Successful":successful,"Failed":failed})

  def resetFileStatusForTransformation(self,transName,lfns):
    """ Reset file error counter for the given transformation identified by transID
        and set status to Unused for files in the list of lfns
    """
    transID = self.getTransformationID(transName)
    fileIDs = self.__getFileIDsForLfns(lfns).keys()
    if not fileIDs:
      return S_ERROR('TransformationDB.resetFileStatusForTransformation: No files found.')
    else:
      req = "UPDATE T_%s SET Status='Unused', ErrorCount=0 WHERE FileID IN (%s);" % (transID,intListToString(fileIDs))
      return self._update(req)

  def setFileJobID(self,transName,jobID,lfns):
    """ Set file job ID for the given transformation identified by transID
        for the given stream for files in the list of lfns
    """
    transID = self.getTransformationID(transName)
    fileIDs = self.__getFileIDsForLfns(lfns).keys()
    if not fileIDs:
      return S_ERROR('TransformationDB.setFileJobID: No files found.')
    else:
      req = "UPDATE T_%s SET JobID='%s' WHERE FileID IN (%s);" % (transID,jobID,intListToString(fileIDs))
      return self._update(req)

  def deleteTransformation(self, transName):
    """ Remove the transformation specified by name or id
    """
    transID = self.getTransformationID(transName)
    if not self.transformationExists(transID) > 0:
      gLogger.warn("The transformation '%s' did not exist so could not delete" % transName)
      return S_OK()
    res = self._deleteTransformationFiles(transID)
    if not res['OK']:
      return res
    res = self._deleteTransformationParameters(transID)
    if not res['OK']:
      return res
    res = self._deleteTransformationLog(transID)
    if not res['OK']:
      return res
    res = self._deleteTransformation(transID)
    if not res['OK']:
      return res
    self.filters = self.__getFilters()
    return S_OK()

  def _deleteTransformationFiles(self, transID):
    """ Remove the files associated to a transformation
    """  
    req = "DROP TABLE IF EXISTS T_%d;" % transID
    return self._update(req)

  def _deleteTransformationParameters(self, transID):
    """ Remove the parameters associated to a transformation
    """
    req = "DELETE FROM TransformationParameters WHERE TransformationID=%s;" % transID
    return self._update(req)

  def _deleteTransformationLog(self,transID):
    """ Remove the entries in the transformation log for a transformation
    """
    req = "DELETE FROM TransformationLog WHERE TransformationID=%s;" % transID
    return self._update(req)

  def _deleteTransformation(self,transID):
    req = "DELETE FROM Transformations WHERE TransformationID=%s;" % transID
    return self._update(req)

  def getTransformationLastUpdate(self,transName):
    """ Get the last update from the TransformationLog table for the transformation """
    transID = self.getTransformationID(transName)
    req = "SELECT MessageDate FROM TransformationLog WHERE TransformationID=%d ORDER BY MessageDate DESC LIMIT 1;" % transID 
    res = self._query(req)
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR("Transformation not known")
    return S_OK(res['Value'][0][0])

####################################################################################
#
#  This part should correspond to the internal methods required for tranformation manipulation
#
####################################################################################

  def __addExistingFiles(self,transID=0):
    """ Add files that already exist in the DataFiles table to the
        transformation specified by the transID
    """

    dataLog = RPCClient('DataManagement/DataLogging', timeout=120 )
    # Add already existing files to this transformation if any
    filters = self.__getFilters(transID)

    if transID:
      for tid,filter in filters:
        if tid == transID:
          filters = [(tid,filter)]
          break

      if not filters:
        return S_ERROR('No filters defined for transformation %d' % transID)

    req = "SELECT LFN,FileID FROM DataFiles;"
    res = self._query(req)
    if not res['OK']:
      return res
    for lfn,fileID in res['Value']:
      resultFilter = self.__filterFile(lfn,filters)
      if resultFilter:
        res = self.__addFileToTransformation(fileID,resultFilter)
        if res['OK']:
          if res['Value']:
            for transID in res['Value']:
              ret = dataLog.addFileRecord(lfn,'AddedToTransformation','Transformation %s' % transID,'',self.dbname)
              if not ret['OK']:
                gLogger.warn('Unable to add dataLogging record for Transformation %s FileID %s' % (transID, fileID))
    return S_OK()

  def __addTransformationTable(self,transID):
    """ Add a new Transformation table for a given transformation
    """
    req = """CREATE TABLE T_%s(
FileID INTEGER NOT NULL,
Status VARCHAR(32) DEFAULT "Unused",
INDEX (Status),
ErrorCount INT(4) NOT NULL DEFAULT 0,
JobID VARCHAR(32),
TargetSE VARCHAR(32) DEFAULT "Unknown",
UsedSE VARCHAR(32) DEFAULT "Unknown",
LastUpdate DATETIME,
PRIMARY KEY (FileID)
)""" % str(transID)
    res = self._update(req)
    if not res['OK']:
      return S_ERROR("TransformationDB.__addTransformationTable: Failed to add new transformation table",res['Message'])
    return S_OK()

  def __getFilters(self,transID=None):
    """ Get filters for all defined input streams in all the transformations.
        If transID argument is given, get filters only for this transformation.
    """

    # Define the general filter first
    setup = gConfig.getValue('/DIRAC/Setup','')
    generalMask = gConfig.getValue('/Operations/InputDataFilter/%sFilter' % self.database_name,'')
    value = gConfig.getValue('/Operations/InputDataFilter/%s/%sFilter' % (setup,self.database_name),'')
    if value:
      generalMask = value
    resultList = []
    refilter = re.compile(generalMask)
    resultList.append((0,refilter))

    # Per transformation filters
    req = "SELECT TransformationID,FileMask FROM Transformations"
    result = self._query(req)
    if not result['OK']:
      return result
    for transID,mask in result['Value']:
      if mask:
        refilter = re.compile(mask)
        resultList.append((transID,refilter))

    return resultList

  def addLFNsToTransformation(self,lfnList,transName):
    """ Add a list of LFNs to the transformation specified by transname without filtering
    """

    if not lfnList:
      return S_ERROR('Zero length LFN list')

    transID = self.getTransformationID(transName)

    # get file IDs
    lfnString = ','.join(["'"+x+"'" for x in lfnList])
    req = "SELECT FileID,LFN FROM DataFiles WHERE LFN IN ( %s )" % lfnString
    result = self._query(req)
    if not result['OK']:
      return result

    fileIDs = [ (x[0],x[1]) for x in result['Value'] ]
    successful = {}
    failed = {}
    for fileID,lfn in fileIDs:
      result = self.__addFileToTransformation(fileID,[transID])
      if result['OK']:
        if result['Value']:
          successful[lfn] = "Added"
        else:
          successful[lfn] = "Present"
      else:
        failed[lfn] = result['Message']

    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def __addFileToTransformation(self,fileID,resultFilter):
    """Add file to transformations

       Add file to all the transformations which require this kind of files.
       resultFilter is a list of pairs transID,StreamName which needs this file
    """
    addedTransforms = []
    if resultFilter:
      for transID in resultFilter:
        if transID:
          req = "SELECT * FROM T_%s WHERE FileID=%s;" % (transID,fileID)
          res = self._query(req)
          if not res['OK']:
            return res
          if not res['Value']:
            req = "INSERT INTO T_%s (FileID,LastUpdate) VALUES ( %s,UTC_TIMESTAMP() );"  % (transID,fileID)
            res = self._update(req)
            if not res['OK']:
              return res
            else:
              gLogger.info("TransformationDB.__addFileToTransformation: File %s added to transformation %s." % (fileID,transID))
              addedTransforms.append(transID)
          else:
            gLogger.verbose("TransformationDB.__addFileToTransformation: File %s already present in transformation %s." % (fileID,transID))
    return S_OK(addedTransforms)

  def __getFileIDsForLfns(self,lfns):
    """ Get file IDs for the given list of lfns
    """
    fids = {}
    req = "SELECT LFN,FileID FROM DataFiles WHERE LFN in (%s);" % stringListToString(lfns)
    res = self._query(req)
    if not res['OK']:
      return res
    for lfn,fileID in res['Value']:
      fids[fileID] = lfn
    return fids

  def __filterFile(self,lfn,filters=None):
    """Pass the input file through a filter

       Apply input file filters of the currently active transformations to the
       given lfn and select appropriate transformations if any. If 'filters'
       argument is given, use this one instead of the global filter list.
       Filter list is composed of triplet tuples transID,StreamName,refilter
       where refilter is a compiled RE object to check the lfn against.
    """
    result = []
    # If the list of filters is given use it, otherwise use the complete list
    if filters:
      for transID,refilter in filters:
        if refilter.search(lfn):
          result.append(transID)
    else:
      for transID,refilter in self.filters:
        if refilter.search(lfn):
          result.append(transID)
    return result

####################################################################################
#
#  This part should correspond to the DIRAC Standard File Catalog interface
#
####################################################################################

  def addDirectory(self,path,force=False):
    """ Adds all the files stored in a given directory in the LFC catalog.
    """
    gLogger.info("TransformationDB.addDirectory: Attempting to populate %s." % path)
    if self.rm is None:
      res = self.__getReplicaManager()
      if not res['OK']:
        return res
    start = time.time()
    res = self.rm.getCatalogDirectoryReplicas(path)
    end = time.time()
    if not res['OK']:
      gLogger.error("TransformationDB.addDirectory: Failed to get replicas. %s" % res['Message'])
      return res
    elif not res['Value']['Successful'].has_key(path):
      gLogger.error("TransformationDB.addDirectory: Failed to get replicas. %s" % res['Message'])
      return res
    else:
      gLogger.info("TransformationDB.addDirectory: Obtained %s replicas in %s seconds." % (path,end-start))
      replicas = res['Value']['Successful'][path]
      fileCount = 0
      filesAdded = 0
      replicaCount = 0
      replicasAdded = 0
      replicasFailed = 0
      replicasForced = 0
      for lfn,replicaDict in replicas.items():
        fileCount += 1
        addFile = False
        for se,pfn in replicaDict.items():
          replicaCount += 1
          replicaTuples = [(lfn,pfn,se,'IGNORED-MASTER')]
          res = self.addReplica(replicaTuples,force)
          if not res['OK']:
            replicasFailed += 1
          elif not res['Value']['Successful'].has_key(lfn):
            replicasFailed += 1
          else:
            addFile = True
            if res['Value']['Successful'][lfn]['AddedToCatalog']:
              replicasAdded += 1
            if res['Value']['Successful'][lfn]['Forced']:
              replicasForced += 1
        if addFile:
          filesAdded += 1
      infoStr = "Found %s files and %s replicas\n" % (fileCount,replicaCount)
      infoStr = "%sAdded %s files.\n" % (infoStr,filesAdded)
      infoStr = "%sAdded %s replicas.\n" % (infoStr,replicasAdded)
      infoStr = "%sFailed to add %s replicas.\n" % (infoStr,replicasFailed)
      infoStr = "%sForced %s replicas." % (infoStr,replicasForced)
      gLogger.info(infoStr)
      return S_OK(infoStr)

  def updateTransformation(self,transName):
    """ Update the transformation w.r.t files registered already
    """
    transID = self.getTransformationID(transName)
    result = self.__addExistingFiles(transID)
    return result

  def __getReplicaManager(self):
    """Gets the RM client instance
    """
    try:
      self.rm = ReplicaManager()
      return S_OK()
    except Exception,x:
      errStr = "TransformationDB.__getReplicaManager: Failed to create ReplicaManager"
      gLogger.exception(errStr, lException=x)
      return S_ERROR(errStr)

  def exists(self,lfns):
    """ Check the presence of the lfn in the TransformationDB DataFiles table
    """
    gLogger.info("TransformationDB.exists: Attempting to determine existence of %s files." % len(lfns))
    fileIDs = self.__getFileIDsForLfns(lfns)
    failed = {}
    successful = {}
    for lfn in lfns:
      if not lfn in fileIDs.values():
        successful[lfn] = False
      else:
        successful[lfn] = True
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def removeFile(self,lfns):
    """ Remove file specified by lfn from the ProcessingDB
    """
    if len(lfns) == 0:
      resDict = {'Successful':{},'Failed':{}}
      return S_OK(resDict)
    gLogger.info("TransformationDB.removeFile: Attempting to remove %s files." % len(lfns))
    res = self.getAllTransformations()
    if res['OK']:
      for transformation in res['Value']:
        transName = transformation['Name']
        res = self.setFileStatusForTransformation(transName,'Deleted',lfns)
    fileIDs = self.__getFileIDsForLfns(lfns)
    failed = {}
    successful = {}
    for lfn in lfns:
      if not lfn in fileIDs.values():
        successful[lfn] = True
    if len(fileIDs.keys()) > 0:
      req = "DELETE Replicas FROM Replicas WHERE FileID IN (%s);" % intListToString(fileIDs.keys())
      res = self._update(req)
      if not res['OK']:
        return S_ERROR("TransformationDB.removeFile: Failed to remove file replicas.")
      #req = "DELETE FROM DataFiles WHERE FileID IN (%s);" % intListToString(fileIDs.keys())
      #res = self._update(req)
      #if not res['OK']:
      #  return S_ERROR("TransformationDB.removeFile: Failed to remove files.")
    for lfn in fileIDs.values():
      successful[lfn] = True
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def addReplica(self,replicaTuples,force=False):
    """ Add new replica to the TransformationDB for an existing lfn.
    """
    gLogger.info("TransformationDB.addReplica: Attempting to add %s replicas." % len(replicaTuples))
    fileTuples = []
    for lfn,pfn,se,master in replicaTuples:
      fileTuples.append((lfn,pfn,0,se,'IGNORED-GUID','IGNORED-CHECKSUM'))
    #print fileTuples
    res = self.addFile(fileTuples,force)
    return res

  def addFile(self,fileTuples,force=False):
    """  Add a new file to the TransformationDB together with its first replica.
    """
    gLogger.info("TransformationDB.addFile: Attempting to add %s files." % len(fileTuples))

    if not fileTuples:
      return S_ERROR('Zero file list')

    successful = {}
    failed = {}
    dataLog = RPCClient('DataManagement/DataLogging',timeout=120)
    for lfn,pfn,size,se,guid,checksum in fileTuples:
      passFilter = False
      forced = False
      retained = False
      fileExists = False
      replicaExists = False
      lFilters = self.__filterFile(lfn)
      if lFilters:
        passFilter = True
        retained = True
      elif force:
        forced = True
        retained = True

      addedToCatalog = False
      addedToTransformation = False

      if retained:
        res = self.__addFile(lfn,pfn,se)
        if not res['OK']:
          failed[lfn] = "TransformationDB.addFile: Failed to add file. %s" % res['Message']
        else:
          addedToCatalog = True
          fileID = res['Value']['FileID']
          fileExists = res['Value']['LFNExist']
          replicaExists = res['Value']['ReplicaExist']
          if lFilters:
            res = self.__addFileToTransformation(fileID,lFilters)
            if res['OK']:
              if res['Value']:
                addedToTransformation = True
                for transID in res['Value']:
                  ret = dataLog.addFileRecord(lfn,'AddedToTransformation','Transformation %s' % transID,'',self.dbname)
                  if not ret['OK']:
                    gLogger.warn('Unable to add dataLogging record for Transformation %s FileID %s' % (transID, fileID))

          successful[lfn] = {'PassFilter':passFilter,'Retained':retained,
                             'Forced':forced,'AddedToCatalog':addedToCatalog,
                             'AddedToTransformation':addedToTransformation,
                             'FileExists':fileExists,'ReplicaExists':replicaExists,
                             'FileID':fileID}
      else:
        successful[lfn] = {'PassFilter':passFilter,'Retained':retained,
                           'Forced':forced,'AddedToCatalog':addedToCatalog,
                           'AddedToTransformation':addedToTransformation,
                           'FileExists':fileExists,'ReplicaExists':replicaExists,
                           'FileID':0}
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def __addFile(self,lfn,pfn,se):
    """ Add file without checking for filters
    """
    lfn_exist = 0
    fileIDs = self.__getFileIDsForLfns([lfn])
    if lfn in fileIDs.values():
      lfn_exist = 1
      fileID = fileIDs.keys()[0]
    else:
      self.lock.acquire()
      req = "INSERT INTO DataFiles (LFN,Status) VALUES ('%s','New');" % lfn
      result = self._getConnection()
      if result['OK']:
        connection = result['Value']
      else:
        return S_ERROR('Failed to get connection to MySQL: '+result['Message'])
      res = self._update(req,connection)
      if not res['OK']:
        self.lock.release()
        return S_ERROR("TransformationDB.__addFile: %s" % res['Message'])
      req = " SELECT LAST_INSERT_ID();"
      res = self._query(req,connection)
      self.lock.release()
      if not res['OK']:
        return S_ERROR("TransformationDB.__addFile: %s" % res['Message'])
      fileID = res['Value'][0][0]

    replica_exist = 0
    res = self.__addReplica(fileID,se,pfn)
    if not res['OK']:
      self.removeFile([lfn])
      return S_ERROR("TransformationDB.__addFile: %s" % res['Message'])
    elif not res['Value']:
      replica_exist = 1

    resDict = {'FileID':fileID,'LFNExist':lfn_exist,'ReplicaExist':replica_exist}
    return S_OK(resDict)

  def __addReplica(self,fileID,se,pfn):
    """ Add a SE,PFN for the given fileID in the Replicas table.

        If the SQL fails this method returns S_ERROR()
        If the replica already exists it returns S_OK(0)
        If the replica was inserted it returns S_OK(1)
    """
    req = "SELECT FileID FROM Replicas WHERE FileID=%s AND SE='%s';" % (fileID,se)
    res = self._query(req)
    if not res['OK']:
      return S_ERROR("TransformationDB.addReplica: %s" % res['Message'])
    elif len(res['Value']) == 0:
      req = "INSERT INTO Replicas (FileID,SE,PFN) VALUES (%s,'%s','%s');" % (fileID,se,pfn)
      res = self._update(req)
      if not res['OK']:
        return S_ERROR("TransformationDB.addReplica: %s" % res['Message'])
      else:
        return S_OK(1)
    else:
      return S_OK(0)


  def removeReplica(self,replicaTuples):
    """ Remove replica pfn of lfn. If this is the last replica then remove the file.
    """
    gLogger.info("TransformationDB.removeReplica: Attempting to remove %s replicas." % len(replicaTuples))
    successful = {}
    failed = {}
    for lfn,pfn,se in replicaTuples:
      req = "DELETE r FROM Replicas as r,DataFiles as d WHERE r.FileID=d.FileID AND d.LFN='%s' AND r.SE='%s';" % (lfn,se)
      res = self._update(req)
      if not res['OK']:
        failed[lfn] = "TransformationDB.removeReplica. Failed to remove replica. %s" % res['Message']
      else:
          successful[lfn] = True
          failedToRemove = False
          res = self.getReplicas([lfn],True)
          if not res['OK']:
            gLogger.error("TransformationDB.removeReplica. Failed to get replicas for file removal",res['Message'])
            failedToRemove = True
          elif not res['Value']['Successful'].has_key(lfn):
            gLogger.error("TransformationDB.removeReplica. Failed to get replicas for file removal",res['Value']['Failed'][lfn])
            failedToRemove = True
          else:
            replicas = res['Value']['Successful'][lfn]
            if len(replicas.keys()) == 0:
              res = self.removeFile([lfn])
              if not res['OK']:
                failedToRemove = True
              elif not res['Value']['Successful'].has_key(lfn):
                failedToRemove = True
          if failedToRemove:
            successful.pop(lfn)
            failed[lfn] = "TransformationDB.removeReplica. Failed to remove replica and associated file."
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def getReplicas(self,lfns,getAll=False):
    """ Get replicas for the files specified by the lfn list
    """
    gLogger.info("TransformationDB.getReplicas: Attempting to get replicas for %s files." % len(lfns))
    fileIDs = self.__getFileIDsForLfns(lfns)
    failed = {}
    successful = {}
    for lfn in lfns:
      if not lfn in fileIDs.values():
        successful[lfn] = {}
    if len(fileIDs.keys()) > 0:
      req = "SELECT FileID,SE,PFN,Status FROM Replicas WHERE FileID IN (%s);" % intListToString(fileIDs.keys())
      res = self._query(req)
      if not res['OK']:
        return res
      for fileID,se,pfn,status in res['Value']:
        takeReplica = True
        if status != "AprioriGood":
          if not getAll:
            takeReplica = False
        if takeReplica:
          lfn = fileIDs[fileID]
          if not successful.has_key(lfn):
            successful[lfn] = {}
          successful[lfn][se] = pfn
    for lfn in fileIDs.values():
      if not successful.has_key(lfn):
        successful[lfn] = {} #"TransformationDB.getReplicas: No replicas found."
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def setReplicaStatus(self,replicaTuples):
    """Set status for the supplied replica tuples
    """
    gLogger.info("TransformationDB.setReplicaStatus: Attempting to set statuses for %s replicas." % len(replicaTuples))
    successful = {}
    failed = {}
    for lfn,pfn,se,status in replicaTuples:
      fileIDs = self.__getFileIDsForLfns([lfn])
      if not lfn in fileIDs.values():
        successful[lfn] = True # In the case that the file does not exist then return ok
      else:
        fileID = fileIDs.keys()[0]
        if se.lower() == "any" :
          req = "UPDATE Replicas SET Status='%s' WHERE FileID=%s;" % (status,fileID)
        else:
          req = "UPDATE Replicas SET Status='%s' WHERE FileID= %s AND SE = '%s';" % (status,fileID,se)
        res = self._update(req)
        if not res['OK']:
          failed[lfn] = "TransformationDB.setReplicaStatus: Failed to update status."
        else:
          successful[lfn] = True
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def getReplicaStatus(self,replicaTuples):
    """ Get the status for the supplied file replicas
    """
    gLogger.info("TransformationDB.getReplicaStatus: Attempting to get statuses of file replicas.")
    lfns = []
    for lfn,se in replicaTuples:
      lfns.append(lfn)
    fileIDs = self.__getFileIDsForLfns(lfns)
    failed = {}
    successful = {}
    for lfn,se in replicaTuples:
      if not lfn in fileIDs.values():
        failed[lfn] = "TransformationDB.getReplicaStatus: File not found."
    req = "SELECT FileID,SE,Status FROM Replicas WHERE FileID IN (%s);" % intListToString(fileIDs.keys())
    res = self._query(req)
    if not res['OK']:
      return res
    for fileID,se,status in res['Value']:
      lfn = fileIDs[fileID]
      if not successful.has_key(lfn):
        successful[lfn] = {}
      successful[lfn][se] = status
    for lfn in fileIDs.values():
      if not successful.has_key(lfn):
        failed[lfn] = "TransformationDB.getReplicaStatus: No replicas found."
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def setReplicaHost(self,replicaTuples):
    gLogger.info("TransformationDB.setReplicaHost: Attempting to set SE for %s replicas." % len(replicaTuples))
    successful = {}
    failed = {}
    for lfn,pfn,oldse,newse in replicaTuples:
      fileIDs = self.__getFileIDsForLfns([lfn])
      if not lfn in fileIDs.values():
        successful[lfn] = True # If the file does not exist then return that it was OK
      else:
        ############## Need to consider the case where the new se already exists for the file (breaks the primary key restriction)
        fileID = fileIDs.keys()[0]
        req = "UPDATE Replicas SET SE='%s' WHERE FileID=%s AND SE ='%s';" % (newse,fileID,oldse)
        res = self._update(req)
        if not res['OK']:
          failed[lfn] = "TransformationDB.setReplicaHost: Failed to update status."
        else:
          successful[lfn] = True
    resDict = {'Successful':successful,'Failed':failed}
    return S_OK(resDict)

  def addBookkeepingQuery(self,queryDict):
    """ Add a new Bookkeeping query specification
    """

    queryFields = ['SimulationConditions','DataTakingConditions','ProcessingPass','FileType','EventType',
                   'ConfigName','ConfigVersion','ProductionID','DataQualityFlag']

    parameters = []
    values = []
    qvalues = []
    for field in queryFields:
      if field in queryDict.keys():
        parameters.append(field)
        if field == 'ProductionID' or field == 'EventType':
          values.append(str(queryDict[field]))
          qvalues.append(str(queryDict[field]))
        else:
          values.append("'"+queryDict[field]+"'")
          qvalues.append(queryDict[field])
      else:
        if field == 'ProductionID' or field == 'EventType':
          qvalues.append(0)
        else:
          qvalues.append('All')

    # Check for the already existing queries first
    selections = []
    for i in range(len(queryFields)):
      selections.append(queryFields[i]+"='"+str(qvalues[i])+"'")
    selectionString = ' AND '.join(selections)
    req = "SELECT BkQueryID FROM BkQueries WHERE %s" % selectionString
    result = self._query(req)
    if not result['OK']:
      return result
    if result['Value']:
      bkQueryID = result['Value'][0][0]
      return S_OK(bkQueryID)

    req = "INSERT INTO BkQueries (%s) VALUES (%s)" % (','.join(parameters),','.join(values))

    self.lock.acquire()
    result = self._getConnection()
    if result['OK']:
      connection = result['Value']
    else:
      return S_ERROR('Failed to get connection to MySQL: '+result['Message'])
    res = self._update(req,connection)
    if not res['OK']:
      self.lock.release()
      return res
    req = "SELECT LAST_INSERT_ID();"
    res = self._query(req,connection)
    self.lock.release()
    if not res['OK']:
      return res
    queryID = int(res['Value'][0][0])

    return S_OK(queryID)

  def getBookkeepingQueryForTransformation(self,transName):
    """
    """

    transID = self.getTransformationID(transName)
    req = "SELECT BkQueryID FROM Transformations WHERE TransformationID=%s" % (transID)
    result = self._query(req)
    if not result['OK']:
      return result

    if not result['Value']:
      return S_ERROR('Transformation %s not found' % transID)

    bkQueryID = result['Value'][0][0]
    return self.getBookkeepingQuery(bkQueryID)

  def getBookkeepingQuery(self,bkQueryID=0):
    """ Get the bookkeeping query parameters, if bkQueyID is 0 then get all the queries
    """

    queryFields = ['SimulationConditions','DataTakingConditions','ProcessingPass',
                   'FileType','EventType','ConfigName','ConfigVersion','ProductionID','DataQualityFlag']

    fieldsString = ','.join(queryFields)

    if bkQueryID:
      req = "SELECT BkQueryID,%s FROM BkQueries WHERE BkQueryID=%d" % (fieldsString,int(bkQueryID))
    else:
      req = "SELECT BkQueryID,%s FROM BkQueries" % (fieldsString,)
    result = self._query(req)
    if not result['OK']:
      return result

    if not result['Value']:
      return S_ERROR('BkQuery %d not found' % int(bkQueryID))

    resultDict = {}
    for row in result['Value']:
      bkDict = {}
      for parameter,value in zip(['BkQueryID']+queryFields,row):
        bkDict[parameter] = value
      resultDict[bkDict['BkQueryID']] = bkDict

    if bkQueryID:
      return S_OK(bkDict)
    else:
      return S_OK(resultDict)

  def deleteBookkeepingQuery(self,bkQueryID):
    """ Delete the specified query from the database
    """

    req = 'DELETE FROM BkQueries WHERE BkQueryID=%d' % int(bkQueryID)
    result = self._update(req)
    return result

