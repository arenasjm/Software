#!/usr/bin/env python
import threading, Queue
import pika
import serial
import time
import numpy as np
import re

def callback(ch, method, properties, body): #Function adds the received messages in the queue for communication with the other thread
    #print(" [x] Received %r" % body)
    if re.search('person', body): #If person detected -> add detection to the queue
   	 out_q.put(body)

def sensors(): #Function reads the ultrasonic sensor value given by the arduino
	global US_sensor
	arduino.flushInput() 
	arduino.write(b':')
	for i in range(5):
		US_sensor = arduino.readline()
		if re.search('US Sensors :[0-9][0-9][0-9] [0-9][0-9][0-9] [0-9][0-9][0-9]', US_sensor): #Discards the messages not corresponding with the expected one
			US_sensor = US_sensor.split(':') 
			US_sensor = US_sensor[1] #Only numeric value of the string: XXX YYY ZZZ
			US_sensor = US_sensor.split(' ')
			US_sensor = US_sensor[0] #Only the one returning info (X-axis)
			US_sensor = int(US_sensor) 
			print US_sensor
			return US_sensor

def move(message): #Function in charge of the movement
	global maxmove 
	print(" [x] %r" % message)
	receivedstring = message.split(',') 
	detected = receivedstring[0] #Info about the detected object  
	left = receivedstring[1].split('=') #Info about the left position of the bounding box 
	left = left[1]  #Only numeric value 
	left = int(left)
	right = receivedstring[3].split('=') #Info about the right position of the bounding box 
	right = right[1]  #Only numeric value 
	right = int(right)
	pos = (((right - left)/2) + left) #Center of the bounding box corresponding to the detected object/person
	#print "recibido " + detected + "at: " + str(pos) + "->" + str(left) + "," + str(right)
	if re.search('person', detected): #If person detected -> follow
		if (left <= 150) and (right >= 550): #if the bounding box is too big: forwards
			arduino.write(b'40075') #Forwards 75mm 
			maxmove += 1            	
		else:
			if (pos > 150) and (pos < 500): #If the person is in the center: forwards
				arduino.write(b'40100') #Forwards 75mm
				maxmove += 1 
			if (pos > 500): #If person is at the left position: turn  
				arduino.write(b'3010') #Clockwise 10 degrees
			if(pos < 150): #If person is at the right position: turn  
				arduino.write(b'2010') #Counter-clockwise 10 degrees
	else:
		arduino.write(b'?') #If no person is detected -> don't move
	out_q.queue.clear() #Empty queue to act on the most recent object detected

def consumer(): # T H R E A D -- 1
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost')) #Message broker conection establishing
    channel = connection.channel() #Open channel 
    channel.queue_declare(queue=queueName) #Suscription to the message broker queue
    channel.basic_consume(callback,      #If there is a message use callback to input new message in the other queue
                      queue=queueName,   #
                      no_ack=True)       #
    print(' [*] Waiting for messages. To exit press CTRL+Z')
    channel.start_consuming() #Start consuming
    
def moving(): # T H R E A D -- 2 
    global maxmove 
    global colision
    stoprequest = threading.Event() #Thread won't stop until stop event occurs
    while not stoprequest.isSet():  #Thread won't stop until stop event occurs
	try:
	    message = out_q.get(True, 0.005) #Read new message from queue every 0.005s
	    if maxmove == 5:
	    	sensors()
		if ((US_sensor <= 80) and (US_sensor != 0) and (colision == 0)): #Colision might happen
			arduino.write(b'50200') #Backwards 200mm
			time.sleep(1)
			arduino.write(b'3020') #Clockwise 20 degrees
			time.sleep(1)
			colision = 1
		elif ((US_sensor <= 80) and (US_sensor != 0) and (colision == 1)): #Colision might happen
			arduino.write(b'50200') #Backwards 200mm
			time.sleep(1)
			arduino.write(b'2045') #Clockwise 45 degrees
			time.sleep(1)
			colision = 0
		maxmove = 0
	    else:
            	move(message) #Movement regarding the new object detected
	except Queue.Empty:
	    continue



if __name__ == '__main__': # M A I N 
	queueName = 'detection' #Queue YOLO is sending the detections to 
	out_q = Queue.Queue()   #Queue in charge of communicating the two available threads
	out_q.queue.clear()     #Clear any waste messages left on the queue
	global US_sensor 
        global detected 
	global person
	global left 
	global right 
	global maxmove 
	global colision
	colision = 0 #Check if it has been able to avoid object that might cause colision
	maxmove = 0 #Maximum number of movements before checking the US sensors
	arduino = serial.Serial("/dev/ttyUSB1", 38400, timeout=1); #Establish connection with arduino serial port at 38400 baud
	arduino.setDTR(False) #Run new connection with arduino
	time.sleep(1)         #
	arduino.flushInput()  #
	arduino.setDTR(True)  #
	print arduino.readline() # if print = LOLA INI V1.00 -> inicialized OK
	t1 = threading.Thread(target=consumer) #Thread n.1
	t1.start()
	t2 = threading.Thread(target=moving) #Thread n.2
	t2.start()

		

