"""
Hello World
"""

__RCSID__ = "$Id$"

from DIRAC import gLogger, S_OK, S_ERROR
from DIRAC.Core.DISET.RequestHandler import RequestHandler

# All service handlers are inherited from RequestHandler
class HelloHandler(RequestHandler):

    @classmethod
    def initializeHandler(cls, serviceInfo):
        """
        Handler Initialization
        """
        cls.defaultWhom = "World"
        return S_OK()

    def initialize(self):
        """
        Response initialisation
        """
        self.requestDefaultWhom = self.srv_getCSOption("DefaultWhom", HelloHandler.defaultWhom)
    
    auth_sayHello = ['all']
    types_sayHello = [basestring]

    def export_sayHello(self, whom):
        """
        Say hello to somebody
        """
        gLogger.notice("Called sayHello of HelloHandler with whom = %s" % whom)
        if not whom:
            whom = self.requestDefaultWhom
        if whom.lower() == 'nobody':
            return S_ERROR("Not greeting anybody!")
        return S_OK("Hello " + whom)
    
