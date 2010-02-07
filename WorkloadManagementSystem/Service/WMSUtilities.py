########################################################################
# $HeadURL$
########################################################################

""" A set of utilities used in the WMS services
"""

__RCSID__ = "$Id$"

from tempfile import mkdtemp
import shutil, os
from DIRAC.Core.Utilities.Subprocess import systemCall
from DIRAC.FrameworkSystem.Client.ProxyManagerClient       import gProxyManager
from DIRAC.Core.Utilities.Grid import executeGridCommand

from DIRAC import S_OK, S_ERROR, gConfig

# List of files to be inserted/retrieved into/from pilot Output Sandbox
# first will be defined as StdOut in JDL and the second as StdErr
outputSandboxFiles = [ 'StdOut', 'StdErr', 'std.out', 'std.err' ]

COMMAND_TIMEOUT = 60
###########################################################################
def getPilotOutput( proxy, grid, pilotRef ):
  """
   Get Output of a GRID job
  """
  tmp_dir = mkdtemp()
  if grid == 'LCG':
    cmd = [ 'edg-job-get-output' ]
  elif grid == 'gLite':
    cmd = [ 'glite-wms-job-output' ]
  else:
    return S_ERROR( 'Unknown GRID %s' % grid  )

  cmd.extend( ['--noint','--dir', tmp_dir, pilotRef] )
  
  gridEnv = ''
  setup = gConfig.getValue('/DIRAC/Setup','')
  if setup:
    instance = gConfig.getValue('/DIRAC/Setups/%s/WorkloadManagement' % setup,'')
    if instance:
      gridEnv = gConfig.getValue('/Systems/WorkloadManagement/%s/GridEnv' % instance,'')
      
  ret = executeGridCommand( proxy, cmd, gridEnv )  
  if not ret['OK']:
    shutil.rmtree(tmp_dir)
    return ret

  status,output,error = ret['Value']
  if error.find('already retrieved') != -1:
    shutil.rmtree(tmp_dir)
    return S_ERROR('Pilot job output already retrieved')

  if error.find('Output not yet Ready') != -1 :
    shutil.rmtree(tmp_dir)
    return S_ERROR(error)

  if output.find('not yet ready') != -1 :
    shutil.rmtree(tmp_dir)
    return S_ERROR(output)

  if error.find('the status is ABORTED') != -1 :
    shutil.rmtree(tmp_dir)
    return S_ERROR(error)

  if status:
    shutil.rmtree(tmp_dir)
    return S_ERROR(error)

  # Get the list of files

  # LCG always creates an unique sub-directory
  # gLite does it too now
  tmp_dir = os.path.join(tmp_dir,os.listdir(tmp_dir)[0])

  result = S_OK()
  result['FileList'] = outputSandboxFiles

  for filename in outputSandboxFiles:
    tmpname = os.path.join( tmp_dir, filename )
    if os.path.exists(tmpname):
      myfile = file(tmpname,'r')
      f = myfile.read()
      myfile.close()
    else:
      f = ''
    # HACK: removed after the current scheme has been in production for at least 1 week
    if filename == 'std.out' and f: filename = 'StdOut'
    if filename == 'std.err' and f: filename = 'StdErr'
    result[filename] = f

  shutil.rmtree(tmp_dir)
  return result

###########################################################################
def getPilotLoggingInfo( proxy, grid, pilotRef ):
  """
   Get LoggingInfo of a GRID job
  """
  if grid == 'LCG':
    cmd = [ 'edg-job-get-logging-info', '-v', '2' ]
  elif grid == 'gLite':
    cmd = [ 'glite-wms-job-logging-info', '-v', '3' ]
  else:
    return S_ERROR( 'Unknnown GRID %s' % grid  )

  cmd.extend( ['--noint', pilotRef] )

  gridEnv = ''
  setup = gConfig.getValue('/DIRAC/Setup','')
  if setup:
    instance = gConfig.getValue('/DIRAC/Setups/%s/WorkloadManagement' % setup,'')
    if instance:
      gridEnv = gConfig.getValue('/Systems/WorkloadManagement/%s/GridEnv' % instance,'')
      
  ret = executeGridCommand( proxy, cmd, gridEnv )
  if not ret['OK']:
    return ret

  status,output,error = ret['Value']
  if status:
    return S_ERROR(error)

  return S_OK( output )


