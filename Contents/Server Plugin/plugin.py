#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Control an Aviosys IP9528 IP PDU from Indigo
# V1.1	4 November 2012
# Copyright (c) 2012, Nick Smith
# MIT licence - refer to licence.txt
#
# Based on example code from Indigo SDK v1.02
# Copyright (c) 2012, Perceptive Automation, LLC.
# http://www.perceptiveautomation.com

# V1.1: added code to keep connection alive to improve response time
# V1.0: initial version

# import os
# import sys
import urllib2
import socket
import string

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
class Plugin(indigo.PluginBase):
	
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = pluginPrefs.get("showDebugInfo", False)
		self.interval = int(pluginPrefs.get("interval", False))
		
	def __del__(self):
		indigo.PluginBase.__del__(self)

	########################################
	def startup(self):
		self.debugLog(u"startup called")
		# setup a socket timeout
		timeout = 5
		socket.setdefaulttimeout(timeout)

	########################################		
	def shutdown(self):
		self.debugLog(u"shutdown called")

	########################################
	def runConcurrentThread(self):
		self.debugLog("Starting concurrent thread")
		try:
			while True:
				prId = "com.nickandmeryl.ip9258"
				self.debugLog("Found prId " + prId)
				for device in indigo.devices.iter(prId):	
					self.debugLog("Found device " + device.name)		
					self.readAndUpdateState(device)
					
				self.debugLog("Sleeping for " + str(self.interval * 60) + " minutes")
				self.sleep(self.interval * 60)
						
		except self.StopThread:
			self.debugLog("runConcurrentThread stopping: ")	
			pass

	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		# validate supplied values
		outletNum = int(valuesDict["outlet"])
		if outletNum < 1 or outletNum > 4:
			self.errorLog(u"Error: Outlet \"%s\" must be between 1 & 4" % str(outletNum))
			errorDict = indigo.Dict()
			errorDict["outlet"] = "The value of this field must be between 1 & 4"
			return (False, valuesDict, errorDict)
		else:
			return True

	########################################
	def getDeviceStateList(self, dev):
		typeId = dev.deviceTypeId
		statesList = self.devicesTypeDict[typeId][u'States']

		if dev.pluginProps['model'] == 'IP9255Pro':
			stateDict = {'Disabled': False, 'Key': 'temp', 'StateLabel': 'temp', 'TriggerLabel': 'temp', 'Type': 100}
			statesList.append(stateDict)
			stateDict = {'Disabled': False, 'Key': 'current', 'StateLabel': 'current', 'TriggerLabel': 'current', 'Type': 100}
			statesList.append(stateDict)
	 
		return statesList

	########################################
	# Relay / Dimmer Action callback
	######################
	def actionControlDimmerRelay(self, action, dev):
			
		###### TURN ON ######
		if action.deviceAction == indigo.kDeviceAction.TurnOn:
			# Command hardware module (dev) to turn ON here:						
			if self.setPDUState(dev, "on") == 0:
				sendSuccess = True
			else:
				sendSuccess = False

			if sendSuccess:
				# If success then log that the command was successfully sent.
				indigo.server.log(u"Turned \"%s\" %s" % (dev.name, "on"))
	
				# And then tell the Indigo Server to update the state.
				dev.updateStateOnServer("onOffState", True)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "on"), isError=True)

		###### TURN OFF ######
		elif action.deviceAction == indigo.kDeviceAction.TurnOff:
			# Command hardware module (dev) to turn OFF here:			
			if self.setPDUState(dev, "off") == 0:
				sendSuccess = True
			else:
				sendSuccess = False

			if sendSuccess:
				# If success then log that the command was successfully sent.
				indigo.server.log(u"Turned \"%s\" %s" % (dev.name, "off"))
	
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", False)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)

		###### TOGGLE ######
		elif action.deviceAction == indigo.kDeviceAction.Toggle:
			# Command hardware module (dev) to toggle here:
			sendSuccess = False
			newOnState = not dev.onState
			if newOnState == True:
				# currently off, so turn on
				if self.setPDUState(dev, "on") == 0:
					sendSuccess = True
			else:
				# currently on, so turn off
				if self.setPDUState(dev, "off") == 0:
					sendSuccess = True
				
			if sendSuccess:
				# If success then log that the command was successfully sent.
				indigo.server.log(u"sent \"%s\" %s" % (dev.name, "toggle"))
	
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", newOnState)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "toggle"), isError=True)

		###### STATUS REQUEST ######
		elif action.deviceAction == indigo.kDeviceAction.RequestStatus:
			# Query hardware module (dev) for its current states here:
			self.readAndUpdateState(dev)		

	########################################
	def setPDUState(self, dev, state):
		# send command to PDU to change state of an outlet
		# state argument is either "on" or "off"
		
		# validate inputs
		state_num = 2
		if string.lower(state) == "on":
			state_num = 1
		elif string.lower(state) == "off":
			state_num = 0
		else:
			self.errorLog(u"Error: State must be on or off")
			return(state_num)
			
		userName = dev.pluginProps["userName"]
		password = dev.pluginProps["password"]
		pduIpAddr = dev.pluginProps["ipAddr"]
		outlet = dev.pluginProps["outlet"]
		
		self.debugLog("Username: " + userName)
		self.debugLog("Password: " + password)
		self.debugLog("IP address: " + pduIpAddr)
		self.debugLog("Outlet: " + outlet)

		# build the request string to send to the PDU
		base_url_cmd = "http://" + pduIpAddr + "/set.cmd?user=" + userName + "+pass=" + password + "+"
		url_cmd = base_url_cmd +  "cmd=setpower+p6" + outlet + "=" + str(state_num)
	
		self.debugLog(u"Sending to PDU: " + url_cmd)
	
		try:
			# send the command to the PDU & clean up afterwards
			response = urllib2.urlopen(url_cmd)
			response.read()
			response.close()
		
		except urllib2.URLError, e:
			if hasattr(e, 'reason'):
				self.errorLog(u"Error: We failed to reach a server.")
				self.errorLog("Reason: " + str(e.reason))
				return(2)
			elif hasattr(e, 'code'):
				self.errorLog(u"Error: The server couldn\'t fulfill the request.")
				self.errorLog("Error code: " + str(e.code))
				return(2)
		
		else:
			# everything worked
			self.debugLog(u"Sent to PDU")
			return(0)

	########################################			
	def getPDUState(self, dev):
		# request state of PDU
		# returns state of all outlets in a single string
		userName = dev.pluginProps["userName"]
		password = dev.pluginProps["password"]
		pduIpAddr = dev.pluginProps["ipAddr"]
		outlet = dev.pluginProps["outlet"]
		
		self.debugLog("Username: " + userName)
		self.debugLog("Password: " + password)
		self.debugLog("IP address: " + pduIpAddr)
		self.debugLog("Outlet: " + outlet)

		# build the request string to send to the PDU
		base_url_cmd = "http://" + pduIpAddr + "/set.cmd?user=" + userName + "+pass=" + password + "+"
		url_cmd = base_url_cmd +  "cmd=getpower"
		self.debugLog(u"Created URL command " + url_cmd )
			
		resultCode = 0
		
		try:
			# send the command to the PDU & clean up afterwards
			response = urllib2.urlopen(url_cmd)
			resultString = response.read()

			if dev.pluginProps['model'] == 'IP9255Pro':
				url_cmd = base_url_cmd +  "cmd=gettemperature"
				response = urllib2.urlopen(url_cmd)
				resultString += response.read()
				url_cmd = base_url_cmd +  "cmd=getcurrent"
				response = urllib2.urlopen(url_cmd)
				resultString += response.read()

			response.close()
			self.debugLog(u"Received response " + str(resultString))
		
		except urllib2.URLError, e:
			if hasattr(e, 'reason'):
				self.errorLog(u"Error: We failed to reach a server.")
				self.errorLog("Reason: " + str(e.reason))
				return("2")
			elif hasattr(e, 'code'):
				self.errorLog(u"Error: The server couldn\'t fulfill the request.")
				self.errorLog("Error code: " + str(e.code))
				return("2")	
		else:
			# everything worked
			self.debugLog(u"Sent to PDU: " + url_cmd)
			self.debugLog(u"Received from PDU: " + resultString)
			
			# check if this outlet status is in string returned from PDU
			# if so, grab the 5th char which will be either 1 (on) or 0 (off)
			# f we have a 9255Pro, also get the temp and current (mispelled as Cruuent in the API)
			outletString = "p6" + outlet + "="
			index = resultString.find(outletString)
			if index != -1:
				resultCode = resultString[index+4]
				if dev.pluginProps['model'] == 'IP9255Pro':
					index = resultString.find('Temperature:')
					resultCode +=  "+" + resultString[index+13:index+15]
					index = resultString.find('Cruuent:')
					resultCode +=  "+" + resultString[index+8:index+11]

				self.debugLog(u"Received code " + str(resultCode))
			else:
				self.errorLog(u"Error: received unexpected response \"" + resultString + "\"")
				resultCode = "2"
			
			return(resultCode)	

	########################################			
	def readAndUpdateState(self, dev):
		# request state from the PDU & update state variable accordingly
		logChanges = dev.pluginProps['logChanges']

		resultCode = self.getPDUState(dev)
		if resultCode == '2':
			self.errorLog(u"Error: PDU %s in unknown state: %s" % (dev.name, resultCode))
			return(False)

		if dev.pluginProps['model'] == 'IP9255Pro':
			(resultCode,temp,current) = resultCode.split("+")
			self.debugLog(u"Received codes: %s, %s, %s " % (resultCode, temp, current))
			dev.updateStateOnServer("temp", temp)
			dev.updateStateOnServer("current", current)
	
		if int(resultCode) == 0:
			dev.updateStateOnServer("onOffState", False)
			if logChanges: 
				indigo.server.log(u"Device %s is off" % dev.name)
			return(True)
		elif int(resultCode)  == 1:
			dev.updateStateOnServer("onOffState", True)
			if logChanges: 
				indigo.server.log(u"Device %s is on" % dev.name)
			return(True)
		else:
			self.errorLog(u"Error: PDU %s in unknown state: %s" % (dev.name, resultCode))
			return(False)
			
		
		
