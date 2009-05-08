"""  StorageUsageAgent takes the LFC as the primary source of information to determine storage usage.
"""
from DIRAC  import gLogger, gConfig, gMonitor, S_OK, S_ERROR
from DIRAC.Core.Base.Agent import Agent
from DIRAC.Core.Utilities.Pfn import pfnparse, pfnunparse
from DIRAC.Core.DISET.RPCClient import RPCClient
from DIRAC.Core.Utilities.Shifter import setupShifterProxyInEnv
from DIRAC.RequestManagementSystem.Client.DataManagementRequest import DataManagementRequest
from DIRAC.DataManagementSystem.Client.ReplicaManager import ReplicaManager
from DIRAC.DataManagementSystem.Agent.NamespaceBrowser import NamespaceBrowser
from DIRAC.DataManagementSystem.Client.FileCatalog import FileCatalog
from DIRAC.Core.Utilities.List import sortList

import time,os
from types import *


class StorageUsageAgent(Agent):

  def __init__(self):
    """ Standard constructor
    """
    AGENT_NAME = gConfig.getValue('/AgentName','DataManagement/StorageUsageAgent')
    Agent.__init__(self,AGENT_NAME)

  def initialize(self):
    result = Agent.initialize(self)
    self.lfc = FileCatalog(['LcgFileCatalogCombined'])

    self.useProxies = gConfig.getValue(self.section+'/UseProxies','True').lower() in ( "y", "yes", "true" )
    self.proxyLocation = gConfig.getValue( self.section+'/ProxyLocation', '' )
    if not self.proxyLocation:
      self.proxyLocation = False

    return result

  def execute(self):

    StorageUsageDB = RPCClient('DataManagement/StorageUsage')

    if self.useProxies:
      result = setupShifterProxyInEnv( "DataManager", self.proxyLocation )
      if not result[ 'OK' ]:
        self.log.error( "Can't get shifter's proxy: %s" % result[ 'Message' ] )
        return result

    res = StorageUsageDB.getStorageSummary()
    if res['OK']:
      gLogger.info("StorageUsageAgent: Storage Usage Summary")
      gLogger.info("============================================================")
      gLogger.info("StorageUsageAgent: %s %s %s" % ('Storage Element'.ljust(40),'Number of files'.rjust(20),'Total size'.rjust(20)))
      for se in sortList(res['Value'].keys()):
        usage = res['Value'][se]['Size']
        files = res['Value'][se]['Files']
        site = se.split('_')[0].split('-')[0]
        gLogger.info("StorageUsageAgent: %s %s %s" % (se.ljust(40),str(files).rjust(20),str(usage).rjust(20)))
        gMonitor.registerActivity("%s-used" % se, "%s usage" % se,"StorageUsage/%s usage" % site,"",gMonitor.OP_MEAN,bucketLength = 600)
        gMonitor.addMark("%s-used" % se, usage )
        gMonitor.registerActivity("%s-files" % se, "%s files" % se,"StorageUsage/%s files" % site,"Files",gMonitor.OP_MEAN, bucketLength = 600)
        gMonitor.addMark("%s-files" % se, files )

    baseDir = gConfig.getValue(self.section+'/BaseDirectory','/lhcb')
    ignoreDirectories = gConfig.getValue(self.section+'/Ignore',[])
    oNamespaceBrowser = NamespaceBrowser(baseDir)
    gLogger.info("StorageUsageAgent: Initiating with %s as base directory." % baseDir)

    # Loop over all the directories and sub-directories
    while (oNamespaceBrowser.isActive()):
      currentDir = oNamespaceBrowser.getActiveDir()
      gLogger.info("StorageUsageAgent: Getting usage for %s." % currentDir)
      numberOfFiles = 0
      res = self.lfc.getDirectorySize(currentDir)
      if not res['OK']:
        gLogger.error("StorageUsageAgent: Completely failed to get usage.", "%s %s" % (currentDir,res['Message']))
        subDirs = [currentDir]
      elif res['Value']['Failed'].has_key(currentDir):
        gLogger.error("StorageUsageAgent: Failed to get usage.", "%s %s" % (currentDir,res['Value']['Failed'][currentDir]))
        subDirs = [currentDir]
      else:
        subDirs = res['Value']['Successful'][currentDir]['SubDirs']
        gLogger.info("StorageUsageAgent: Found %s sub-directories." % len(subDirs))
        numberOfFiles = int(res['Value']['Successful'][currentDir]['Files'])
        gLogger.info("StorageUsageAgent: Found %s files in the directory." % numberOfFiles)
        totalSize = long(res['Value']['Successful'][currentDir]['TotalSize'])

        siteUsage = res['Value']['Successful'][currentDir]['SiteUsage']

        if numberOfFiles > 0:
          res = StorageUsageDB.insertDirectory(currentDir,numberOfFiles,totalSize)
          if not res['OK']:
            gLogger.error("StorageUsageAgent: Failed to insert the directory.", "%s %s" % (currentDir,res['Message']))
            subDirs = [currentDir]
          else:
            gLogger.info("StorageUsageAgent: Successfully inserted directory.\n")
            gLogger.info("StorageUsageAgent: %s %s %s" % ('Storage Element'.ljust(40),'Number of files'.rjust(20),'Total size'.rjust(20)))
            for storageElement in sortList(siteUsage.keys()):
              usageDict = siteUsage[storageElement]
              res = StorageUsageDB.publishDirectoryUsage(currentDir,storageElement,long(usageDict['Size']),usageDict['Files'])
              if not res['OK']:
                gLogger.error("StorageUsageAgent: Failed to update the Storage Usage database.", "%s %s" % (storageElement,res['Message']))
                subDirs = [currentDir]
              else:
                gLogger.info("StorageUsageAgent: %s %s %s" % (storageElement.ljust(40),str(usageDict['Files']).rjust(20),str(usageDict['Size']).rjust(20)))

      # If there are no subdirs
      if (len(subDirs) ==  0) and (numberOfFiles == 0):
        gLogger.info("StorageUsageAgent: Attempting to remove empty directory from Storage Usage database")
        res = StorageUsageDB.publishEmptyDirectory(currentDir)
        if not res['OK']:
          gLogger.error("StorageUsageAgent: Failed to remove empty directory from Storage Usage database.",res['Message'])
        else:
          res = self.lfc.removeDirectory(currentDir)
          if not res['OK']:
            gLogger.error("StorageUsageAgent: Failed to remove empty directory from File Catalog.",res['Message'])
          elif res['Value']['Failed'].has_key(currentDir):
            gLogger.error("StorageUsageAgent: Failed to remove empty directory from File Catalog.",res['Value']['Failed'][currentDir])
          else:
            gLogger.info("StorageUsageAgent: Successfully removed empty directory from File Catalog.")

      chosenDirs = []
      for subDir in subDirs:
        if subDir not in ignoreDirectories:
          chosenDirs.append(subDir)
      oNamespaceBrowser.updateDirs(chosenDirs)
      gLogger.info("StorageUsageAgent: There are %s active directories to be searched." % oNamespaceBrowser.getNumberActiveDirs())

    gLogger.info("StorageUsageAgent: Finished recursive directory search.")
    return S_OK()


