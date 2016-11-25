"""Unit tests of MQCommunication interface in the DIRAC.Resources.MessageQueue.MQCommunication
"""

import unittest
from DIRAC.Resources.MessageQueue.MQCommunication import createProducer
from DIRAC.Resources.MessageQueue.MQCommunication import setupConnection
from DIRAC import S_OK, S_ERROR
import mock
#from DIRAC.Resources.MessageQueue.MQCommunication import createConsumer
#from DIRAC.Resources.MessageQueue.MQCommunication import setupConnection

class TestMQCommunication( unittest.TestCase ):
  def setUp( self ):
    pass
  def tearDown( self ):
    pass

class TestMQCommunication_setupConnection( TestMQCommunication):
  @mock.patch('DIRAC.Resources.MessageQueue.MQCommunication.getMQParamsFromCS')
  def test_success(self, mock_getMQParamsFromCS):
    mock_getMQParamsFromCS.return_value = S_OK({'Queue':'test1', 'MQType':'Fake', 'Host':'mardirac3.in2p3.fr', 'Port':'666'})
    mqURI = 'mardirac3.in2p3.fr::Queue::test1'
    result = setupConnection(mqURI = mqURI, messangerType = "producer")

    #connection = result['Value']
    #result = connection.get()
    #self.assertEqual(result, "FakeMQConnection getting message" )
    #result = connection.start()
    #self.assertEqual(result, "FakeMQConnection started" )
    #result = connection.stop()
    #self.assertEqual(result, "FakeMQConnection stopped" )
    #result = connection.disconnect()
    #self.assertEqual(result, "FakeMQConnection disconnected" )

#class TestMQCommunication_createFakeProducer( TestMQCommunication):
  #def test_success( self ):
    #producer = createProducer(mqURI = "/queue/testFakeQueue")
    #result = producer.put("wow!")
    #self.assertEqual(result, "FakeMQConnection sending message wow!" )
    #result = producer.put("wow2!")
    #self.assertEqual(result, "FakeMQConnection sending message wow2!" )
    #result = producer.close()
    #self.assertEqual(result, "FakeMQConnection disconnected" )



#class TestMQCommunication_createFakeConsumer( TestMQCommunication):
  #def test_success( self ):
    #consumer = createConsumer(destination = "/queue/testFakeQueue")
    #result = consumer.get()
    #self.assertEqual(result, "FakeMQConnection getting message" )
    #result = consumer.close()
    #self.assertEqual(result, "FakeMQConnection disconnected" )

class TestMQCommunication_myProducer( TestMQCommunication):
  @mock.patch('DIRAC.Resources.MessageQueue.MQCommunication.getMQParamsFromCS')
  def test_success(self, mock_getMQParamsFromCS):
    mock_getMQParamsFromCS.return_value = S_OK({'VHost':'/', 'Queue':'test2', 'MQType':'Stomp', 'Host':'localhost', 'Port':'61613', 'User':'ala', 'Password':'ala'})
    producer = createProducer(mqURI = 'localhost::Queue::test2')
    result = producer.put( 'blabla')
    self.assertTrue(result['OK']) 
    result = producer.put( 'blable')
    #mock_getMQParamsFromCS.return_value = S_OK({'VHost':'/', 'Queue':'test2', 'MQType':'Stomp', 'Host':'localhost', 'Port':'61613', 'User':'ala', 'Password':'ala'})
    #producer2 = createProducer(mqURI = 'localhost::Queue::test2')
    #result = producer2.put( 'blabla2')
    #self.assertTrue(result['OK']) 
    #result = producer2.put( 'blable2')
    #self.assertTrue(result['OK']) 
    mock_getMQParamsFromCS.return_value = S_OK({'VHost':'/', 'Queue':'test3', 'MQType':'Stomp', 'Host':'localhost', 'Port':'61613', 'User':'ala', 'Password':'ala'})
    producer3 = createProducer(mqURI = 'localhost::Queue::test3')
    result = producer3.put( 'blabla3')
    self.assertTrue(result['OK']) 
    result = producer3.put( 'blable3')
    self.assertTrue(result['OK']) 
    #result = producer2.close()
    #self.assertTrue(result['OK']) 
    producer3.close()
    



if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestMQCommunication )
  #suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestMQCommunication_setupConnection))
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestMQCommunication_myProducer))
  #suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestMQCommunication_createFakeProducer))
  #suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestMQCommunication_createFakeConsumer))
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
