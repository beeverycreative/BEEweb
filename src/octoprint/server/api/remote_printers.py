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
			print
			myResponse.reason
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
				print (myResponse.reason)

		return myResponse

@api.route("/remote/getRemotePrinters", methods=["POST"])
@restricted_access
def getRemotePrinters():

	prod_api = ProdsmartAPIMethods()

	try:
		while prod_api.autentication():
			pass
	except Exception:
		return True

	jobsList = prod_api.getJobs(notstarted=False).content
	jobs = json.loads(jobsList)


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
