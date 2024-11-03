#!/usr/bin/env python3

import RPi.GPIO as GPIO 
import time
import LCD1602
from mfrc522 import SimpleMFRC522
import smbus2 as smbus
import subprocess
import threading

rgbPins = {'Red':18, 'Green':27, 'Blue':22}
pirPin = 17    # the pir connect to pin17
armed = False
motion = False
motion_time = time.time()
check_time = time.time()

def setup():
	init(0x27, 0)
	
	GPIO.setmode(GPIO.BCM)		# Set the GPIO modes to BCM Numbering
	GPIO.setup(pirPin, GPIO.IN)    # Set pirPin to input
	 
	# PIR setup
	global p_R, p_G, p_B
	# Set all LedPin's mode to output and initial level to High(3.3v)
	for i in rgbPins:
		GPIO.setup(rgbPins[i], GPIO.OUT, initial=GPIO.HIGH)

	# Set all led as pwm channel and frequency to 2KHz
	p_R = GPIO.PWM(rgbPins['Red'], 2000)
	p_G = GPIO.PWM(rgbPins['Green'], 2000)
	p_B = GPIO.PWM(rgbPins['Blue'], 2000)

	# Set all begin with value 0
	p_R.start(0)
	p_G.start(0)
	p_B.start(0)
	 
	#LCD setup
	LCD1602.init(0x3f, 0)    # init(slave address, background light)
	LCD1602.clear()

def send_command(comm):
	# Send bit7-4 firstly
	buf = comm & 0xF0
	buf |= 0x04               # RS = 0, RW = 0, EN = 1
	write_word(LCD_ADDR ,buf)
	time.sleep(0.002)
	buf &= 0xFB               # Make EN = 0
	write_word(LCD_ADDR ,buf)

	# Send bit3-0 secondly
	buf = (comm & 0x0F) << 4
	buf |= 0x04               # RS = 0, RW = 0, EN = 1
	write_word(LCD_ADDR ,buf)
	time.sleep(0.002)
	buf &= 0xFB               # Make EN = 0
	write_word(LCD_ADDR ,buf)

def send_data(data):
	# Send bit7-4 firstly
	buf = data & 0xF0
	buf |= 0x05               # RS = 1, RW = 0, EN = 1
	write_word(LCD_ADDR ,buf)
	time.sleep(0.002)
	buf &= 0xFB               # Make EN = 0
	write_word(LCD_ADDR ,buf)

	# Send bit3-0 secondly
	buf = (data & 0x0F) << 4
	buf |= 0x05               # RS = 1, RW = 0, EN = 1
	write_word(LCD_ADDR ,buf)
	time.sleep(0.002)
	buf &= 0xFB               # Make EN = 0
	write_word(LCD_ADDR ,buf)

def i2c_scan():
    cmd = "i2cdetect -y 1 |awk \'NR>1 {$1=\"\";print}\'"
    result = subprocess.check_output(cmd, shell=True).decode()
    result = result.replace("\n", "").replace(" --", "")
    i2c_list = result.split(' ')
    return i2c_list

def init(addr=None, bl=1):
	global LCD_ADDR
	global BLEN

	i2c_list = i2c_scan()
	print(f"i2c_list: {i2c_list}")

	if addr is None:
		if '27' in i2c_list:
			LCD_ADDR = 0x27
		elif '3f' in i2c_list:
			LCD_ADDR = 0x3f
		else:
			raise IOError("I2C address 0x27 or 0x3f no found.")
	else:
		LCD_ADDR = addr
		if str(hex(addr)).strip('0x') not in i2c_list:
			raise IOError(f"I2C address {str(hex(addr))} or 0x3f no found.")
		
	BLEN = bl
	try:
		send_command(0x33) # Must initialize to 8-line mode at first
		time.sleep(0.005)
		send_command(0x32) # Then initialize to 4-line mode
		time.sleep(0.005)
		send_command(0x28) # 2 Lines & 5*7 dots
		time.sleep(0.005)
		send_command(0x0C) # Enable display without cursor
		time.sleep(0.005)
		send_command(0x01) # Clear Screen
		BUS.write_byte(LCD_ADDR, 0x08)
	except:
		return False
	else:
		return True

def clear():
	send_command(0x01) # Clear Screen

def openlight():  # Enable the backlight
	BUS.write_byte(0x27,0x08)
	BUS.close()

def closelight():  # Enable the backlight
	BUS.write_byte(0x27,0x00)
	BUS.close()

def write(x, y, str):
	if x < 0:
		x = 0
	if x > 15:
		x = 15
	if y <0:
		y = 0
	if y > 1:
		y = 1

	# Move cursor
	addr = 0x80 + 0x40 * y + x
	send_command(addr)

	for chr in str:
		send_data(ord(chr))

# LED coloring

# Define a MAP function for mapping values.  Like from 0~255 to 0~100
def MAP(x, in_min, in_max, out_min, out_max):
	return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

BUS = smbus.SMBus(1)

def write_word(addr, data):
	global BLEN
	temp = data
	if BLEN == 1:
		temp |= 0x08
	else:
		temp &= 0xF7
	BUS.write_byte(addr ,temp)

# Define a function to set up colors 
def setColor(color):
 # configures the three LEDs' luminance with the inputted color value . 
	# Devide colors from 'color' variable
	R_val = (color & 0xFF0000) >> 16
	G_val = (color & 0x00FF00) >> 8
	B_val = (color & 0x0000FF) >> 0
	# Map color value from 0~255 to 0~100
	R_val = MAP(R_val, 0, 255, 0, 100)
	G_val = MAP(G_val, 0, 255, 0, 100)
	B_val = MAP(B_val, 0, 255, 0, 100)
	
	#Assign the mapped duty cycle value to the corresponding PWM channel to change the luminance. 
	p_R.ChangeDutyCycle(R_val)
	p_G.ChangeDutyCycle(G_val)
	p_B.ChangeDutyCycle(B_val)
	#print ("color_msg: R_val = %s,	G_val = %s,	B_val = %s"%(R_val, G_val, B_val))
	 
def pir_check():
	global armed
	global motion
	pir_val = GPIO.input(pirPin)
	if pir_val==GPIO.HIGH:
		setColor(0xFFFF00)
		timer()
		if armed and not motion:
			motion = True
			timer()
	else :
		if armed:
			setColor(0xFF0000)
		else:
			setColor(0x00FF00F)

def clear():
	send_command(0x01) # Clear Screen

def openlight():  # Enable the backlight
	BUS.write_byte(0x27,0x08)
	BUS.close()

def closelight():  # Enable the backlight
	BUS.write_byte(0x27,0x00)
	BUS.close()

def timer():  
    global counter
    global timer1
    timer1 = threading.Timer(1, timer) 
    timer1.start()  
    counter += 1
	

def destroy():
	p_R.stop()
	p_G.stop()
	p_B.stop()
	LCD1602.clear()
	GPIO.cleanup()

def loop():
	while True:
		if counter > 30:
			print("alarm")
			LCD1602.write(0, 0, 'Greetings!')
			LCD1602.write(1, 1, 'From SunFounder')

def activate():
	global armed
	global counter
	global motion
	armed = True
	counter = 0
	motion = False

def deactivate():
	global armed
	armed = False

if __name__ == '__main__':     # Program start from here
	try:
		setup()
		pir_thread = threading.Thread(target=pir_check)
		#t2 = threading.Thread(target=thread2)
		# start the threads
		pir_thread.start()
		#t2.start()
		time.sleep(10)
	except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the program destroy() will be  executed.
		destroy()
