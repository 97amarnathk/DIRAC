# Needed for stand alone tests
from DIRAC.Core.Base.Script import parseCommandLine
parseCommandLine(ignoreErrors=False)

from DIRAC.Core.Base.Client import Client

simpleMessageService = Client()
simpleMessageService.serverURL = 'Framework/Hello'
result = simpleMessageService.sayHello('World')
if not result['OK']:
    print "Error while calling the service:", result['Message'] #Here, in DIRAC, you better use the gLogger
else:
    print result[ 'Value' ] #Here, in DIRAC, you better use the gLogger
