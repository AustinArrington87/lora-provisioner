import os.path, serial, io, uuid, csv
import urllib2, json, codecs
import RPi.GPIO as GPIO
import time
import sys
from subprocess import call
# note - script won't work until you enter the LoRa API credentials on ln 85

#turn on Lora module
GPIO.setmode(GPIO.BCM)
LORA = 23
GPIO.setup(LORA,GPIO.OUT)
GPIO.output(LORA,True)

time.sleep(1)

ser = serial.Serial(
    port = '/dev/serial0',
    baudrate = 57600,
    bytesize = serial.EIGHTBITS,
    parity = serial.PARITY_NONE,
    stopbits = serial.STOPBITS_ONE,
    timeout=1,
 )

print "Port is located at: " + ser.name

#get hweui
sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser))
sio.write(unicode(b"sys get hweui\r\n"))
sio.flush()
hweui = sio.readline()
print "hwEUI: " + hweui
#concactanate
devid = "mac set deveui "+hweui+"\r\n"

#set devEUI as hwEUI
sio.write(unicode(devid))
sio.flush()
sio.readline()
sio.write(unicode(b"mac get deveui\r\n"))
sio.flush()
devEUI = sio.readline()
print "devEUI: " + devEUI

#write appEUI
sio.write(unicode(b"mac set appeui YOUR_API_EUI\r\n"))
sio.flush()
sio.readline()
sio.write(unicode(b"mac get appeui\r\n"))
sio.flush()
appEUI = sio.readline()
print "appEUI: " + appEUI

#generate 16byte hexadecimal for nwkKey
nwkKey = uuid.uuid4().hex
print "nwkKey: " + nwkKey
#concactanate
appid = "mac set appkey "+nwkKey+"\r\n"
#write nwkKey
sio.write(unicode(appid))
sio.flush()
sio.readline()
sio.write(unicode(b"mac save\r\n"))
sio.flush()
sio.readline()

#write everything to a CSV

file_exists = os.path.isfile('lora-modules.csv')

with open('lora-modules.csv', 'a') as csvfile:
    headers = ['devEUI', 'appEUI', 'nwkKey']
    writer = csv.DictWriter(csvfile, delimiter=',', lineterminator='\n',fieldnames=headers)

    if not file_exists:
        writer.writeheader()

    writer.writerow({'devEUI': devEUI, 'appEUI': appEUI, 'nwkKey': nwkKey})

print 'DevEUI + appEUI + nwkKey successfully written to lora-modules.csv!'
# print barcode w devEUI
print 'Printing label...'
call(["zint", "-o", "out.svg", "--height=20", "-w", "5", "-d", str(devEUI)])
time.sleep(0.5)
call(["rsvg-convert", "-f", "pdf", "-o", "out.pdf", "out.svg"])
time.sleep(0.5)
call(["lpr", "-#1", "-P", "DYMO_450", "out.pdf"])
# assign devEUI to a node in LoRa Server API
#step 1 - get jwt token
# enter credentials to access API
try:
    url1 = 'https://YOUR_URL:8080/api/internal/login'
    postdata = {'password': '','username': ''}
    req1 = urllib2.Request(url1)
    req1.add_header('Content-Type','application/json')
    data = json.dumps(postdata)
    response = urllib2.urlopen(req1,data)
    token = response.read()
    hold=json.loads(token)
    #decode  the devEUI string to unicode, call replace method to take out '\n' from string, encode back to utf-8
    serialEncoded = devEUI.decode("utf-8").replace(u"\n","").encode("utf-8")
    #step 2 - pass endoded devEUI variable to create device in LoRa Server API
    url2 = 'https://lora.teralytic.io:8080/api/devices'
    nodedata = {
        'device': {
            'applicationID': 'APP_ID',
            'description': 'Agricultural sensor',
            'devEUI': serialEncoded,
            'deviceProfileID': 'DEV_PROFILE_ID',
            'name': serialEncoded[9:16]
	    }
    }
    req2 = urllib2.Request(url2)
    req2.add_header('Content-Type','application/json')
    req2.add_header('Grpc-Metadata-Authorization',hold["jwt"])
    data1 = json.dumps(nodedata)
    response1 = urllib2.urlopen(req2,data1)
    node = response1.read()
    print node+': Node added to LoRa Server API!'
    #step 3 - pass applicationKey to LoRa Server API
    url3 = 'https://lora.teralytic.io:8080/api/devices/'+serialEncoded+'/keys'
    keydata = {
        'devEUI': serialEncoded,
        'deviceKeys': {
            'nwkKey': str(nwkKey)
            }
    }
    req3 = urllib2.Request(url3)
    req3.add_header('Content-Type','application/json')
    req3.add_header('Grpc-Metadata-Authorization',hold["jwt"])
    data2 = json.dumps(keydata)
    response2 = urllib2.urlopen(req3,data2)
    applicationKey = response2.read()
    print applicationKey+': nwkKey added to LoRa Server API!'
    print 'Continue on to the next board.'

except urllib2.HTTPError as err:
    print 'There was an issue connecting to the internet and logging in LoRa Server API. However, the information has been stored in lora-modules.csv. Continue on to the next board.'
    print err
