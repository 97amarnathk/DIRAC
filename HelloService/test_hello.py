import unittest
from DIRAC.Core.DISET.RPCClient import RPCClient

""" 
Base test Class
"""
class TestHelloHandler( unittest.TestCase ):

  def setUp( self ):
    self.helloService = RPCClient('Framework/Hello')

  def tearDown( self ):
    pass

class TestHelloHandlerSuccess( TestHelloHandler ):

  def test_success( self ):
      input_string = '123'
      expected_string = 'Hello 123'
      response = self.helloService.sayHello(input_string)['Value']
      #self.assertEqual(response, expected_string)

class TestHelloHandlerFailure( TestHelloHandler ):

  def test_failure( self ):
      input_string = '123'
      expected_string = 'Hello World'
      response = self.helloService.sayHello(input_string)['Value']
      self.assertNotEqual(response, expected_string)


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestHelloHandler )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestHelloHandlerSuccess ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestHelloHandlerFailure ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

