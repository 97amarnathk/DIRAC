########################################################################
# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/DataManagementSystem/Service/DataIntegrityHandler.py,v 1.6 2009/09/03 16:32:16 acsmith Exp $
########################################################################
__RCSID__   = "$Id: DataIntegrityHandler.py,v 1.6 2009/09/03 16:32:16 acsmith Exp $"
__VERSION__ = "$Revision: 1.6 $"

""" DataIntegrityHandler is the implementation of the Data Integrity service in the DISET framework """

from types import *
from DIRAC.Core.DISET.RequestHandler import RequestHandler
from DIRAC import gLogger, gConfig, rootPath, S_OK, S_ERROR
from DIRAC.DataManagementSystem.DB.DataIntegrityDB import DataIntegrityDB
import time,os
# This is a global instance of the DataIntegrityDB class
integrityDB = False

def initializeDataIntegrityHandler(serviceInfo):

  global integrityDB
  integrityDB = DataIntegrityDB()
  return S_OK()

class DataIntegrityHandler(RequestHandler):

  types_removeProblematic = [[IntType,LongType]]
  def export_removeProblematic(self,fileID):
    """ Remove the file with the supplied FileID from the database
    """
    try:
      gLogger.info("DataIntegrityHandler.removeProblematic: Attempting to remove problematic.")
      res = integrityDB.removeProblematic(fileID)
      if res['OK']:
        gLogger.info("DataIntegrityHandler.removeProblematic: Successfully removed problematic.")
      else:
        gLogger.error("DataIntegrityHandler.removeProblematic: Failed to remove problematic.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.removeProblematic: Exception while removing problematic."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_getProblematic = []
  def export_getProblematic(self):
    """ Get the next problematic to resolve from the IntegrityDB
    """ 
    try:
      gLogger.info("DataIntegrityHandler.getProblematic: Attempting to get file to resolve.")
      res = integrityDB.getProblematic()
      if res['OK']:
        gLogger.info("DataIntegrityHandler.getProblematic: Found problematic file to resolve.")
      else:
        gLogger.error("DataIntegrityHandler.getProblematic: Failed to get problematic file to resolve.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.getProblematic: Exception while getting problematic file."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_getPrognosisProblematics = [StringType]
  def export_getPrognosisProblematics(self,prognosis):
    """ Get problematic files from the problematics table of the IntegrityDB
    """
    try:
      gLogger.info("DataIntegrityHandler.getPrognosisProblematics: Attempting to get files with %s prognosis." % prognosis)
      res = integrityDB.getPrognosisProblematics(prognosis)
      if res['OK']:
        gLogger.info("DataIntegrityHandler.getPrognosisProblematics: Found %s files with prognosis." % len(res['Value']))
      else:
        gLogger.error("DataIntegrityHandler.getPrognosisProblematics: Failed to get prognosis files.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.getPrognosisProblematics: Exception while getting prognosis files."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_setProblematicStatus = [[IntType,LongType],StringType]
  def export_setProblematicStatus(self,fileID,status):
    """ Update the status of the problematics with the provided fileID
    """
    try:
      gLogger.info("DataIntegrityHandler.setProblematicStatus: Attempting to set file %s status to %s." % (fileID,status))
      res = integrityDB.setProblematicStatus(fileID,status)
      if res['OK']:
        gLogger.info("DataIntegrityHandler.setProblematicStatus: Successful.")
      else:
        gLogger.error("DataIntegrityHandler.setProblematicStatus: Failed to set status.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.setProblematicStatus: Exception while setting file status."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_getProblematicsSummary = []
  def export_getProblematicsSummary(self):
    """ Get a summary from the Problematics table from the IntegrityDB
    """
    try:
      gLogger.info("DataIntegrityHandler.getProblematicsSummary: Attempting to get problematics summary.")
      res = integrityDB.getProblematicsSummary()
      if res['OK']:
        for prognosis,statusDict in res['Value'].items():
          gLogger.info("DataIntegrityHandler.getProblematicsSummary: %s." % prognosis)
          for status,count in statusDict.items():
            gLogger.info("DataIntegrityHandler.getProblematicsSummary: \t%s %s." % (status.ljust(10),str(count).ljust(10)))
      else:
        gLogger.error("DataIntegrityHandler.getProblematicsSummary: Failed to get summary.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.getProblematicsSummary: Exception while getting summary."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_getDistinctPrognosis = []
  def export_getDistinctPrognosis(self):
    """ Get a list of the distinct prognosis from the IntegrityDB
    """
    try:
      gLogger.info("DataIntegrityHandler.getDistinctPrognosis: Attempting to get distinct prognosis.")
      res = integrityDB.getDistinctPrognosis()
      if res['OK']:
        for prognosis in res['Value']:
          gLogger.info("DataIntegrityHandler.getDistinctPrognosis: \t%s." % prognosis)
      else:
        gLogger.error("DataIntegrityHandler.getDistinctPrognosis: Failed to get unique prognosis.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.getDistinctPrognosis: Exception while getting summary."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_incrementProblematicRetry = [[IntType,LongType]]
  def export_incrementProblematicRetry(self,fileID):
    """ Update the retry count for supplied file ID.
    """
    try:
      gLogger.info("DataIntegrityHandler.incrementProblematicRetry: Attempting to increment retries for file %s." % (fileID))
      res = integrityDB.incrementProblematicRetry(fileID)
      if res['OK']:
        gLogger.info("DataIntegrityHandler.incrementProblematicRetry: Successful.")
      else:
        gLogger.error("DataIntegrityHandler.incrementProblematicRetry: Failed to increment retries.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.incrementProblematicRetry: Exception while incrementing retries."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)

  types_insertProblematic = [StringType,DictType]
  def export_insertProblematic(self,source,fileMetadata):
    """ Insert problematic files into the problematics table of the IntegrityDB
    """
    try:
      gLogger.info("DataIntegrityHandler.insertProblematic: Attempting to insert problematic file to integrity DB.")
      res = integrityDB.insertProblematic(source,fileMetadata)
      if res['OK']:
        gLogger.info("DataIntegrityHandler.insertProblematic: Successful.")
      else:
        gLogger.error("DataIntegrityHandler.insertProblematic: Failed to insert.", res['Message'])
      return res
    except Exception, x:
      errStr = "DataIntegrityHandler.insertProblematic: Exception while inserting problematic."
      gLogger.exception(errStr,lException=x)
      return S_ERROR(errStr)
