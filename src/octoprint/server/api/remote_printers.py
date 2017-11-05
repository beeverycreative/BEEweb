# coding=utf-8
from __future__ import absolute_import, division, print_function

__author__ = "Marcos Gomes <mgomes@beeverycreative.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from flask import request, jsonify, make_response, url_for
from werkzeug.exceptions import BadRequest

from octoprint.server import slicingManager, printer
from octoprint.server.util.flask import restricted_access, with_revalidation_checking
from octoprint.server.api import api, NO_CONTENT

from octoprint.settings import settings as s, valid_boolean_trues

from octoprint.slicing import UnknownSlicer, SlicerNotConfigured, ProfileAlreadyExists, UnknownProfile, CouldNotDeleteProfile

import requests
import json
import base64
import datetime
import datetime, dateutil.parser


class ProdsmartAPIMethods(object):
	url = "http://app.prodsmart.com/"
	apiKey = "8fm7ahh0ukrju";
	apiSecret = "confukbj95htvkf7m85l8pbper";
	key = apiKey + ":" + apiSecret;
	b = bytearray()
	b.extend(key)
	encoding = base64.b64encode(b)
	token = ""

	def autentication(self):

		headers = {'Authorization': "Basic " + self.encoding, "Content-Type": "application/json"}
		authorizationRequest = "{ \"scopes\": [ \"productions_write\" ] }";

		myResponse = requests.post(self.url + "api/authorization", data=authorizationRequest, headers=headers)

		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				for key in jData:
					if (key == "token"):
						self.token = str(jData[key])
		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)
			return True
		print("Token: " + self.token)
		return False

	def getJobs(self, urlToCall="api/production-orders/?", all=False, notstarted=False):
		headers = {"Content-Type": "application/json"}
		if all:
			link = self.url + urlToCall + "access_token=" + self.token
		else:
			if notstarted:
				link = self.url + urlToCall + "access_token=" + self.token + "&running-status=notstarted"
			else:
				link = self.url + urlToCall + "access_token=" + self.token + "&running-status=started"
		myResponse = requests.get(link, headers=headers)
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				for key in jData:
					x = json.dumps(key)

		else:
			if myResponse.status_code == 401:
				self.autentication()
				myResponse = self.getJobs()
			else:
				# If response code is not ok (200), print the resulting http error code with description
				# myResponse.raise_for_status()
				print(myResponse.reason)
		return myResponse

	def updateOrder(self, machine, id, status=0):
		headers = {"Content-Type": "application/json"}
		# api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
		link = self.url + "api/machines/" + machine + "/production-orders/" + id + "?" + "access_token=" + self.token
		data = {"status": status}

		myResponse = requests.post(link, data=json.dumps(data), headers=headers)
		# print myResponse.request.url
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				print("The response contains {0} properties".format(len(jData)))
				for key in jData:
					x = json.dumps(key)
					print(key)
					print(key["status"])

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)

	def getProductionOrder(self, id, urlToCall="api/production-orders/"):

		headers = {"Content-Type": "application/json"}

		link = self.url + urlToCall + id + "?access_token=" + self.token
		myResponse = requests.get(link, headers=headers)
		print(myResponse.status_code)
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				print("The response contains {0} properties".format(len(jData)))
				for key in jData:
					x = json.dumps(key)
					print(key)
					print(key["status"])

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)

	def createProductionOrder(self, machines, products, start_time, end_time, workers, code, status=0):
		headers = {"Content-Type": "application/json"}
		# api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
		link = self.url + "api/production-orders/?access_token=" + self.token
		data = {"status": status,
				"products": products,
				"code": code,
				"start-date": start_time,
				"due-date": end_time,
				"workers-assigned": workers,
				"machines": machines}

		myResponse = requests.post(link, data=json.dumps(data), headers=headers)
		# print myResponse.request.url
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				return json.loads(myResponse.content)

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)

			return None

	def getPrinters(self, urlToCall="api/machines?", all=False, notstarted=False):
		headers = {"Content-Type": "application/json"}
		if all:
			link = self.url + urlToCall + "access_token=" + self.token
		else:
			if notstarted:
				link = self.url + urlToCall + "access_token=" + self.token + "&running-status=notstarted"
			else:
				link = self.url + urlToCall + "access_token=" + self.token + "&running-status=started"
		myResponse = requests.get(link, headers=headers)
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				for key in jData:
					x = json.dumps(key)

		else:
			if myResponse.status_code == 401:
				self.autentication()
				myResponse = self.getPrinters()
			else:
				# If response code is not ok (200), print the resulting http error code with description
				# myResponse.raise_for_status()
				print(myResponse.reason)
		return myResponse

	def updatePrinterNotes(self, machine, notes):

		headers = {"Content-Type": "application/json"}
		# api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
		link = self.url + "api/machines/" + machine + "/notes?access_token=" + self.token

		notes_str = json.dumps(notes, separators=(',', ':'))

		data = {"notes": notes_str}

		myResponse = requests.post(link, data=json.dumps(data), headers=headers)
		# print myResponse.request.url
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				print("The response contains {0} properties".format(len(jData)))

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)

		return

	def activateProductionOrder(self, id):

		headers = {"Content-Type": "application/json"}
		link = self.url + "api/production-orders/" + str(id) + "/activate?access_token=" + self.token

		myResponse = requests.post(link, headers=headers)

		if (myResponse.ok):
			if (myResponse.content != ""):
				return json.loads(myResponse.content)

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)

			return None

	def updateProductionOrder(self, id, status=0):
		headers = {"Content-Type": "application/json"}
		# api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
		link = self.url + "api/production-orders/" + id + "?" + "access_token=" + self.token
		data = {"status": status}

		myResponse = requests.post(link, data=json.dumps(data), headers=headers)
		# print myResponse.request.url
		if (myResponse.ok):

			# Loading the response data into a dict variable
			# json.loads takes in only binary or string variables so using content to fetch binary content
			# Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
			if (myResponse.content != ""):
				jData = json.loads(myResponse.content)
				print("The response contains {0} properties".format(len(jData)))
				for key in jData:
					x = json.dumps(key)
					print(key)
					print(key["status"])

		else:
			# If response code is not ok (200), print the resulting http error code with description
			# myResponse.raise_for_status()
			print(myResponse.reason)


@api.route("/remote/getRemotePrinters", methods=["POST"])
@restricted_access
def getRemotePrinters():

	colors= {'A101 - Transparent':{'material':'PLA','color':'ECECE7'},
			 'A102 - Blanc Gris':{'material':'PLA','color':'ECECE7'},
			 'A103 - Zinc Yellow':{'material':'PLA','color':'FBCA44'},
			 'A104 - Signal Yellow':{'material':'PLA','color':'FBCA44'},
			 'A105 - Bright Red Orange':{'material':'PLA','color':'EE6B2A'},
			 'A106 - Traffic Red':{'material':'PLA','color':'BC1B13'},
			 'A107 - Tomato Red':{'material':'PLA','color':'BC1B13'},
			 'A108 - Light Pink':{'material':'PLA','color':'BC84BA'},
			 'A109 - Traffic Purple':{'material':'PLA','color':'913071'},
			 'A110 - Violet':{'material':'PLA','color':'8C0091'},
			 'A111 - Sky Blue':{'material':'PLA','color':'007BAE'},
			 'A112 - Traffic Blue':{'material':'PLA','color':'005A8A'},
			 'A114 - Yellow Green':{'material':'PLA','color':'868A00'},
			 'A115 - Pure Green':{'material':'PLA','color':'008C33'},
			 'A116 - Chrome Green':{'material':'PLA','color':'008C33'},
			 'A117 - Chocolate Brown':{'material':'PLA','color':'8C3A09'},
			 'A118 - Telegrey':{'material':'PLA','color':'858583'},
			 'A119 - Signal Black':{'material':'PLA','color':'#000000'},
			 'A120 - Pearl Gold':{'material':'PLA','color':'806442'},
			 'A121 - Pearl Light Grey':{'material':'PLA','color':'8D9295'}}

	modelImgs = {'BEETHEFIRST':'BEETHEFIRST black background.png',
				 'BEETHEFIRST+':'BEETHEFIRST+ black background.png',
				 'BEETHEFIRST+A': 'BEETHEFIRST+A black background.png',
				 'BEEINSCHOOL': 'BEEINSCHOOL black background.png',
				 'BEEINSCHOOL A': 'BEEINSCHOOL A black background.png'}

	prod_api = ProdsmartAPIMethods()

	try:
		while prod_api.autentication():
			pass
	except Exception:
		return True

	"""
	                GET PRINTER LIST
	"""

	printerList = json.loads(prod_api.getPrinters().content)

	Info = {}
	Info['Printers'] = {}
	Info['PrintersList'] = printerList

	remotePrinters = {}

	for printer in printerList:
		# prod_api.updatePrinterNotes(printer['code'],notes)

		Info['Printers'][printer['code']] = {}
		Info['Printers'][printer['code']]['on_hold'] = 0

		notes = json.loads(printer['notes'])
		for note in notes:
			printer[note] = notes[note]

	"""
	                READ AND LIST PRODUCTION ORDERS
	"""
	jobsList = prod_api.getJobs(notstarted=False).content
	jobs = json.loads(jobsList)

	"""
	                CREATE DICT WITH PRINTER AND JOBS
	"""

	Info['jobs'] = jobs

	for job in jobs:
		due_date = dateutil.parser.parse(job['due-date'])
		for machine in job['machines']:
			Info['Printers'][machine['code']]['on_hold'] += 1
			if not 'available_at' in Info['Printers'][machine['code']].keys():
				Info['Printers'][machine['code']]['available_at'] = due_date
			else:
				if due_date > Info['Printers'][machine['code']]['available_at']:
					Info['Printers'][machine['code']]['available_at'] = due_date

	for printer in Info['Printers']:
		Info['Printers'][printer]['Ready'] = Info['Printers'][printer]['on_hold'] == 0

		remotePrinter = {}
		remotePrinter['id'] = printer['id']
		remotePrinter['Filament'] = note['material_code']
		remotePrinter['Material'] = colors[note['material_code']['material']]
		remotePrinter['rgb'] = colors[note['material_code']['color']]
		remotePrinter['model'] = note['model']
		remotePrinter['serial'] = note['serial']

		remotePrinter['imgPath'] = url_for('static', filename='img/' + modelImgs[remotePrinter['model']])

		if Info['Printers'][printer]['Ready'] == 0:
			remotePrinter['state'] = 'READY'
		else:
			remotePrinter['state'] = 'Printing'

		remotePrinter['Progress'] = '60%'

		remotePrinters[remotePrinter['id']] = remotePrinter


	remotePrinters = {}

	remotePrinter = {}
	remotePrinter['id'] = 1
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Printing'
	remotePrinter['Progress'] = '60%'
	remotePrinter['Material'] = 'PLA'
	remotePrinter['Color'] = 'Black'
	remotePrinter['rgb'] = '#000000'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 2
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'READY'
	remotePrinter['Progress'] = '100%'
	remotePrinter['Material'] = 'PETG'
	remotePrinter['Color'] = 'Transparent'
	remotePrinter['rgb'] = 'snow'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 3
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Heating'
	remotePrinter['Progress'] = '80%'
	remotePrinter['Material'] = 'Nylon'
	remotePrinter['Color'] = 'Red'
	remotePrinter['rgb'] = 'red'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 4
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Heating'
	remotePrinter['Progress'] = '80%'
	remotePrinter['Material'] = 'Nylon'
	remotePrinter['Color'] = 'Red'
	remotePrinter['rgb'] = 'red'
	remotePrinters[remotePrinter['id']] = remotePrinter

	return jsonify({
		"response": remotePrinters
	})
