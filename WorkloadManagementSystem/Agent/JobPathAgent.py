########################################################################
# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/WorkloadManagementSystem/Agent/JobPathAgent.py,v 1.18 2009/05/04 19:07:37 atsareg Exp $
# File :   JobPathAgent.py
# Author : Stuart Paterson
########################################################################

"""   The Job Path Agent determines the chain of Optimizing Agents that must
      work on the job prior to the scheduling decision.

      Initially this takes jobs in the received state and starts the jobs on the
      optimizer chain.  The next development will be to explicitly specify the
      path through the optimizers.

"""
__RCSID__ = "$Id: JobPathAgent.py,v 1.18 2009/05/04 19:07:37 atsareg Exp $"

from DIRAC.WorkloadManagementSystem.Agent.OptimizerModule  import OptimizerModule
from DIRAC.ConfigurationSystem.Client.Config               import gConfig
from DIRAC.Core.Utilities.ClassAd.ClassAdLight             import ClassAd
from DIRAC.Core.Utilities.ModuleFactory                    import ModuleFactory
from DIRAC.WorkloadManagementSystem.Client.JobDescription  import JobDescription
from DIRAC                                                 import S_OK, S_ERROR, List
import string,re

OPTIMIZER_NAME = 'JobPath'

class JobPathAgent(OptimizerModule):

  #############################################################################
  def initializeOptimizer(self):
    """Initialize specific parameters for JobPathAgent.
    """
    self.startingMajorStatus = "Received"
    self.startingMinorStatus = False
    #self.requiredJobInfo = "jdlOriginal"
    return S_OK()

  def beginExecution(self):

    self.basePath     = self.am_getOption( 'BasePath',  ['JobPath','JobSanity'] )
    self.inputData    = self.am_getOption( 'InputData', ['InputData','BKInputData'] )
    self.endPath      = self.am_getOption( 'EndPath',   ['JobScheduling','TaskQueue'] )
    self.voPlugin     = self.am_getOption( 'VOPlugin',  '' )

    return S_OK()

  def __syncJobDesc( self, jobId, jobDesc, classAd ):
    if not jobDesc.isDirty():
      return
    for op in jobDesc.getOptions():
      classAdJob.insertAttributeString( op, jobDesc.getVar( op ) )
    self.jobDB.setJobJDL( jobId, jobDesc.dumpDescriptionAsJDL() )

  #############################################################################
  def checkJob( self, job, classAdJob ):
    """This method controls the checking of the job.
    """
    jobDesc = JobDescription()
    result = jobDesc.loadDescription( classAdJob.asJDL() )
    if not result[ 'OK' ]:
      self.setFailedJob(job, result['Message'],classAdJob)
      return result
    self.__syncJobDesc( job, jobDesc, classAdJob )

    #Check if job defines a path itself
    # FIXME: only some group might be able to overwrite the jobPath
    jobPath = classAdJob.get_expression('JobPath').replace('"','').replace('Unknown','')
    #jobPath = jobDesc.getVarWithDefault( 'JobPath' ).replace( 'Unknown', '' )
    if jobPath:
      # HACK: Remove the { and } to ensure we have a simple string
      jobPath= jobPath.replace("{","").replace("}","")
      self.log.info('Job %s defines its own optimizer chain %s' % ( job, jobPath ) )
      return self.processJob( job, List.fromChar( jobPath ) )

    #If no path, construct based on JDL and VO path module if present
    path = list(self.basePath)
    if self.voPlugin:
      argumentsDict = {'JobID':job,'ClassAd':classAdJob,'ConfigPath':self.am_getModuleParam( "section" )}
      moduleFactory = ModuleFactory()
      moduleInstance = moduleFactory.getModule(self.voPlugin,argumentsDict)
      if not moduleInstance['OK']:
        self.log.error('Could not instantiate module:', '%s' %(self.voPlugin))
        self.setFailedJob(job, 'Could not instantiate module: %s' %(self.voPlugin),classAdJob)
        return S_ERROR('Holding pending jobs')

      module = moduleInstance['Value']
      result = module.execute()
      if not result['OK']:
        self.log.warn('Execution of %s failed' %(self.voPlugin))
        return result
      extraPath = List.fromChar(result['Value'])
      if extraPath:
        path.extend( extraPath )
        self.log.verbose('Adding extra VO specific optimizers to path: %s' %(extraPath))
    else:
      self.log.verbose('No VO specific plugin module specified')

    result = self.jobDB.getInputData(job)
    if not result['OK']:
      self.log.error('Failed to get input data from JobDB', job  )
      self.log.warn(result['Message'])
      return result

    if result['Value']:
      # if the returned tuple is not empty it will evaluate true
      self.log.info('Job %s has an input data requirement' % (job))
      path.extend( self.inputData )
    else:
      self.log.info('Job %s has no input data requirement' % (job))

    path.extend( self.endPath )
    self.log.info('Constructed path for job %s is: %s' %(job,path))
    return self.processJob( job, path )

  #############################################################################
  def processJob(self,job,chain):
    """Set job path and send to next optimizer
    """
    result = self.setOptimizerChain(job,chain)
    if not result['OK']:
      self.log.warn(result['Message'])
    result = self.setJobParam(job,'JobPath',string.join(chain,','))
    if not result['OK']:
      self.log.warn(result['Message'])
    return self.setNextOptimizer( job )

#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
