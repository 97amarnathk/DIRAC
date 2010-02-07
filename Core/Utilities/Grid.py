# $HeadURL:  $


""" The Grid module contains several utilities for grid operations
"""

__RCSID__ = "$Id:  $"

import os
from DIRAC.Core.Utilities.Os import sourceEnv
from DIRAC.FrameworkSystem.Client.ProxyManagerClient  import gProxyManager
from DIRAC import systemCall, shellCall, S_OK, S_ERROR

def executeGridCommand(self, proxy, cmd, gridEnvScript=None ):
    """
     Execute cmd tuple after sourcing GridEnv
    """
    currentEnv = dict(os.environ)
    if gridEnvScript:
      self.log.verbose( 'Sourcing GridEnv script:', gridEnvScript )
      ret = sourceEnv( 10, [gridEnvScript] )
      if not ret['OK']:
        self.log.error( 'Failed sourcing GridEnv:', ret['Message'] )
        return S_ERROR( 'Failed sourcing GridEnv' )
      if ret['stdout']: self.log.verbose( ret['stdout'] )
      if ret['stderr']: self.log.warn( ret['stderr'] )
      gridEnv = ret['outputEnv']

    ret = gProxyManager.dumpProxyToFile( proxy )
    if not ret['OK']:
      self.log.error( 'Failed to dump Proxy to file' )
      return ret
    gridEnv[ 'X509_USER_PROXY' ] = ret['Value']
    self.log.verbose( 'Executing', ' '.join(cmd) )
    return systemCall( 120, cmd, env = gridEnv )
  
def ldapsearchBDII( filt=None, attr=None, host=None, base = None ):
  """ Python wrapper for ldapserch at bdii.
      
      Input parameters:
        filt:    Filter used to search ldap, default = '', means select all
        attr:    Attributes returned by ldapsearch, default = '*', means return all
        host:    Host used for ldapsearch, default = 'lcg-bdii.cern.ch:2170', can be changed by $LCG_GFAL_INFOSYS
      
      Return standart DIRAC answer with Value equals to list of ldapsearch responses
      Each element of list is dictionary with keys:
        'dn':                 Distinguished name of ldapsearch response
        'objectClass':        List of classes in response
        'attr':               Dictionary of attributes
  """

  if filt == None:
    filt = ''
  if attr == None:
    attr = '*'
  if host == None:
    host='lcg-bdii.cern.ch:2170'
  if base == None:
    base = 'Mds-Vo-name=local,o=grid'

  cmd = 'ldapsearch -x -LLL -h %s -b %s "%s" "%s"'%(host,base,filt,attr)
  result = shellCall(0,cmd)

  response = []

  if not result['OK']:
    return result

  status = result['Value'][0]
  stdout = result['Value'][1]
  stderr = result['Value'][2]

  if not status==0:
    return S_ERROR( stderr )

  lines = []
  for line in stdout.split("\n"):
    if line.find(" ")==0:
      lines[-1]+=line.strip()
    else:
      lines.append(line.strip())

  record = None
  for line in lines:
    if line.find('dn:')==0:
      record = {'dn':line.replace('dn:','').strip(),'objectClass':[],'attr':{'dn':line.replace('dn:','').strip()}}
      response.append(record)
      continue
    if record:
      if line.find('objectClass:')==0:
        record['objectClass'].append(line.replace('objectClass:','').strip())
        continue
      if line.find('Glue')==0:
        index = line.find(':')
        if index>0:
          attr = line[:index]
          value = line[index+1:].strip()
          if record['attr'].has_key(attr):
            if type(record['attr'][attr])==type([]):
              record['attr'][attr].append(value)
            else:
              record['attr'][attr] = [record['attr'][attr],value]
          else:
            record['attr'][attr] = value

  return S_OK(response)


def ldapSite( site, attr=None, host=None ):
  """ Site information from bdii.
      Input parameter:
        site:         Site as it defined in GOCDB or part of it whith globbing
                      for example: "UKI-*"
      Return standart DIRAC answer with Value equals to list of sites.
      Each site is dictionary which contains attributes of site.
      For example result['Value'][0]['GlueSiteLocation']
  """
  filt = '(GlueSiteUniqueID=%s)'%site

  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  sites = []
  for value in result['Value']:
    sites.append(value['attr'])

  return S_OK(sites)

def ldapCluster( ce, attr=None, host=None ):
  """ CE (really SubCluster in definition of bdii) information from bdii.
      It contains by the way host information for ce.
      Input parameter:
        ce:           ce or part of it whith globbing
                      for example  "ce0?.tier2.hep.manchester*"
      Return standart DIRAC answer with Value equals to list of clusters.
      Each cluster is dictionary which contains attributes of ce.
      For example result['Value'][0]['GlueHostBenchmarkSI00']
  """
  filt = '(GlueClusterUniqueID=%s)'%ce

  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  clusters = []
  for value in result['Value']:
    clusters.append(value['attr'])

  return S_OK(clusters)

def ldapCE( ce, attr=None, host=None ):
  """ CE (really SubCluster in definition of bdii) information from bdii.
      It contains by the way host information for ce.
      Input parameter:
        ce:           ce or part of it whith globbing
                      for example  "ce0?.tier2.hep.manchester*"
      Return standart DIRAC answer with Value equals to list of clusters.
      Each cluster is dictionary which contains attributes of ce.
      For example result['Value'][0]['GlueHostBenchmarkSI00']
  """
  filt = '(GlueSubClusterUniqueID=%s)'%ce

  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  ces = []
  for value in result['Value']:
    ces.append(value['attr'])

  return S_OK(ces)

def ldapCEState( ce, vo='lhcb', attr=None, host=None ):
  """ CEState information from bdii. Only CE with CEAccessControlBaseRule=VO:lhcb are selected.
      Input parameter:
        ce:           ce or part of it whith globbing
                      for example  "ce0?.tier2.hep.manchester*"
      Return standart DIRAC answer with Value equals to list of ceStates.
      Each ceState is dictionary which contains attributes of ce.
      For example result['Value'][0]['GlueCEStateStatus']
  """
  filt = '(&(GlueCEUniqueID=%s*)(GlueCEAccessControlBaseRule=*%s*))'%(ce,vo)

  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  states = []
  for value in result['Value']:
    states.append(value['attr'])

  return S_OK(states)

def ldapCEVOView( ce, vo='lhcb', attr=None, host=None ):
  """ CEVOView information from bdii. Only CE with CEAccessControlBaseRule=VO:lhcb are selected.
      Input parameter:
        ce:           ce or part of it whith globbing
                      for example  "ce0?.tier2.hep.manchester*"
      Return standart DIRAC answer with Value equals to list of ceVOViews.
      Each ceVOView is dictionary which contains attributes of ce.
      For example result['Value'][0]['GlueCEStateRunningJobs']
  """

  filt = '(&(GlueCEUniqueID=%s*)(GlueCEAccessControlBaseRule=*%s*))'%(ce,vo)
  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  ces = result['Value']

  filt = '(&(objectClass=GlueVOView)(GlueCEAccessControlBaseRule=*%s*))'%vo
  views = []

  for ce in ces:
    dn = ce['dn']
    result = ldapsearchBDII( filt, attr, host, base=dn )
    if result['OK']:
      views.append(result['Value'][0]['attr'])

  return S_OK(views)

def ldapSA( site, vo='lhcb', attr=None, host=None ):
  """ CEVOView information from bdii. Only CE with CEAccessControlBaseRule=VO:lhcb are selected.
      Input parameter:
        ce:    ce or part of it whith globbing
          for example  "ce0?.tier2.hep.manchester*"
      Return standart DIRAC answer with Value equals to list of ceVOViews.
      Each ceVOView is dictionary which contains attributes of ce.
      For example result['Value'][0]['GlueCEStateRunningJobs']
  """

  filt = '(&(GlueSEUniqueID=*)(GlueForeignKey=GlueSiteUniqueID=%s))'%(site)
  result = ldapsearchBDII( filt, attr, host )

  if not result['OK']:
    return result

  ses = result['Value']

  filt = 'GlueSALocalID=%s'%vo
  sas = []

  for se in ses:
    dn = se['dn']
    result = ldapsearchBDII( filt, attr, host, base=dn )
    if result['OK']:
      if result['Value']:
        sas.append(result['Value'][0]['attr'])

  return S_OK(sas)

  
