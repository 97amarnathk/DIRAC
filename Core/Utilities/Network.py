# $HeadURL$
__RCSID__ = "$Id$"
"""
   Collection of DIRAC useful network related modules
   by default on Error they return None

   getAllInterfaces and getAddressFromInterface do not work in MAC
"""
import socket
import struct
import array
import os
from DIRAC.Core.Utilities.ReturnValues import S_OK, S_ERROR

def discoverInterfaces():
  max_possible = 128
  bytes = max_possible * 32
  s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
  names = array.array( 'B', '\0' * bytes )
  #0x8912 SICGIFCONF
  fcntlOut = fcntl.ioctl( s.fileno(), 0x8912, struct.pack( 'iL', bytes, names.buffer_info()[0] ) )
  outbytes = struct.unpack( 'iL', fcntlOut )[0]
  namestr = names.tostring()
  ifaces = {}
  arch = platform.architecture()[0]
  if arch.find( '32' ) == 0:
    for i in range( 0, outbytes, 32 ):
      name = namestr[i:i + 32].split( '\0', 1 )[0]
      ip = namestr[i + 20:i + 24]
      ifaces[ name ] = { 'ip' : socket.inet_ntoa( ip ), 'mac' : getMACFromInterface( name ) }
  else:
    for i in range( 0, outbytes, 40 ):
      name = namestr[i:i + 16].split( '\0', 1 )[0]
      ip = namestr[i + 20:i + 24]
      ifaces[ name ] = { 'ip' : socket.inet_ntoa( ip ), 'mac' : getMACFromInterface( name ) }
  return ifaces

def getAllInterfaces():
  import fcntl
  max_possible = 128  # arbitrary. raise if needed.
  bytes = max_possible * 32
  s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
  names = array.array( 'B', '\0' * bytes )
  outbytes = struct.unpack( 
                            'iL',
                            fcntl.ioctl( 
                                         s.fileno(),
                                         0x8912, # SIOCGIFCONF
                                         struct.pack( 'iL',
                                                      bytes,
                                                      names.buffer_info()[0] )
                                       )
                          )[0]
  namestr = names.tostring()
  return [namestr[i:i + 32].split( '\0', 1 )[0] for i in range( 0, outbytes, 32 )]

def getAddressFromInterface( ifName ):
  import fcntl
  try:
    s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
    return socket.inet_ntoa( fcntl.ioctl( 
                                          s.fileno(),
                                          0x8915, # SIOCGIFADDR
                                          struct.pack( '256s', ifName[:15] )
                                        )[20:24] )
  except:
    return False

def getMACFromInterface( self, ifname ):
  s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
  info = fcntl.ioctl( s.fileno(), 0x8927, struct.pack( '256s', ifname[:15] ) )
  return ''.join( ['%02x:' % ord( char ) for char in info[18:24]] )[:-1]

def getFQDN():
  sFQDN = socket.getfqdn()
  if sFQDN.find( 'localhost' ) > -1:
    sFQDN = os.uname()[1]
    socket.getfqdn( sFQDN )
  return sFQDN

def splitURL( URL ):
  protocolEnd = URL.find( "://" )
  if protocolEnd == -1:
    return S_ERROR( "'%s' URL is malformed" % URL )
  protocol = URL[ : protocolEnd ]
  URL = URL[ protocolEnd + 3: ]
  pathStart = URL.find( "/" )
  if pathStart > -1:
    host = URL[ :pathStart ]
    path = URL[ pathStart + 1: ]
  else:
    host = URL
    path = "/"
  if path[-1] == "/":
    path = path[:-1]
  portStart = host.find( ":" )
  if portStart > -1:
    port = int( host[ portStart + 1: ] )
    host = host[ :portStart ]
  else:
    port = 0
  return S_OK( ( protocol, host, port, path ) )

def getIPsForHostName( hostName ):
  try:
    ips = [ t[4][0] for t in socket.getaddrinfo( hostName, 0 ) ]
  except Exception, e:
    return S_ERROR( "Can't get info for host %s: %s" % ( hostName, str( e ) ) )
  uniqueIPs = []
  for ip in ips:
    if ip not in uniqueIPs:
      uniqueIPs.append( ip )
  return S_OK( uniqueIPs )

def checkHostsMatch( host1, host2 ):
  ipLists = []
  for host in ( host1, host2 ):
    result = getIPsForHostName( host )
    if not result[ 'OK' ]:
      return result
    ipLists.append( result[ 'Value' ] )
  #Check
  for i in range( len( ipLists ) - 1 ):
    for ip in ipLists[i]:
      for ipl in ipLists[i + 1]:
        if ip in ipl:
          return S_OK( True )
  return S_OK( False )




