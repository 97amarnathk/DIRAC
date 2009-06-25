# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/Core/Utilities/CFG.py,v 1.3 2009/06/25 14:59:19 acasajus Exp $
__RCSID__ = "$Id: CFG.py,v 1.3 2009/06/25 14:59:19 acasajus Exp $"

import types
import copy

from DIRAC.Core.Utilities import List, ThreadSafe

gCFGSynchro = ThreadSafe.Synchronizer( recursive = True )

class CFG:

  def __init__( self ):
    """
    Constructor
    """
    self.reset()

  @gCFGSynchro
  def reset( self ):
    """
    Empty the CFG
    """
    self.__orderedList = []
    self.__commentDict = {}
    self.__dataDict = {}

  @gCFGSynchro
  def createNewSection( self, sectionName, comment = "", contents = False ):
    """
    Create a new section

    @type sectionName: string
    @param sectionName: Name of the section
    @type comment: string
    @param comment: Comment for the section
    @type contents: CFG
    @param contents: Optional cfg with the contents of the section.
    """
    if sectionName == "":
      raise Exception( "Creating a section with empty name! You shouldn't do that!" )
    if sectionName.find( "/" ) > -1:
      recDict = self.getRecursive( sectionName, -1 )
      parentSection = recDict[ 'value' ]
      if type( parentSection ) in ( types.StringType, types.UnicodeType ):
        raise Exception( "Entry %s doesn't seem to be a section" % recDict[ 'key' ] )
      return parentSection.createNewSection( recDict[ 'levelsBelow' ], comment, contents )
    self.__addEntry( sectionName, comment )
    if sectionName not in self.__dataDict:
      if not contents:
        self.__dataDict[ sectionName ] = CFG()
      else:
        self.__dataDict[ sectionName ] = contents
    else:
      raise Exception( "%s key already exists"  % sectionName )
    return self.__dataDict[ sectionName ]

  def __overrideAndCloneSection( self, sectionName, oCFGToClone ):
    """
    Replace the contents of a section

    @type sectionName: string
    @params sectionName: Name of the section
    @type oCFGToClone: CFG
    @param oCFGToClone: CFG with the contents of the section
    """
    if sectionName not in self.listSections():
      raise Exception( "Section %s does not exist" % sectionName )
    self.__dataDict[ sectionName ] = oCFGToClone.clone()

  @gCFGSynchro
  def setOption( self, optionName, value, comment = "" ):
    """
    Create a new option.

    @type optionName: string
    @param optionName: Name of the option to create
    @type value: string
    @param value: Value of the option
    @type comment: string
    @param comment: Comment for the option
    """
    if optionName == "":
      raise Exception( "Creating an option with empty name! You shouldn't do that!" )
    if optionName.find( "/" ) > -1:
      recDict = self.getRecursive( optionName, -1 )
      parentSection = recDict[ 'value' ]
      if type( parentSection ) in ( types.StringType, types.UnicodeType ):
        raise Exception( "Entry %s doesn't seem to be a section" % recDict[ 'key' ] )
      return parentSection.setOption( recDict[ 'levelsBelow' ], value, comment )
    self.__addEntry( optionName, comment )
    self.__dataDict[ optionName ] = str( value )

  def __addEntry( self, entryName, comment ):
    """
    Add an entry and set the comment

    @type entryName: string
    @param entryName: Name of the entry
    @type comment: string
    @param comment: Comment for the entry
    """
    if not entryName in self.__orderedList:
      self.__orderedList.append( entryName )
    self.__commentDict[ entryName ] = comment

  def existsKey( self, key ):
    """
    Check if an option/section with that name exists

    @type key: string
    @param key: Name of the option/section to check
    @return: Boolean with the result
    """
    return key in self.__orderedList

  def sortAlphabetically( self, ascending = True ):
    """
    Order this cfg alphabetically
    returns true if modified
    """
    unordered = list( self.__orderedList )
    if ascending:
      self.__orderedList.sort()
    else:
      self.__orderedList.reverse()
    return unordered != self.__orderedList

  @gCFGSynchro
  def deleteKey( self, key ):
    """
    Delete an option/section

    @type key: string
    @param key: Name of the option/section to delete
    @return: Boolean with the result
    """
    if key in self.__orderedList:
      del( self.__commentDict[ key ] )
      del( self.__dataDict[ key ] )
      pos = self.__orderedList.index( key )
      del( self.__orderedList[ pos ] )
      return True
    return False

  @gCFGSynchro
  def copyKey( self, originalKey, newKey ):
    """
    Copy an option/section

    @type originalKey: string
    @param originalKey: Name of the option/section to copy
    @type newKey: string
    @param newKey: Destination name
    @return: Boolean with the result
    """
    if originalKey == newKey:
      return False
    if newKey in self.__orderedList:
      return False
    if originalKey in self.__orderedList:
      self.__dataDict[ newKey ] = copy.copy( self.__dataDict[ originalKey ] )
      self.__commentDict[ newKey ] = copy.copy( self.__commentDict[ originalKey ] )
      self.__orderedList.append( newKey )
      return True
    return False

  @gCFGSynchro
  def listOptions( self, ordered = False ):
    """
    List options

    @type ordered: boolean
    @param ordered: Return the options ordered. By default is False
    @return: List with the option names
    """
    if ordered:
      return [ sKey for sKey in self.__orderedList if type( self.__dataDict[ sKey ] ) == types.StringType ]
    else:
      return [ sKey for sKey in self.__dataDict.keys() if type( self.__dataDict[ sKey ] ) == types.StringType ]

  @gCFGSynchro
  def listSections( self, ordered = False ):
    """
    List subsections

    @type ordered: boolean
    @param ordered: Return the subsections ordered. By default is False
    @return: List with the subsection names
    """
    if ordered:
      return [ sKey for sKey in self.__orderedList if type( self.__dataDict[ sKey ] ) != types.StringType ]
    else:
      return [ sKey for sKey in self.__dataDict.keys() if type( self.__dataDict[ sKey ] ) != types.StringType ]

  @gCFGSynchro
  def isSection( self, key ):
    """
    Return if a section exists

    @type key: string
    @param key: Name to check
    @return: Boolean with the results
    """
    if key.find( "/" ) != -1:
      keyDict = self.getRecursive( key, -1 )
      if not keyDict:
        return False
      section = keyDict[ 'value' ]
      if type( section ) in ( types.StringType, types.UnicodeType ):
        return False
      secKey = keyDict[ 'levelsBelow' ]
      return section.isSection( secKey )
    return key in self.__dataDict and type( self.__dataDict[ key ] ) not in ( types.StringType, types.UnicodeType )

  @gCFGSynchro
  def isOption( self, key ):
    """
    Return if an option exists

    @type key: string
    @param key: Name to check
    @return: Boolean with the results
    """
    if key.find( "/" ) != -1:
      keyDict = self.getRecursive( key, -1 )
      if not keyDict:
        return False
      section = keyDict[ 'value' ]
      if type( section ) in ( types.StringType, types.UnicodeType ):
        return False
      secKey = keyDict[ 'levelsBelow' ]
      return section.isOption( secKey )
    return key in self.__dataDict and type( self.__dataDict[ key ] ) == types.StringType

  def listAll( self ):
    """
    List all sections and options

    @return: List with names of all options and subsections
    """
    return self.__orderedList

  def __recurse( self, pathList ):
    """
    Explore recursively a path

    @type pathList: list
    @param pathList: List containing the path to explore
    @return: Dictionary with the contents { key, value, comment }
    """
    if pathList[0] in self.__dataDict:
      if len( pathList ) == 1:
        return { 'key' : pathList[0], 'value' : self.__dataDict[ pathList[0] ], 'comment' : self.__commentDict[ pathList[0] ] }
      else:
        return self.__dataDict[ pathList[0] ].__recurse( pathList[1:] )
    else:
      return False

  @gCFGSynchro
  def getRecursive( self, path, levelsAbove = 0 ):
    """
    Get path contents

    @type path: string
    @param path: Path to explore recursively and get the contents
    @type levelsAbove: integer
    @param levelsAbove: Number of children levels in the path that won't be explored.
                        For instance, to explore all sections in a path except the last one use
                        levelsAbove = 1
    @return: Dictionary containing:
                key -> name of the entry
                value -> content of the key
                comment -> comment of the key
    """
    pathList = [ dir.strip() for dir in path.split( "/" ) if not dir.strip() == "" ]
    levelsAbove = abs( levelsAbove )
    if len( pathList ) - levelsAbove < 0:
      return False
    if len( pathList ) - levelsAbove == 0:
      return { 'key' : "", 'value' : self, 'comment' : "", 'levelsBelow' : "" }
    levelsBelow = ""
    if levelsAbove > 0:
      levelsBelow = "/".join( pathList[-levelsAbove:] )
      pathList = pathList[:-levelsAbove]
    retDict = self.__recurse( pathList )
    if not retDict:
      return False
    retDict[ 'levelsBelow' ] = levelsBelow
    return retDict

  def getOption( self, opName, defaultValue = None ):
    """
    Get option value with default applied

    @type opName: string
    @param opName: Path to the option to retrieve
    @type defaultValue: optional (any python type)
    @param defaultValue: Default value for the option if the option is not defined.
                         If the option is defined, the value will be returned casted to
                         the type of defaultValue if it is defined.
    @return: Value of the option casted to defaultValue type, or defaultValue
    """
    levels = List.fromChar( opName, "/" )
    dataD = self.__dataDict
    while len( levels ) > 1:
      try:
        dataD = dataD[ levels[0] ]
      except KeyError:
        return None
    try:
      optionValue = self.__dataDict[ opName ]
      if type( optionValue ) != types.StringType:
        optionValue = defaultValue
    except KeyError:
      optionValue = defaultValue

    #Return value if existing, defaultValue if not
    if optionValue == defaultValue:
      if defaultValue == None or type( defaultValue ) == types.TypeType:
        return None
      return optionValue

    #Value has been returned from the configuration
    if defaultValue == None:
      return optionValue

    #Casting to defaultValue's type
    defaultType = defaultValue
    if not type( defaultValue ) == types.TypeType:
      defaultType = type( defaultValue )

    if defaultType == types.ListType:
      try:
        return List.fromChar( optionValue, ',' )
      except Exception, v:
        return None
    elif defaultType == types.BooleanType:
      try:
        return optionValue.lower() in ( "y", "yes", "true", "1" )
      except Exception, v:
        return None
    else:
      try:
        return defaultType( optionValue )
      except:
        return None

  def getAsDict( self, path = "" ):
    """
    Get the contents below a give path as a dict

    @type secPath: string
    @param secPath: Path to retrieve as dict
    @return : Dictionary containing the data
    """
    resVal = {}
    if path:
      reqDict = self.getRecursive( path )
      if not reqDict:
        return resVal
      keyCfg = reqDict[ 'value' ]
      if type( keyCfg ) in ( types.StringType, types.UnicodeType ):
        return resVal
      return keyCfg.getAsDict()
    for op in self.listOptions():
      resVal[ op ] = self[ op ]
    for sec in self.listSections():
      resVal[ sec ] = self[ sec ].getAsDict()
    return resVal

  @gCFGSynchro
  def appendToOption( self, optionName, value ):
    """
    Append a value to an option prepending a comma

    @type optionName: string
    @param optionName: Name of the option to append the value
    @type value: string
    @param value: Value to append to the option
    """
    if optionName not in self.__dataDict:
      raise Exception( "Option %s has not been declared" % optionName )
    self.__dataDict[ optionName ] += str( value )

  @gCFGSynchro
  def addKey( self, key, value, comment, beforeKey = "" ):
    """
    Add a new entry (option or section)

    @type key: string
    @param key: Name of the option/section to add
    @type value: string/CFG
    @param value: Contents of the new option/section
    @type comment: string
    @param comment: Comment for the option/section
    @type beforeKey: string
    @param beforeKey: Name of the option/section to add the entry above. By default
                        the new entry will be added at the end.
    """
    if key in self.__dataDict:
      raise Exception( "%s already exists" % key )
    self.__dataDict[ key ] = value
    self.__commentDict[ key ] = comment
    if beforeKey == "":
      self.__orderedList.append( key )
    else:
      refKeyPos = self.__orderedList.index( beforeKey )
      print "RefKeyPos", refKeyPos
      self.__orderedList.insert( refKeyPos, key )

  @gCFGSynchro
  def renameKey( self, oldName, newName ):
    """
    Rename a option/section

    @type oldName: string
    @param oldName: Name of the option/section to change
    @type newName: string
    @param newName: New name of the option/section
    @return: Boolean with the result of the rename
    """
    if oldName == newName:
      return True
    if oldName in self.__dataDict:
      self.__dataDict[ newName ] = self.__dataDict[ oldName ]
      self.__commentDict[ newName ] = self.__commentDict[ oldName ]
      refKeyPos = self.__orderedList.index( oldName )
      self.__orderedList[ refKeyPos ] = newName
      del( self.__dataDict[ oldName ] )
      del( self.__commentDict[ oldName ] )
      return True
    else:
      return False

  def __getitem__( self, key ):
    """
    Get the contents of a section/option

    @type key: string
    @param key: Name of the section/option to retrieve
    @return: String/CFG with the contents
    """
    if key.find( "/" ) > -1:
      subDict = self.getRecursive( key )
      if not subDict:
        return False
      return subDict[ 'value' ]
    return self.__dataDict[ key ]

  def __iter__( self ):
    """
    Iterate though the contents in order
    """
    for key in self.__orderedList:
      yield key

  def __contains__( self, key ):
    """
    Check if a key is defined
    """
    return key in self.__orderedList

  def __str__( self ):
    """
    Get a print friendly representation of the CFG

    @return: String with the contents of the CFG
    """
    return self.serialize()

  def __repr__( self ):
    """
    Get a print friendly representation of the CFG

    @return: String with the contents of the CFG
    """
    return self.serialize()

  def __nonzero__( self ):
    """
    CFGs are not zeroes! ;)
    """
    return True

  def __eq__( self, cfg ):
    """
    Check CFGs
    """
    if not self.__orderedList == cfg.__orderedList:
      return False
    for key in self.__orderedList:
      if not self.__commentDict[ key ] == cfg.__commentDict[ key ]:
        return False
      if not self.__dataDict[ key ] == cfg.__dataDict[ key ]:
        return False
    return True

  @gCFGSynchro
  def getComment( self, entryName ):
    """
    Get the comment for an option/section

    @type entryName: string
    @param entryName: Name of the option/section
    @return: String with the comment
    """
    try:
      return self.__commentDict[ entryName ]
    except:
      raise Exception( "%s does not have any comment defined" % entryName )

  @gCFGSynchro
  def setComment( self, entryName, comment ):
    """
    Set the comment for an option/section

    @type entryName: string
    @param entryName: Name of the option/section
    @type comment: string
    @param comment: Comment for the option/section
    """
    if entryName in self.__orderedList:
      self.__commentDict[ entryName ] = comment
      return True
    return False

  @gCFGSynchro
  def serialize( self, tabLevelString = "" ):
    """
    Generate a human readable serialization of a CFG

    @type tabLevelString: string
    @param tabLevelString: Tab string to apply to entries before representing them
    @return: String with the contents of the CFG
    """
    indentation = "  "
    CFGSTring = ""
    for entryName in self.__orderedList:
      if entryName in self.__commentDict:
        for commentLine in List.fromChar( self.__commentDict[ entryName ], "\n" ):
          CFGSTring += "%s#%s\n" % ( tabLevelString, commentLine )
      if entryName in self.listSections():
        CFGSTring += "%s%s\n%s{\n" % ( tabLevelString, entryName, tabLevelString )
        CFGSTring += self.__dataDict[ entryName ].serialize( "%s%s" % ( tabLevelString, indentation ) )
        CFGSTring += "%s}\n" % tabLevelString
      elif entryName in self.listOptions():
        valueList = List.fromChar( self.__dataDict[ entryName ] )
        if len( valueList ) == 0:
          CFGSTring += "%s%s = \n" % ( tabLevelString, entryName )
        else:
          CFGSTring += "%s%s = %s\n" % ( tabLevelString, entryName, valueList[0] )
          for value in valueList[1:]:
            CFGSTring += "%s%s += %s\n" % ( tabLevelString, entryName, value )
      else:
        raise Exception( "Oops. There is an entry in the order which is not a section nor an option" )
    return CFGSTring

  @gCFGSynchro
  def clone( self ):
    """
    Create a copy of the CFG

    @return: CFG copy
    """
    clonedCFG = CFG()
    clonedCFG.__orderedList = copy.deepcopy( self.__orderedList )
    clonedCFG.__commentDict = copy.deepcopy( self.__commentDict )
    for option in self.listOptions():
      clonedCFG.__dataDict[ option ] = self[ option ]
    for section in self.listSections():
      clonedCFG.__dataDict[ section ] = self[ section ].clone()
    return clonedCFG

  @gCFGSynchro
  def mergeWith( self, cfgToMergeWith ):
    """
    Generate a CFG by merging with the contents of another CFG.

    @type cfgToMergeWith: CFG
    @param cfgToMergeWith: CFG with the contents to merge with. This contents are more
                            preemtive than this CFG ones
    @return: CFG with the result of the merge
    """
    mergedCFG = CFG()
    for option in self.listOptions():
      mergedCFG.setOption( option,
                           self[ option ],
                           self.getComment( option ) )
    for option in cfgToMergeWith.listOptions():
      mergedCFG.setOption( option,
                           cfgToMergeWith[ option ],
                           cfgToMergeWith.getComment( option ) )
    for section in self.listSections():
      if section in cfgToMergeWith.listSections():
        oSectionCFG = self[ section ].mergeWith( cfgToMergeWith[ section ] )
        mergedCFG.createNewSection( section,
                                    cfgToMergeWith.getComment( section ),
                                    oSectionCFG )
      else:
        mergedCFG.createNewSection( section,
                                    self.getComment( section ),
                                    self[ section ].clone() )
    for section in cfgToMergeWith.listSections():
      if section not in self.listSections():
        mergedCFG.createNewSection( section,
                                    cfgToMergeWith.getComment( section ),
                                    cfgToMergeWith[ section ] )
    return mergedCFG

  #Functions to load a CFG
  def loadFromFile( self, fileName ):
    """
    Load the contents of the CFG from a file

    @type fileName: string
    @param fileName: File name to load the contents from
    @return: This CFG
    """
    fd = file( fileName )
    fileData = fd.read()
    fd.close()
    return self.loadFromBuffer( fileData )

  @gCFGSynchro
  def loadFromBuffer( self, data ):
    """
    Load the contents of the CFG from a string

    @type data: string
    @param data: Contents of the CFG
    @return: This CFG
    """
    self.reset()
    levelList = []
    currentLevel = self
    currentlyParsedString = ""
    currentComment = ""
    for line in data.split( "\n" ):
      line = line.strip()
      if len( line ) < 1:
        continue
      commentPos = line.find( "#" )
      if commentPos > -1:
        currentComment += "%s\n" % line[ commentPos: ].replace( "#", "" )
        line = line[ :commentPos ]
      for index in range( len( line ) ):
        if line[ index ] == "{":
          currentlyParsedString = currentlyParsedString.strip()
          currentLevel.createNewSection( currentlyParsedString, currentComment )
          levelList.append( currentLevel )
          currentLevel = currentLevel[ currentlyParsedString ]
          currentlyParsedString = ""
          currentComment = ""
        elif line[ index ] == "}":
          currentLevel = levelList.pop()
        elif line[ index ] == "=":
          lFields = line.split( "=" )
          currentLevel.setOption( lFields[0].strip(),
           "=".join( lFields[1:] ).strip(),
           currentComment )
          currentlyParsedString = ""
          currentComment = ""
          break
        elif line[ index: index + 2 ] == "+=":
          valueList = line.split( "+=" )
          currentLevel.appendToOption( valueList[0].strip(), ", %s" % "+=".join( valueList[1:] ).strip() )
          currentlyParsedString = ""
          currentComment = ""
          break
        else:
          currentlyParsedString += line[ index ]
    return self

  def writeToFile( self, fileName ):
    """
    Write the contents of the cfg to file

    @type fileName: string
    @param fileName: Name of the file to write the cfg to
    @return: True/False
    """
    try:
      fd = file( fileName, "w" )
      fd.write( str( self ) )
      fd.close()
      return True
    except:
      return False




