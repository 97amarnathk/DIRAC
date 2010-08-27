########################################################################
# $Id$
########################################################################

""" The TimeLeft utility allows to calculate the amount of CPU time
    left for a given batch system slot.  This is essential for the 'Filling
    Mode' where several VO jobs may be executed in the same allocated slot.

    The prerequisites for the utility to run are:
      - Plugin for extracting information from local batch system
      - Scale factor for the local site.

    With this information the utility can calculate in normalized units the
    CPU time remaining for a given slot.
"""

from DIRAC import gLogger, gConfig, S_OK, S_ERROR, rootPath
import DIRAC
__RCSID__ = "$Id$"

import os, re

class TimeLeft:

  #############################################################################
  def __init__( self ):
    """ Standard constructor
    """
    self.log = gLogger.getSubLogger( 'TimeLeft' )
    # FIXME: Why do we need to load any .cfg file here????
    self.__loadLocalCFGFiles()
    # This is the ratio SpecInt published by the site over 250 (the reference used for Matching)
    self.scaleFactor = gConfig.getValue( '/LocalSite/CPUScalingFactor', 0.0 )
    if not self.scaleFactor:
      self.log.warn( '/LocalSite/CPUScalingFactor not defined for site %s' % DIRAC.siteName() )
    self.cpuMargin = gConfig.getValue( '/LocalSite/CPUMargin', 10 ) #percent

  def getScaledCPU( self ):
    """Returns the current CPU Time spend (according to batch system) scaled according 
       to /LocalSite/CPUScalingFactor
    """
    #Quit if no scale factor available
    if not self.scaleFactor:
      return S_OK( 0.0 )

    #Work out which type of batch system to query and attempt to instantiate plugin
    result = self.__checkCurrentBatchSystem()
    if not result['OK']:
      return S_OK( 0.0 )
    name = result['Value']

    batchInstance = self.__getBatchSystemPlugin( name )
    if not batchInstance['OK']:
      return S_OK( 0.0 )

    batchSystem = batchInstance['Value']
    resourceDict = batchSystem.getResourceUsage()

    if 'Value' in resourceDict and resourceDict['Value']['CPU']:
      return S_OK( resourceDict['Value']['CPU'] * self.scaleFactor )

    return S_OK( 0.0 )

  #############################################################################
  def getTimeLeft( self, cpuConsumed ):
    """Returns the CPU Time Left for supported batch systems.  The CPUConsumed
       is the current raw total CPU.
    """
    #Quit if no scale factor available
    if not self.scaleFactor:
      return S_ERROR( '/LocalSite/CPUScalingFactor not defined for site %s' % DIRAC.siteName() )

    #Work out which type of batch system to query and attempt to instantiate plugin
    result = self.__checkCurrentBatchSystem()
    if not result['OK']:
      return result
    name = result['Value']

    batchInstance = self.__getBatchSystemPlugin( name )
    if not batchInstance['OK']:
      return batchInstance

    batchSystem = batchInstance['Value']
    resourceDict = batchSystem.getResourceUsage()
    if not resourceDict['OK']:
      self.log.warn( 'Could not determine timeleft for batch system %s at site %s' % ( name, DIRAC.siteName() ) )
      return resourceDict

    resources = resourceDict['Value']
    self.log.verbose( resources )
    if not resources['CPULimit'] or not resources['WallClockLimit']:
      return S_ERROR( 'No CPU / WallClock limits obtained' )

    cpuFactor = 100 * float( resources['CPU'] ) / float( resources['CPULimit'] )
    cpuRemaining = 100 - cpuFactor
    cpuLimit = float( resources['CPULimit'] )
    wcFactor = 100 * float( resources['WallClock'] ) / float( resources['WallClockLimit'] )
    wcRemaining = 100 - wcFactor
    wcLimit = float( resources['WallClockLimit'] )
    self.log.verbose( 'Used CPU is %.02f, Used WallClock is %.02f.' % ( cpuFactor, wcFactor ) )
    self.log.verbose( 'Remaining WallClock %.02f, Remaining CPU %.02f, margin %s' % ( wcRemaining, cpuRemaining, self.cpuMargin ) )

    timeLeft = None
    if wcRemaining > cpuRemaining and ( wcRemaining - cpuRemaining ) > self.cpuMargin:
      # In some cases cpuFactor might be 0
      # timeLeft = float(cpuConsumed*self.scaleFactor*cpuRemaining/cpuFactor)
      # We need time left in the same units used by the Matching
      timeLeft = float( cpuRemaining * cpuLimit / 100 * self.scaleFactor )
      self.log.verbose( 'Remaining WallClock %.02f > Remaining CPU %.02f and difference > margin %s' % ( wcRemaining, cpuRemaining, self.cpuMargin ) )
    else:
      if cpuRemaining > self.cpuMargin and wcRemaining > self.cpuMargin:
        self.log.verbose( 'Remaining WallClock %.02f and Remaining CPU %.02f both > margin %s' % ( wcRemaining, cpuRemaining, self.cpuMargin ) )
        # In some cases cpuFactor might be 0
        # timeLeft = float(cpuConsumed*self.scaleFactor*(wcRemaining-self.cpuMargin)/cpuFactor)
        timeLeft = float( cpuRemaining * cpuLimit / 100 * self.scaleFactor )
      else:
        self.log.verbose( 'Remaining CPU %.02f < margin %s and WallClock %.02f < margin %s so no time left' % ( cpuRemaining, self.cpuMargin, wcRemaining, self.cpuMargin ) )

    if timeLeft:
      self.log.verbose( 'Remaining CPU in normalized units is: %.02f' % timeLeft )
      return S_OK( timeLeft )
    else:
      return S_ERROR( 'No time left for slot' )

  #############################################################################
  def __loadLocalCFGFiles( self ):
    """Loads any extra CFG files residing in the local DIRAC site root.
    """
    files = os.listdir( rootPath )
    self.log.debug( 'Checking directory %s' % rootPath )
    for i in files:
      if re.search( '.cfg$', i ):
        gConfig.loadFile( '%s/%s' % ( rootPath, i ) )
        self.log.debug( 'Found local .cfg file %s' % i )

  #############################################################################
  def __getBatchSystemPlugin( self, name ):
    """Using the name of the batch system plugin, will return an instance
       of the plugin class.
    """
    self.log.debug( 'Creating plugin for %s batch system' % ( name ) )
    try:
      batchSystemName = "%sTimeLeft" % ( name )
      batchPlugin = __import__( 'DIRAC.Core.Utilities.TimeLeft.%s' % batchSystemName, globals(), locals(), [batchSystemName] )
    except Exception, x:
      msg = 'Could not import DIRAC.Core.Utilities.TimeLeft.%s' % ( batchSystemName )
      self.log.warn( x )
      self.log.warn( msg )
      return S_ERROR( msg )

    try:
      batchStr = 'batchPlugin.%s()' % ( batchSystemName )
      batchInstance = eval( batchStr )
    except Exception, x:
      msg = 'Could not instantiate %s()' % ( batchSystemName )
      self.log.warn( x )
      self.log.warn( msg )
      return S_ERROR( msg )

    return S_OK( batchInstance )

  #############################################################################
  def __checkCurrentBatchSystem( self ):
    """Based on the current environment, this utility will return the
       current batch system name.
    """
    batchSystems = {'LSF':'LSB_JOBID', 'PBS':'PBS_JOBID', 'BQS':'QSUB_REQNAME'} #more to be added later
    current = None
    for batchSystem, envVar in batchSystems.items():
      if os.environ.has_key( envVar ):
        current = batchSystem

    if current:
      return S_OK( current )
    else:
      self.log.warn( 'Batch system type for site %s is not currently supported' % DIRAC.siteName() )
      return S_ERROR( 'Currrent batch system is not supported' )

#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
