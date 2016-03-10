''' EmailAction

  This action writes all the necessary data to a cache file ( cache.json ) that
  will be used later by the EmailAgent in order to send the emails for each site.

'''

import os
import json
from datetime import datetime
from DIRAC                                                      import gConfig, S_ERROR, S_OK
from DIRAC.Core.Utilities                                       import DErrno
from DIRAC.Interfaces.API.DiracAdmin                            import DiracAdmin
from DIRAC.ResourceStatusSystem.PolicySystem.Actions.BaseAction import BaseAction
from DIRAC.Core.Utilities.SiteSEMapping                         import getSitesForSE

__RCSID__ = '$Id:  $'

class EmailAction( BaseAction ):

  def __init__( self, name, decisionParams, enforcementResult, singlePolicyResults,
                clients = None ):

    super( EmailAction, self ).__init__( name, decisionParams, enforcementResult,
                                         singlePolicyResults, clients )
    self.diracAdmin = DiracAdmin()

    self.dirac_path = os.getenv('DIRAC')
    self.cacheFile = self.dirac_path + 'work/ResourceStatus/' + 'cache.json'

  def run( self ):
    ''' Checks it has the parameters it needs and writes the date to a cache file.
    '''
    # Minor security checks

    element = self.decisionParams[ 'element' ]
    if element is None:
      return S_ERROR( 'element should not be None' )

    name = self.decisionParams[ 'name' ]
    if name is None:
      return S_ERROR( 'name should not be None' )

    statusType = self.decisionParams[ 'statusType' ]
    if statusType is None:
      return S_ERROR( 'statusType should not be None' )

    previousStatus = self.decisionParams[ 'status' ]
    if previousStatus is None:
      return S_ERROR( 'status should not be None' )

    status = self.enforcementResult[ 'Status' ]
    if status is None:
      return S_ERROR( 'status should not be None' )

    reason = self.enforcementResult[ 'Reason' ]
    if reason is None:
      return S_ERROR( 'reason should not be None' )

    siteName = getSitesForSE(name)['Value'][0]
    time     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dict    = { 'name': name, 'statusType': statusType, 'status': status, 'time': time, 'previousStatus': previousStatus }

    actionResult = self._addtoJSON(siteName, dict)

    #returns S_OK() if the record was added successfully using addtoJSON
    return actionResult


  def _addtoJSON(self, siteName, record):
    ''' Adds a record of a banned element to a local JSON file grouped by site name.
    '''

    try:

      if not os.path.isfile(self.cacheFile) or (os.stat(self.cacheFile).st_size == 0):
        #if the file is empty or it does not exist create it and write the first element of the group
        with open(self.cacheFile, 'w') as f:
          json.dump({ siteName: [record] }, f)

      else:
        #otherwise load the file
        with open(self.cacheFile, 'r') as f:
          new_dict = json.load(f)

        #if the site's name is in there just append the group
        if siteName in new_dict:
          new_dict[siteName].append(record)
        else:
          #if it is not there, create a new group
          new_dict.update( { siteName: [record] } )

        #write the file again with the modified contents
        with open(self.cacheFile, 'w') as f:
          json.dump(new_dict, f)

      return S_OK()

    except ValueError as e:
      return S_ERROR(DErrno.EWF, "Error %s" % repr(e))

################################################################################
#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF
