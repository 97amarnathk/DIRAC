# $HeadURL$
__RCSID__ = "$Id$"

from DIRAC.Core.Utilities import Network, List
from DIRAC.ConfigurationSystem.Client.ConfigurationData import gConfigurationData
from DIRAC.ConfigurationSystem.Client.PathFinder import getServiceSection, getSystemSection
from DIRAC.Core.DISET.private.Protocols import gDefaultProtocol

class ServiceConfiguration:

  def __init__( self, serviceName ):
    self.serviceName = serviceName
    self.serviceURL = False
    self.serviceSectionPath = getServiceSection( serviceName )
    self.systemSectionPath = getSystemSection( serviceName )

  def getOption( self, optionName ):
    if optionName[0] != "/":
      optionName = "%s/%s" % ( self.serviceSectionPath, optionName )
    return gConfigurationData.extractOptionFromCFG( optionName )

  def getAddress( self ):
    return ( "", self.getPort() )

  def getHandlerLocation( self ):
    return self.getOption( "HandlerPath" )

  def getName( self ):
    return self.serviceName

  def setURL( self, sURL ):
    self.serviceURL = sURL

  def getURL( self, URL = False ):
    optionValue = self.getOption( "URL" )
    if optionValue:
      return optionValue
    elif URL:
        return URL
    else:
        return self.serviceURL

  def registerAlsoAs( self ):
    optionValue = self.getOption( "RegisterAlsoAs" )
    if optionValue:
      return List.fromChar( optionValue )
    else:
      return []

  def getMaxThreads( self ):
    try:
      return int( self.getOption( "MaxThreads" ) )
    except:
      return 15

  def getMaxWaitingPetitions( self ):
    try:
      return int( self.getOption( "MaxWaitingPetitions" ) )
    except:
      return 500

  def getMaxThreadsPerFunction( self, funcName ):
    try:
      return int( self.getOption( "%sMaxThreads" % funcName ) )
    except:
      return 15

  def getPort( self ):
    try:
      return int( self.getOption( "Port" ) )
    except:
      return 9876

  def getProtocol( self ):
    optionValue = self.getOption( "Protocol" )
    if optionValue:
      return optionValue
    return gDefaultProtocol

  def getServicePath( self ):
    return self.serviceSectionPath

  def getSystemPath( self ):
    return self.systemSectionPath

  def getHostname( self ):
    hostname = self.getOption( "/DIRAC/Hostname" )
    if not hostname:
      return Network.getFQDN()
    return hostname
