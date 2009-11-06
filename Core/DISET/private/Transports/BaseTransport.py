# $HeadURL$
__RCSID__ = "$Id$"

from DIRAC.Core.Utilities.ReturnValues import S_ERROR, S_OK
from DIRAC.Core.Utilities import DEncode
from DIRAC.FrameworkSystem.Client.Logger import gLogger
import select

class BaseTransport:

  bAllowReuseAddress = True
  iListenQueueSize = 5
  iReadTimeout = 600

  def __init__( self, stServerAddress, bServerMode = False, **kwargs ):
    self.bServerMode = bServerMode
    self.extraArgsDict = kwargs
    self.byteStream = ""
    self.packetSize = 1048576 #1MiB
    self.stServerAddress = stServerAddress
    self.peerCredentials = {}
    self.remoteAddress = False
    self.appData = ""

  def handshake(self):
    pass

  def setAppData( self, appData ):
    self.appData = appData

  def getAppData( self ):
    return self.appData

  def getConnectingCredentials( self ):
    return self.peerCredentials

  def setExtraCredentials( self, group ):
    self.peerCredentials[ 'extraCredentials' ] = group

  def serverMode( self ):
    return self.bServerMode

  def getTransportName( self ):
    return self.sTransportName

  def getRemoteAddress( self ):
    return self.remoteAddress

  def getLocalAddress( self ):
    return self.oSocket.getsockname()

  def getSocket( self ):
    return self.oSocket

  def _write( self, sBuffer ):
    self.oSocket.send( sBuffer )

  def _readReady( self ):
    if not self.iReadTimeout:
      return True
    inList, dummy, dummy = select.select( [ self.oSocket ], [], [], self.iReadTimeout )
    if self.oSocket in inList:
      return True
    return False

  def _read( self, bufSize = 4096, skipReadyCheck = False ):
    try:
      if skipReadyCheck or self._readReady():
        data = self.oSocket.recv( bufSize )
        if not data:
          return S_ERROR( "Connection closed by peer" )
        else:
          return S_OK( data )
      else:
        return S_ERROR( "Connection seems stalled. Closing..." )
    except Exception, e:
      return S_ERROR( "Exception while reading from peer: %s" % str( e ) )

  def _write( self, buffer ):
    return S_OK( self.oSocket.send( buffer ) )

  def sendData( self, uData ):
    sCodedData = DEncode.encode( uData )
    dataToSend = "%s:%s" % ( len( sCodedData ), sCodedData )
    for index in range( 0, len( dataToSend ), self.packetSize ):
      bytesToSend = len( dataToSend[ index : index + self.packetSize ] )
      packSentBytes = 0
      while packSentBytes < bytesToSend:
        try:
          result = self._write( dataToSend[ index + packSentBytes : index + bytesToSend ] )
          if not result[ 'OK' ]:
            return result
          sentBytes = result[ 'Value' ]
        except Exception, e:
          return S_ERROR( "Exception while sending data: %s" % e)
        if sentBytes == 0:
          return S_ERROR( "Connection closed by peer" )
        packSentBytes += sentBytes
    return S_OK()


  def receiveData( self, maxBufferSize = 0 ):
    if maxBufferSize < 0:
      maxBufferSize = 0
    try:
      iSeparatorPosition = self.byteStream.find( ":" )
      while iSeparatorPosition == -1:
        retVal = self._read( 1024 )
        if not retVal[ 'OK' ]:
          return retVal
        if not retVal[ 'Value' ]:
          return S_ERROR( "Peer closed connection" )
        self.byteStream += retVal[ 'Value' ]
        iSeparatorPosition = self.byteStream.find( ":" )
        if maxBufferSize and len( self.byteStream ) > maxBufferSize and iSeparatorPosition == -1 :
          return S_ERROR( "Read limit exceeded (%s chars)" % maxBufferSize )
      size = int( self.byteStream[ :iSeparatorPosition ] )
      self.byteStream = self.byteStream[ iSeparatorPosition+1: ]
      while len( self.byteStream ) < size:
        retVal = self._read( size - len( self.byteStream ), skipReadyCheck = True )
        if not retVal[ 'OK' ]:
          return retVal
        if not retVal[ 'Value' ]:
          return S_ERROR( "Peer closed connection" )
        self.byteStream += retVal[ 'Value' ]
        if maxBufferSize and len( self.byteStream ) > maxBufferSize:
          return S_ERROR( "Read limit exceeded (%s chars)" % maxBufferSize )
      data = self.byteStream[ :size ]
      self.byteStream = self.byteStream[ size: ]
      return DEncode.decode( data )[0]
    except Exception, e:
      gLogger.exception( "Network error while receiving data" )
      return S_ERROR( "Network error while receiving data: %s" % str( e ) )

