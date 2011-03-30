########################################################################
# $HeadURL$
# File :   JobSchedulingAgent.py
# Author : Stuart Paterson
########################################################################

"""   The Job Scheduling Agent takes the information gained from all previous
      optimizers and makes a scheduling decision for the jobs.  Subsequent to this
      jobs are added into a Task Queue by the next optimizer and pilot agents can
      be submitted.

      All issues preventing the successful resolution of a site candidate are discovered
      here where all information is available.  This Agent will fail affected jobs
      meaningfully.

"""
__RCSID__ = "$Id$"

from DIRAC.WorkloadManagementSystem.Agent.OptimizerModule      import OptimizerModule
from DIRAC.Core.Utilities.ClassAd.ClassAdLight                 import ClassAd
from DIRAC.Core.Utilities.SiteSEMapping                        import getSEsForSite
from DIRAC.Core.Utilities.Time                                 import fromString, toEpoch
from DIRAC.StorageManagementSystem.Client.StorageManagerClient import StorageManagerClient
from DIRAC                                                     import S_OK, S_ERROR, List

import random, re

class JobSchedulingAgent( OptimizerModule ):
  """
      The specific Optimizer must provide the following methods:
      - checkJob() - the main method called for each job
      and it can provide:
      - initializeOptimizer() before each execution cycle
  """

  #############################################################################
  def initializeOptimizer( self ):
    """ Initialization of the Agent.
    """

    self.dataAgentName = self.am_getOption( 'InputDataAgent', 'InputData' )
    self.stagingStatus = self.am_getOption( 'StagingStatus', 'Staging' )
    self.stagingMinorStatus = self.am_getOption( 'StagingMinorStatus', 'Request Sent' )
    delays = self.am_getOption( 'RescheduleDelays', [60, 180, 300, 600] )
    self.rescheduleDelaysList = [ int( x ) for x in delays ]
    self.maxRescheduleDelay = self.rescheduleDelaysList[-1]
    self.excludedOnHoldJobTypes = self.am_getOption( 'ExcludedOnHoldJobTypes', [] )

    return S_OK()

  #############################################################################
  def checkJob( self, job, classAdJob ):
    """This method controls the checking of the job.
    """
    self.log.verbose( 'Job %s will be processed' % ( job ) )

    # Check if the job was recently rescheduled
    result = self.jobDB.getJobAttributes( job, ['RescheduleCounter', 'RescheduleTime', 'ApplicationStatus'] )
    if not result['OK']:
      self.log.error( result['Message'] )
      return S_ERROR( 'Can not get job attributes from JobDB' )
    jobDict = result['Value']
    reCounter = int( jobDict['RescheduleCounter'] )
    if reCounter != 0 :
      reTime = fromString( jobDict['RescheduleTime'] )
      delta = toEpoch() - toEpoch( reTime )
      delay = self.maxRescheduleDelay
      if reCounter <= len( self.rescheduleDelaysList ):
        delay = self.rescheduleDelaysList[reCounter - 1]
      if delta < delay:
        if jobDict['ApplicationStatus'].find( 'On Hold: after rescheduling' ) == -1:
          result = self.jobDB.setJobStatus( job, application = 'On Hold: after rescheduling #%d' % reCounter )
        return S_OK()

    # First, get Site and BannedSites from the Job

    result = self.__getJobSiteRequirement( job, classAdJob )
    userBannedSites = result['BannedSites']
    userSites = result['Sites']

    if userSites:
      userSites = applySiteRequirements( userSites, [], userBannedSites )
      if not userSites:
        msg = 'Impossible Site Requirement'
        return S_ERROR( msg )

    # Second, get the Active and Banned sites from the WMS

    wmsSites = self.jobDB.getSiteMask( 'Active' )
    wmsBannedSites = self.jobDB.getSiteMask( 'Banned' )
    if not ( wmsSites['OK'] and wmsBannedSites['OK'] ):
      if not wmsSites['OK']:
        self.log.error( wmsSites['Message'] )
      if not wmsBannedSites['OK']:
        self.log.error( wmsBannedSites['Message'] )
      return S_ERROR( 'Can not get Active and Banned Sites from JobDB' )

    wmsSites = wmsSites['Value']
    wmsBannedSites = wmsBannedSites['Value']

    if userSites:
      sites = applySiteRequirements( userSites, wmsSites, wmsBannedSites )
      if not sites:
        # Put on Hold only non-excluded job types
        jobType = classAdJob.getAttributeString( 'JobType' )
        if not jobType in self.excludedOnHoldJobTypes:
          msg = 'On Hold: Requested site is Banned or not Active'
          self.log.info( msg )
          result = self.jobDB.setJobStatus( job, application = msg )
          return S_OK()


    # Third, check if there is input data
    result = self.jobDB.getInputData( job )
    if not result['OK']:
      self.log.warn( 'Failed to get input data from JobDB for %s' % ( job ) )
      self.log.error( result['Message'] )
      return S_ERROR( 'Failed to get input data from JobDB' )

    if not result['Value']:
      return self.__sendJobToTaskQueue( job, classAdJob, userSites, userBannedSites )

    hasInputData = False
    for i in result['Value']:
      if i:
        hasInputData = True

    if not hasInputData:
      #With no input data requirement, job can proceed directly to task queue
      self.log.verbose( 'Job %s has no input data requirement' % ( job ) )
      return self.__sendJobToTaskQueue( job, classAdJob, userSites, userBannedSites )

    self.log.verbose( 'Job %s has an input data requirement ' % ( job ) )

    # Fourth, Check all optimizer information
    result = self.__checkOptimizerInfo( job )
    if not result['OK']:
      return result

    optInfo = result['Value']

    #Compare site candidates with current mask
    optSites = optInfo['SiteCandidates'].keys()
    self.log.info( 'Input Data Site Candidates: %s' % ( ', '.join( optSites ) ) )
    # Check that it is compatible with user requirements
    optSites = applySiteRequirements( optSites, userSites, userBannedSites )
    if not optSites:
      msg = 'Impossible Site + InputData Requirement'
      return S_ERROR( msg )

    sites = applySiteRequirements( optSites, wmsSites, wmsBannedSites )
    if not sites:
      msg = 'On Hold: InputData Site is Banned or not Active'
      self.log.info( msg )
      result = self.jobDB.setJobStatus( job, application = msg )
      return S_OK()

    #Set stager request as necessary, optimize for smallest #files on tape if
    #more than one site candidate left at this point
    checkStaging = self.__resolveSitesForStaging( job, sites, optInfo['SiteCandidates'] )
    if not checkStaging['OK']:
      return checkStaging

    destinationSites = checkStaging['SiteCandidates']
    if not destinationSites:
      return S_ERROR( 'No destination sites available' )

    stagingFlag = checkStaging['Value']
    if stagingFlag:
      #Single site candidate chosen and staging required
      self.log.verbose( 'Job %s requires staging of input data' % ( job ) )
      # set all LFN to disk for the selected site
      stagingSite = destinationSites[0]
      siteDict = optInfo['SiteCandidates'][stagingSite]
      siteDict['disk'] = siteDict['disk'] + siteDict['tape']
      siteDict['tape'] = 0

      optInfo['SiteCandidates'][stagingSite] = siteDict
      result = self.setOptimizerJobInfo( job, self.dataAgentName, optInfo )
      if not result['OK']:
        return result

      # Site is selected for staging, report it
      self.log.verbose( 'Staging site candidate for job %s is %s' % ( job, stagingSite ) )
      self.jobDB.setJobAttribute( job, 'Site', stagingSite )

      stagerDict = self.__setStagingRequest( job, stagingSite, optInfo )
      if not stagerDict['OK']:
        return stagerDict
      return S_OK()
    else:
      #No staging required, can proceed to task queue agent and then waiting status
      self.log.verbose( 'Job %s does not require staging of input data' % ( job ) )
    #Finally send job to TaskQueueAgent
    return self.__sendJobToTaskQueue( job, classAdJob, destinationSites, userBannedSites )


  #############################################################################
  def __checkOptimizerInfo( self, job ):
    """This method aggregates information from optimizers to return a list of
       site candidates and all information regarding input data.
    """
    #Check input data agent result and limit site candidates accordingly
    dataResult = self.getOptimizerJobInfo( job, self.dataAgentName )
    if dataResult['OK'] and len( dataResult['Value'] ):
      self.log.verbose( dataResult )
      if 'SiteCandidates' in dataResult['Value']:
        return S_OK( dataResult['Value'] )

      msg = 'No possible site candidates'
      self.log.info( msg )
      return S_ERROR( msg )

    msg = 'File Catalog Access Failure'
    self.log.info( msg )
    return S_ERROR( msg )

  #############################################################################
  def __resolveSitesForStaging( self, job, siteCandidates, inputDataDict ):
    """Site candidates are resolved from potential candidates and any job site
       requirement is compared at this point.
    """
    self.log.verbose( inputDataDict )
    finalSiteCandidates = []
    tapeCount = 0
    diskCount = 0
    tapeList = []
    stagingFlag = 0
    numberOfCandidates = len( siteCandidates )
    self.log.verbose( 'Job %s has %s candidate sites' % ( job, numberOfCandidates ) )
    for site in siteCandidates:
      disk = inputDataDict[site]['disk']
      if not disk:
        tape = inputDataDict[site]['tape']
        tapeList.append( tape )
        if tape > 0:
          self.log.verbose( '%s replicas on tape storage for %s' % ( tape, site ) )
          tapeCount += 1
      else:
        diskCount += 1

    if diskCount:
      if not tapeCount:
        self.log.verbose( 'All replicas on disk, no staging required' )
      else:
        self.log.verbose( 'Some replicas on disk for some candidate sites, restricting to those, no staging required' )
      for site in siteCandidates:
        if inputDataDict[site]['disk']:
          finalSiteCandidates.append( site )

    elif tapeCount >= numberOfCandidates:
      self.log.verbose( 'Staging is required for job' )
      tapeList.sort()
      minTapeValue = tapeList[0]
      minTapeSites = []
      for site in siteCandidates:
        if inputDataDict[site]['tape'] == minTapeValue:
          minTapeSites.append( site )

      if not minTapeSites:
        return S_ERROR( 'No possible site candidates' )

      if len( minTapeSites ) > 1:
        self.log.verbose( 'The following sites have %s tape replicas: %s' % ( minTapeValue, minTapeSites ) )
        random.shuffle( minTapeSites )
        randomSite = minTapeSites[0]
        finalSiteCandidates.append( randomSite )
        self.log.verbose( 'Site %s has been randomly chosen for job' % ( randomSite ) )
        stagingFlag = 1
      else:
        self.log.verbose( '%s is the site with smallest number of tape replicas (=%s)' %
                          ( minTapeSites[0], minTapeValue ) )
        finalSiteCandidates.append( minTapeSites[0] )
        stagingFlag = 1

    result = S_OK( stagingFlag )

    result['SiteCandidates'] = finalSiteCandidates

    return result

  #############################################################################
  def __setStagingRequest( self, job, destination, inputDataDict ):
    """A Staging request is formulated and saved as a job optimizer parameter.
    """

    self.log.verbose( 'Destination site %s' % ( destination ) )
    self.log.verbose( 'Input Data: %s' % ( inputDataDict ) )

    destinationSEs = getSEsForSite( destination )
    if not destinationSEs['OK']:
      return S_ERROR( 'Could not determine SEs for site %s' % destination )
    destinationSEs = destinationSEs['Value']

    #Ensure only tape SE files are staged
    tapeSEs = self.am_getOption( 'TapeSE', '-tape,-RDST,-RAW' )
    if type( tapeSEs ) == type( ' ' ):
      tapeSEs = [ x.strip() for x in tapeSEs.split( ',' ) ]

    siteTapeSEs = []
    for se in destinationSEs:
      for tapeSE in tapeSEs:
        if re.search( '%s$' % tapeSE, se ):
          siteTapeSEs.append( se )

    destinationSEs = siteTapeSEs
    if not destinationSEs:
      return S_ERROR( 'No LocalSEs For Site' )

    self.log.verbose( 'Site tape SEs: %s' % ( ', '.join( destinationSEs ) ) )
    stageSURLs = {} # OLD WAY
    stageLfns = {} # NEW WAY
    inputData = inputDataDict['Value']['Value']['Successful']
    for lfn, reps in inputData.items():
      for se, surl in reps.items():
        for destSE in destinationSEs:
          if se == destSE:
            if not lfn in stageSURLs.keys():
              stageSURLs[lfn] = {}
              stageSURLs[lfn].update( {se:surl} )
              if not stageLfns.has_key( se ): # NEW WAY
                stageLfns[se] = []          # NEW WAY
              stageLfns[se].append( lfn )     # NEW WAY

    stagerClient = StorageManagerClient()
    request = stagerClient.setRequest( stageLfns, 'WorkloadManagement',
                                       'updateJobFromStager@WorkloadManagement/JobStateUpdate', job )
    if request['OK']:
      self.jobDB.setJobParameter( int( job ), 'StageRequest', str( request['Value'] ) )

    if not request['OK']:
      self.log.error( 'Problem sending Staging request:' )
      self.log.error( request )
      return S_ERROR( 'Error Sending Staging Request' )
    else:
      self.log.info( 'Staging request successfully sent' )

    result = self.updateJobStatus( job, self.stagingStatus, self.stagingMinorStatus )
    if not result['OK']:
      return result
    return S_OK()

  #############################################################################
  def __getJobSiteRequirement( self, job, classAdJob ):
    """Returns any candidate sites specified by the job or sites that have been
       banned and could affect the scheduling decision.
    """

    result = self.jobDB.getJobAttribute( job, 'Site' )
    if not result['OK']:
      site = []
    else:
      site = List.fromChar( result['Value'] )

    result = S_OK()

    bannedSites = classAdJob.getAttributeString( 'BannedSites' )
    bannedSites = bannedSites.replace( '{', '' ).replace( '}', '' )
    bannedSites = List.fromChar( bannedSites )

    if not 'ANY' in site and not 'Unknown' in site and not 'Multiple' in site:
      if len( site ) == 1:
        self.log.info( 'Job %s has single chosen site %s specified in JDL' % ( job, site[0] ) )
      result['Sites'] = site
    elif 'Multiple' in site:
      result['Sites'] = classAdJob.getListFromExpression( 'Site' )
    else:
      result['Sites'] = []

    if bannedSites:
      self.log.info( 'Job %s has JDL requirement to ban %s' % ( job, bannedSites ) )
      result['BannedSites'] = bannedSites
    else:
      result['BannedSites'] = []

    return result

  #############################################################################
  def __checkSitesInMask( self, job, siteCandidates ):
    """Returns list of site candidates that are in current mask.
    """

    result = self.jobDB.getSiteMask()
    if not result['OK']:
      return S_ERROR( 'Could not get site mask' )

    sites = []
    allowedSites = result['Value']
    for candidate in siteCandidates:
      if not candidate in allowedSites:
        self.log.verbose( '%s is a candidate site for job %s but not in mask' % ( candidate, job ) )
      else:
        sites.append( candidate )

    self.log.info( 'Candidate sites in Mask are %s' % ( sites ) )

    return S_OK( sites )

  #############################################################################
  def __sendJobToTaskQueue( self, job, classAdJob, siteCandidates, bannedSites ):
    """This method sends jobs to the task queue agent and if candidate sites
       are defined, updates job JDL accordingly.
    """

    reqJDL = classAdJob.get_expression( 'JobRequirements' )
    classAddReq = ClassAd( reqJDL )

    if siteCandidates:
      classAddReq.insertAttributeVectorString( 'Sites', siteCandidates )
    if bannedSites:
      classAddReq.insertAttributeVectorString( 'BannedSites', bannedSites )

    if classAdJob.lookupAttribute( "SubmitPools" ):
      classAddReq.set_expression( 'SubmitPools', classAdJob.get_expression( 'SubmitPools' ) )

    if classAdJob.lookupAttribute( "GridMiddleware" ):
      classAddReq.set_expression( 'GridMiddleware', classAdJob.get_expression( 'GridMiddleware' ) )

    if classAdJob.lookupAttribute( "PilotTypes" ):
      classAddReq.set_expression( 'PilotTypes', classAdJob.get_expression( 'PilotTypes' ) )
    #HAck to migrate old jobs to new ones.
    #DELETE ON 08/09
    else:
      if classAdJob.lookupAttribute( "PilotType" ):
        classAddReq.set_expression( 'PilotTypes', classAdJob.get_expression( 'PilotType' ) )

    if classAdJob.lookupAttribute( "JobType" ):
      jobTypes = [ jt for jt in classAdJob.getListFromExpression( 'JobType' ) if jt ]
      classAddReq.insertAttributeVectorString( 'JobTypes', jobTypes )

    #Required CE's requirements
    gridCEs = [ ce for ce in classAdJob.getListFromExpression( 'GridRequiredCEs' ) if ce ]
    if gridCEs:
      classAddReq.insertAttributeVectorString( 'GridCEs', gridCEs )

    if siteCandidates:
      sites = ','.join( siteCandidates )
      classAdJob.insertAttributeString( "Site", sites )

    reqJDL = classAddReq.asJDL()
    classAdJob.insertAttributeInt( 'JobRequirements', reqJDL )

    jdl = classAdJob.asJDL()
    result = self.jobDB.setJobJDL( job, jdl )
    if not result['OK']:
      return result

    if siteCandidates:
      if len( siteCandidates ) == 1:
        self.log.verbose( 'Individual site candidate for job %s is %s' % ( job, siteCandidates[0] ) )
        self.jobDB.setJobAttribute( job, 'Site', siteCandidates[0] )
      elif bannedSites:
        remainingSites = []
        for site in siteCandidates:
          if not site in bannedSites:
            remainingSites.append( site )
        if remainingSites:
          if len( remainingSites ) == 1:
            self.log.verbose( 'Individual site candidate for job %s is %s' % ( job, remainingSites[0] ) )
            self.jobDB.setJobAttribute( job, 'Site', remainingSites[0] )
          else:
            self.log.verbose( 'Site candidates for job %s are %s' % ( job, str( remainingSites ) ) )
            self.jobDB.setJobAttribute( job, 'Site', 'Multiple' )
      else:
        self.log.verbose( 'Site candidates for job %s are %s' % ( job, str( siteCandidates ) ) )
        self.jobDB.setJobAttribute( job, 'Site', 'Multiple' )
    else:
      self.log.verbose( 'All sites are eligible for job %s' % job )
      self.jobDB.setJobAttribute( job, 'Site', 'ANY' )

    return self.setNextOptimizer( job )

def applySiteRequirements( sites, activeSites = [], bannedSites = [] ):
  """ Return site list after applying
  """
  siteList = list( sites )
  if activeSites:
    for site in sites:
      if site not in activeSites:
        siteList.remove( site )
  for site in bannedSites:
    if site in siteList:
      siteList.remove( site )

  return siteList



#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#

