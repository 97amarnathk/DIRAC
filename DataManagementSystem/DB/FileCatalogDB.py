""" DIRAC FileCatalog Database """

__RCSID__ = "$Id$"

from DIRAC                                                            import gLogger, S_OK, S_ERROR
from DIRAC.Core.Base.DB                                               import DB
from DIRAC.DataManagementSystem.DB.FileCatalogComponents.Utilities    import checkArgumentFormat
from DIRAC.Core.Utilities.ObjectLoader import ObjectLoader

#############################################################################
class FileCatalogDB( DB ):

  __tables = {}
  __tables["FC_Statuses"] = { "Fields":
                              {
                                "StatusID": "INT AUTO_INCREMENT",
                                "Status": "VARCHAR(32)"
                              },
                              "UniqueIndexes": { "Status": ["Status"] },
                              "PrimaryKey":"StatusID" 
                            }

  def __init__( self, databaseLocation = 'DataManagement/FileCatalogDB' ):
    """ Standard Constructor
    """

    # The database location can be specified in System/Database form or in just the Database name
    # in the DataManagement system
    db = databaseLocation
    if db.find( '/' ) == -1:
      db = 'DataManagement/' + db
    DB.__init__( self,'FileCatalogDB', db )
    
    result = self._createTables( self.__tables )
    if not result['OK']:
      gLogger.error( "Failed to create tables", str( self.__tables.keys() ) )
    elif result['Value']:
      gLogger.info( "Tables created: %s" % ','.join( result['Value'] ) )    
    
    self.ugManager = None
    self.seManager = None
    self.securityManager = None
    self.dtree = None
    self.fileManager = None
    self.dmeta = None
    self.fmeta = None
    self.statusDict = {}

  def setConfig( self, databaseConfig ):

    self.directories = {}
    # In memory storage of the various parameters
    self.users = {}
    self.uids = {}
    self.groups = {}
    self.gids = {}
    self.seNames = {}
    self.seids = {}
    self.seDefinitions = {}

    # Obtain some general configuration of the database
    self.uniqueGUID = databaseConfig['UniqueGUID']
    self.globalReadAccess = databaseConfig['GlobalReadAccess']
    self.lfnPfnConvention = databaseConfig['LFNPFNConvention']
    if self.lfnPfnConvention == "None":
      self.lfnPfnConvention = False
    self.resolvePfn = databaseConfig['ResolvePFN']
    self.umask = databaseConfig['DefaultUmask']
    self.validFileStatus = databaseConfig['ValidFileStatus']
    self.validReplicaStatus = databaseConfig['ValidReplicaStatus']
    self.visibleFileStatus = databaseConfig['VisibleFileStatus']
    self.visibleReplicaStatus = databaseConfig['VisibleReplicaStatus']

    # Obtain the plugins to be used for DB interaction
    self. objectLoader = ObjectLoader()
    
    result = self.__loadCatalogComponent( databaseConfig['UserGroupManager'] )
    if not result['OK']:
      return result
    self.ugManager = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['SEManager'] )
    if not result['OK']:
      return result
    self.seManager = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['SecurityManager'] )
    if not result['OK']:
      return result
    self.securityManager = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['DirectoryManager'] )
    if not result['OK']:
      return result
    self.dtree = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['FileManager'] )
    if not result['OK']:
      return result
    self.fileManager = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['DatasetManager'] )
    if not result['OK']:
      return result
    self.datasetManager = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['DirectoryMetadata'] )
    if not result['OK']:
      return result
    self.dmeta = result['Value']
    
    result = self.__loadCatalogComponent( databaseConfig['FileMetadata'] )
    if not result['OK']:
      return result
    self.fmeta = result['Value']

    return S_OK()
  
  def __loadCatalogComponent( self, componentName ):
    """ Create an object of a given catalog component
    """
    moduleName = componentName
    # some modules contain several implementation classes
    for m in ['SEManager','UserAndGroupManager','SecurityManager']:
      if m in componentName:
        moduleName = m
    componentPath = 'DataManagementSystem.DB.FileCatalogComponents'
    result = self.objectLoader.loadObject( '%s.%s' % ( componentPath, moduleName ), 
                                      componentName )
    if not result['OK']:
      gLogger.error( 'Failed to load catalog component', result['Message'] )
      return result
    componentClass = result['Value']
    component = componentClass( self )
    return S_OK( component )
    
  def setUmask(self,umask):
    self.umask = umask

  ########################################################################
  #
  #  General purpose utility methods

  def getStatusInt( self, status, connection = False ):
    
    """ Get integer ID of the given status string
    """
    connection = self._getConnection( connection )
    req = "SELECT StatusID FROM FC_Statuses WHERE Status = '%s';" % status
    res = self.db._query( req, connection )
    if not res['OK']:
      return res
    if res['Value']:
      return S_OK( res['Value'][0][0] )
    req = "INSERT INTO FC_Statuses (Status) VALUES ('%s');" % status
    res = self.db._update( req, connection )
    if not res['OK']:
      return res
    return S_OK( res['lastRowId'] )

  def getIntStatus(self,statusID,connection=False):
    """ Get status string for a given integer status ID
    """
    if statusID in self.statusDict:
      return S_OK(self.statusDict[statusID])
    connection = self._getConnection(connection)
    req = "SELECT StatusID,Status FROM FC_Statuses" 
    res = self.db._query(req,connection)
    if not res['OK']:
      return res
    if res['Value']:
      for row in res['Value']:
        self.statusDict[int(row[0])] = row[1]
    if statusID in self.statusDict:
      return S_OK(self.statusDict[statusID])
    return S_OK('Unknown')

  ########################################################################
  #
  #  SE based write methods
  #

  def addSE( self, seName, credDict ):
    """
        Add a new StorageElement
        :param str seName Name of the StorageElement
        :param credDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.seManager.addSE( seName )

  def deleteSE( self, seName, credDict ):
    """
      Delete a StorageElement
      :param str seName Name of the StorageElement
      :param creDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.seManager.deleteSE( seName )

  ########################################################################
  #
  #  User/groups based write methods
  #

  def addUser( self, userName, credDict ):
    """
      Add a new user
      :param str userName Name of the User
      :param creDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.addUser( userName )

  def deleteUser( self, userName, credDict ):
    """
      Delete a user
      :param str userName Name of the User
      :param creDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.deleteUser( userName )

  def addGroup( self, groupName, credDict ):
    """
      Add a new group
      :param str groupName Name of the group
      :param creDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.addGroup( groupName )

  def deleteGroup( self, groupName, credDict ):
    """
      Delete a group
      :param str groupName Name of the group
      :param creDict credential
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.deleteGroup( groupName )

  ########################################################################
  #
  #  User/groups based read methods
  #

  def getUsers( self, credDict ):
    """
      Returns the list of users
      :param creDict credential

      :return dictionary indexed on the user name
    """
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.getUsers()

  def getGroups( self, credDict ):
    """
      Returns the list of groups
      :param creDict credential

      :return dictionary indexed on the group name
    """

    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    return self.ugManager.getGroups()

  ########################################################################
  #
  #  Path based read methods
  #

  def exists( self, lfns, credDict ):
    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.exists( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    notExist = []
    for lfn in res['Value']['Successful'].keys():
      if not successful[lfn]:
        notExist.append( lfn )
        successful.pop( lfn )
    if notExist:
      res = self.dtree.exists( notExist )
      if not res['OK']:
        return res
      failed.update( res['Value']['Failed'] )
      successful.update( res['Value']['Successful'] )
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getPathPermissions( self, lfns, credDict ):
    """ Get permissions for the given user/group to manipulate the given lfns
    """
    res = checkArgumentFormat( lfns )
    if not res['OK']:
      return res
    lfns = res['Value']

    return self.securityManager.getPathPermissions( lfns.keys(), credDict )

  ########################################################################
  #
  #  Path based read methods
  #

  def changePathOwner( self, lfns, credDict, recursive = False ):
    """ Change the owner of the given list of paths
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.changePathOwner( res['Value']['Successful'], credDict, recursive )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def changePathGroup( self, lfns, credDict, recursive = False ):
    """ Change the group of the given list of paths
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.changePathGroup( res['Value']['Successful'], credDict, recursive )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def changePathMode( self, lfns, credDict, recursive = False ):
    """ Change the mode of the given list of paths
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.changePathMode( res['Value']['Successful'], credDict, recursive )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  ########################################################################
  #
  #  File based write methods
  #

  def addFile( self, lfns, credDict ):
    """
      Add a new File
      :param dict lfns: indexed on file's LFN, the values are dictionaries which contains
                        the attributes of the files (PFN, SE, Size, GUID, Checksum)
      :param creDict credential

      :return Successful/Failed dict.
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.addFile( res['Value']['Successful'], credDict )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setFileStatus( self, lfns, credDict ):
    """
      Set the status of a File
      :param dict lfns: dict indexed on the LFNs. The values are the status (should be in config['ValidFileStatus'])
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setFileStatus( res['Value']['Successful'], credDict )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def removeFile( self, lfns, credDict ):
    """
       Remove files
      :param list lfns: list of LFNs to remove
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Delete', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.removeFile( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def addReplica( self, lfns, credDict ):
    """
       Add a replica to a File
      :param dict lfns: keys are LFN. The values are dict with key PFN and SE
                        (e.g. {myLfn : {"PFN" : "myPfn", "SE" : "mySE"}})
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.addReplica( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def removeReplica( self, lfns, credDict ):
    """
       Remove replicas
      :param dict lfns: keys are LFN. The values are dict with key PFN and SE
                        (e.g. {myLfn : {"PFN" : "myPfn", "SE" : "mySE"}})
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Delete', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.removeReplica( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setReplicaStatus( self, lfns, credDict ):
    """
      Set the status of a Replicas
      :param dict lfns: dict indexed on the LFNs. The values are dict with keys
                        "SE" and "Status" (that has to be in config['ValidReplicaStatus'])
      :param creDict credential

      :return Successful/Failed dict.
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setReplicaStatus( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setReplicaHost( self, lfns, credDict ):
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setReplicaHost( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setFileOwner( self, lfns, credDict ):
    """
      Set the owner of a File
      :param dict lfns: dict indexed on the LFNs. The values are the owner's name
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setFileOwner( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setFileGroup( self, lfns, credDict ):
    """
      Set the group of a File
      :param dict lfns: dict indexed on the LFNs. The values are the grou's name
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setFileGroup( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def setFileMode( self, lfns, credDict ):
    """
      Set the mode of a File
      :param dict lfns: dict indexed on the LFNs. The values are the modes (posix like)
      :param creDict credential

      :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.setFileMode( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def addFileAncestors( self, lfns, credDict ):
    """ Add ancestor information for the given LFNs
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.addFileAncestors( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  ########################################################################
  #
  #  File based read methods
  #

  def isFile( self, lfns, credDict ):
    """
        Checks whether a list of LFNS are files or not
        :param list lfns: list of LFN to check
        :param creDict credential

        :return Successful/Failed dict.
                The values of the successful dict are True or False whether it's a file or not
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.isFile( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getFileSize( self, lfns, credDict ):
    """
        Gets the size of a list of lfns
        :param list lfns: list of LFN to check
        :param creDict credential

        :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getFileSize( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getFileMetadata( self, lfns, credDict ):
    """
        Gets the metadata of a list of lfns
        :param list lfns: list of LFN to check
        :param creDict credential

        :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getFileMetadata( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getReplicas( self, lfns, allStatus, credDict ):
    """
        Gets the list of replicas of a list of lfns
        :param list lfns: list of LFN to check
        :param allStatus : if all the status are visible, or only those defined in config['ValidReplicaStatus']
        :param creDict credential

        :return Successful/Failed dict.
        Successful is indexed on the LFN, and the values are dictionary with the SEName as keys
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getReplicas( res['Value']['Successful'], allStatus = allStatus )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed, 'SEPrefixes': res['Value'].get( 'SEPrefixes', {} ) } )

  def getReplicaStatus( self, lfns, credDict ):
    """
        Gets the status of a list of replicas
        :param dict lfns: <lfn, se name>
        :param creDict credential

        :return Successful/Failed dict.
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getReplicaStatus( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getFileAncestors( self, lfns, depths, credDict ):
    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getFileAncestors( res['Value']['Successful'], depths )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getFileDescendents( self, lfns, depths, credDict ):
    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.fileManager.getFileDescendents( res['Value']['Successful'], depths )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getFileDetails( self, lfnList, credDict ):
    """ Get all the metadata for the given files
    """
    connection = False
    result = self.fileManager._findFiles( lfnList, connection = connection )
    if not result['OK']:
      return result
    resultDict = {}
    fileIDDict = {}
    lfnDict = result['Value']['Successful']
    for lfn in lfnDict:
      fileIDDict[lfnDict[lfn]['FileID']] = lfn

    result = self.fileManager._getFileMetadataByID( fileIDDict.keys(), connection = connection )
    if not result['OK']:
      return result
    for fileID in result['Value']:
      resultDict[ fileIDDict[fileID] ] = result['Value'][fileID]

    result = self.fmeta._getFileUserMetadataByID( fileIDDict.keys(), credDict, connection = connection )
    if not result['OK']:
      return result
    for fileID in fileIDDict:
      resultDict[ fileIDDict[fileID] ].setdefault( 'Metadata', {} )
      if fileID in result['Value']:
        resultDict[ fileIDDict[fileID] ]['Metadata'] = result['Value'][fileID]

    return S_OK( resultDict )

  def getLFNForGUID( self, guids, credDict ):
    """
        Gets the lfns that match a list of guids
        :param list lfns: list of guid to look for
        :param creDict credential

        :return S_OK({guid:lfn}) dict.
    """

    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    res = self.fileManager.getLFNForGUID( guids )

    return res
  ########################################################################
  #
  #  Directory based Write methods
  #

  def createDirectory( self, lfns, credDict ):
    """
        Create new directories
        :param list lfns: list of directories
        :param creDict credential

        :return Successful/Failed dict.
    """
    res = self._checkPathPermissions( 'Write', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.dtree.createDirectory( res['Value']['Successful'], credDict )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def removeDirectory( self, lfns, credDict ):
    """
        Remove directories
        :param list lfns: list of directories
        :param creDict credential

        :return Successful/Failed dict.
    """
    res = self._checkPathPermissions( 'Delete', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    successful = res['Value']['Successful']
    if successful:
      res = self.dtree.removeDirectory( res['Value']['Successful'], credDict )
      if not res['OK']:
        return res
      failed.update( res['Value']['Failed'] )
      successful = res['Value']['Successful']
      if not successful:
        return S_OK( {'Successful':successful, 'Failed':failed} )
    else:
      return S_OK( {'Successful':successful, 'Failed':failed} )

    # Remove the directory metadata now
    dirIdList = [ successful[p]['DirID'] for p in successful if 'DirID' in successful[p] ]
    result = self.dmeta.removeMetadataForDirectory( dirIdList, credDict )
    if not result['OK']:
      return result
    failed.update( result['Value']['Failed'] )
    # We remove from The successful those that failed in the metadata removal
    map( lambda x: successful.pop( x ) if x in successful else None, failed )
    # We update the successful
    successful.update( result["Value"]["Successful"] )
    return S_OK( {'Successful':successful, 'Failed':failed} )

  ########################################################################
  #
  #  Directory based read methods
  #

  def listDirectory( self, lfns, credDict, verbose = False ):
    """
        List directories
        :param list lfns: list of directories
        :param creDict credential

        :return Successful/Failed dict.
        The successful values are dictionaries indexed "Files", "Datasets", "Subdirs" and "Links"
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.dtree.listDirectory( res['Value']['Successful'], verbose = verbose )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def isDirectory( self, lfns, credDict ):
    """
        Checks whether a list of LFNS are directories or not
        :param list lfns: list of LFN to check
        :param creDict credential

        :return Successful/Failed dict.
                The values of the successful dict are True or False whether it's a dir or not
    """

    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.dtree.isDirectory( res['Value']['Successful'] )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( {'Successful':successful, 'Failed':failed} )

  def getDirectoryReplicas( self, lfns, allStatus, credDict ):
    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.dtree.getDirectoryReplicas( res['Value']['Successful'], allStatus )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    return S_OK( { 'Successful':successful, 'Failed':failed, 'SEPrefixes': res['Value'].get( 'SEPrefixes', {} )} )

  def getDirectorySize( self, lfns, longOutput, fromFiles, credDict ):
    """
        Get the sizes of a list of directories
        :param list lfns: list of LFN to check
        :param creDict credential

        :return Successful/Failed dict.
         The successful values are dictionaries indexed "LogicalFiles" (nb of files),
         "LogicalDirectories" (nb of dir) and "LogicalSize" (sum of File's sizes)
    """


    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    res = self.dtree.getDirectorySize( res['Value']['Successful'], longOutput, fromFiles )
    if not res['OK']:
      return res
    failed.update( res['Value']['Failed'] )
    successful = res['Value']['Successful']
    queryTime = res['Value'].get( 'QueryTime', -1. )
    return S_OK( {'Successful':successful, 'Failed':failed, 'QueryTime':queryTime} )

  def getDirectoryMetadata( self, lfns, credDict ):
    ''' Get standard directory metadata
    :param list lfns: list of directory paths
    :param dict credDict: credentials
    :return: Successful/Failed dict.
    '''
    res = self._checkPathPermissions( 'Read', lfns, credDict )
    if not res['OK']:
      return res
    failed = res['Value']['Failed']
    successful = {}
    for lfn in res['Value']['Successful']:
      result = self.dtree.getDirectoryParameters( lfn )
      if result['OK']:
        successful[lfn] = result['Value']
      else:
        failed[lfn] = result['Message']

    return S_OK( { 'Successful': successful, 'Failed': failed } )

  def rebuildDirectoryUsage( self ):
    """ Rebuild DirectoryUsage table from scratch
    """

    result = self.dtree._rebuildDirectoryUsage()
    return result

  def repairCatalog( self, directoryFlag = True, credDict = {} ):
    """ Repair catalog inconsistencies
    """
    result = S_OK()
    if directoryFlag:
      result = self.dtree.recoverOrphanDirectories( credDict )

    return result

  #######################################################################
  #
  #  Catalog metadata methods
  #

  def setMetadata( self, path, metadataDict, credDict ):
    """ Add metadata to the given path
    """
    res = self._checkPathPermissions( 'Write', path, credDict )
    if not res['OK']:
      return res
    if not res['Value']['Successful']:
      return S_ERROR( 'Permission denied' )
    if not res['Value']['Successful'][path]:
      return S_ERROR( 'Permission denied' )

    result = self.dtree.isDirectory( {path:True} )
    if not result['OK']:
      return result
    if not result['Value']['Successful']:
      return S_ERROR( 'Failed to determine the path type' )
    if result['Value']['Successful'][path]:
      # This is a directory
      return self.dmeta.setMetadata( path, metadataDict, credDict )
    else:
      # This is a file
      return self.fmeta.setMetadata( path, metadataDict, credDict )

  def setMetadataBulk( self, pathMetadataDict, credDict ):
    """  Add metadata for the given paths
    """
    successful = {}
    failed = {}
    for path, metadataDict in pathMetadataDict.items():
      result = self.setMetadata( path, metadataDict, credDict )
      if result['OK']:
        successful[path] = True
      else:
        failed[path] = result['Message']

    return S_OK( { 'Successful': successful, 'Failed': failed } )

  def removeMetadata( self, pathMetadataDict, credDict ):
    """ Remove metadata for the given paths
    """
    successful = {}
    failed = {}
    for path, metadataDict in pathMetadataDict.items():
      result = self.__removeMetadata( path, metadataDict, credDict )
      if result['OK']:
        successful[path] = True
      else:
        failed[path] = result['Message']

    return S_OK( { 'Successful': successful, 'Failed': failed } )

  def __removeMetadata( self, path, metadata, credDict ):
    """ Remove metadata from the given path
    """
    res = self._checkPathPermissions( 'Write', path, credDict )
    if not res['OK']:
      return res
    if not res['Value']['Successful']:
      return S_ERROR( 'Permission denied' )
    if not res['Value']['Successful'][path]:
      return S_ERROR( 'Permission denied' )

    result = self.dtree.isDirectory( {path:True} )
    if not result['OK']:
      return result
    if not result['Value']['Successful']:
      return S_ERROR( 'Failed to determine the path type' )
    if result['Value']['Successful'][path]:
      # This is a directory
      return self.dmeta.removeMetadata( path, metadata, credDict )
    else:
      # This is a file
      return self.fmeta.removeMetadata( path, metadata, credDict )

  #######################################################################
  #
  #  Catalog admin methods
  #

  def getCatalogCounters( self, credDict ):
    counterDict = {}
    res = self._checkAdminPermission( credDict )
    if not res['OK']:
      return res
    if not res['Value']:
      return S_ERROR( "Permission denied" )
    # res = self.dtree.getDirectoryCounters()
    # if not res['OK']:
    #  return res
    # counterDict.update(res['Value'])
    res = self.fileManager.getFileCounters()
    if not res['OK']:
      return res
    counterDict.update( res['Value'] )
    res = self.fileManager.getReplicaCounters()
    if not res['OK']:
      return res
    counterDict.update( res['Value'] )
    res = self.dtree.getDirectoryCounters()
    if not res['OK']:
      return res
    counterDict.update( res['Value'] )
    return S_OK( counterDict )

  ########################################################################
  #
  #  Security based methods
  #

  def _checkAdminPermission( self, credDict ):
    return self.securityManager.hasAdminAccess( credDict )

  def _checkPathPermissions( self, operation, lfns, credDict ):
    res = checkArgumentFormat( lfns )
    if not res['OK']:
      return res
    lfns = res['Value']
    res = self.securityManager.hasAccess( operation, lfns.keys(), credDict )
    if not res['OK']:
      return res
    # Do not consider those paths for which we failed to determine access
    failed = res['Value']['Failed']
    for lfn in failed.keys():
      lfns.pop( lfn )
    # Do not consider those paths for which access is denied
    successful = {}
    for lfn, access in res['Value']['Successful'].items():
      if not access:
        failed[lfn] = 'Permission denied'
      else:
        successful[lfn] = lfns[lfn]
        
    return S_OK( {'Successful':successful, 'Failed':failed} )
  
