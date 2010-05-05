""" The Pilots_Command class is a command class to know about 
    present pilots efficiency
"""

from DIRAC import gLogger

from DIRAC.ResourceStatusSystem.Client.Command.Command import Command
from DIRAC.ResourceStatusSystem.Utilities.Exceptions import *

#############################################################################

class RSPeriods_Command(Command):
  
  def doCommand(self):
    """ 
    Return getPeriods from ResourceStatus Client
    
    - args[0] should be a ValidRes

    - args[1] should be the name of the ValidRes

    - args[2] should be the present status

    - args[3] are the number of hours requested
    """

    if self.client is None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient   
      self.client = ResourceStatusClient()
      
    try:
      res = self.client.getPeriods(self.args[0], self.args[1], self.args[2], self.args[3])
    except:
      gLogger.exception("Exception when calling ResourceStatusClient for %s %s" %(self.args[0], self.args[1]))
      return {'Result':'Unknown'}
    
    return {'Result':res}


#############################################################################

class ServiceStats_Command(Command):
  """ 
  The ServiceStats_Command class is a command class to know about 
  present services stats
  """
  
  def doCommand(self):
    """ 
    Uses :meth:`DIRAC.ResourceStatusSystem.Client.ResourceStatusClient.getServiceStats`  

    :params:
      :attr:`args`: a tuple
        - args[1]: a ValidRes 
        
        - args[0]: should be the name of the Site
        
    :returns:
      {'Active':xx, 'Probing':yy, 'Banned':zz, 'Total':xyz}
    """

    if self.client is None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient   
      self.client = ResourceStatusClient()
      
    try:
      res = self.client.getServiceStats(self.args[0], self.args[1])
    except:
      gLogger.exception("Exception when calling ResourceStatusClient for %s %s" %(self.args[0], self.args[1]))
      return {'Result':'Unknown'}
            
    return {'Result':res}
    doCommand.__doc__ = Command.doCommand.__doc__ + doCommand.__doc__
    
#############################################################################

class ResourceStats_Command(Command):
  """ 
  The ResourceStats_Command class is a command class to know about 
  present resources stats
  """
  
  def doCommand(self):
    """ 
    Uses :meth:`DIRAC.ResourceStatusSystem.Client.ResourceStatusClient.getResourceStats`  

    :params:
      :attr:`args`: a tuple
        - `args[0]` string, a ValidRes. Should be in ('Site', 'Service')

        - `args[1]` should be the name of the Site or Service
        
    :returns:
    
    """

    if self.client is None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient   
      self.client = ResourceStatusClient()
      
    try:
      res = self.client.getResourceStats(self.args[0], self.args[1])
    except:
      gLogger.exception("Exception when calling ResourceStatusClient for %s %s" %(self.args[0], self.args[1]))
      return {'Result':'Unknown'}
      
    return {'Result':res}
  doCommand.__doc__ = Command.doCommand.__doc__ + doCommand.__doc__

#############################################################################

class StorageElementsStats_Command(Command):
  """ 
  The StorageElementsStats_Command class is a command class to know about 
  present storageElementss stats
  """
  
  def doCommand(self):
    """ 
    Uses :meth:`DIRAC.ResourceStatusSystem.Client.ResourceStatusClient.getStorageElementsStats`  

    :params:
      :attr:`args`: a tuple
        - `args[0]` should be in ['Site', 'Resource']

        - `args[1]` should be the name of the Site or Resource
        
    :returns:
    
    """
    
    if self.args[0] in ('Service', 'Services'):
      granularity = 'Site'
      name = self.args[1].split('@')[1]
    elif self.args[0] in ('Site', 'Sites', 'Resource', 'Resources'):
      granularity = self.args[0]
      name = self.args[1]
    else:
      raise InvalidRes, where(self, self.doCommand)
    
    if self.client is None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient   
      self.client = ResourceStatusClient()
      
    try:
      res = self.client.getStorageElementsStats(granularity, name)
    except:
      gLogger.exception("Exception when calling ResourceStatusClient for %s %s" %(granularity, name))
      return {'Result':'Unknown'}
    
    return {'Result':res}
  doCommand.__doc__ = Command.doCommand.__doc__ + doCommand.__doc__

#############################################################################

class MonitoredStatus_Command(Command):
  """ 
  The MonitoredStatus_Command class is a command class to know about 
  monitored status
  """
  
  def doCommand(self):
    """ 
    Uses :meth:`DIRAC.ResourceStatusSystem.Client.ResourceStatusClient.getMonitoredStatus`  

    :params:
      :attr:`args`: a tuple
        - `args[0]`: string - should be a ValidRes

        - `args[1]`: string - should be the name of the ValidRes
        
        - `args[2]`: optional string - a ValidRes (get status of THIS ValidRes
          for name in args[1], will call getGeneralName)
        
    :returns:
      {'MonitoredStatus': 'Active'|'Probing'|'Banned'}
    """
    
    if self.client is None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient   
      self.client = ResourceStatusClient()
      
    try:
      if len(self.args) == 3:
        if ValidRes.index(self.args[2]) >= ValidRes.index(self.args[0]):
          raise InvalidRes, where(self, self.doCommand)
        generalName = self.client.getGeneralName(self.args[0], self.args[1], self.args[2])
        res = self.client.getMonitoredStatus(self.args[2], generalName)
      else:
        res = self.client.getMonitoredStatus(self.args[0], self.args[1])
    except:
      gLogger.exception("Exception when calling ResourceStatusClient for %s %s" %(self.args[0], self.args[1]))
      return {'Result':'Unknown'}
    
    return {'Result':res}
  
  doCommand.__doc__ = Command.doCommand.__doc__ + doCommand.__doc__

#############################################################################
