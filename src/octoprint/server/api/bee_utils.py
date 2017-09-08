# coding=utf-8
from __future__ import absolute_import

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from octoprint.server.util.wifi_util import get_ssid_list, switch_wifi_client_mode
from octoprint.server.util.hostname_util import is_valid_hostname, update_hostname, get_hostname
from octoprint.server import printer, eventManager, NO_CONTENT
from flask import Blueprint, jsonify, request, make_response, url_for
from octoprint.settings import settings
from os import listdir
from os.path import isfile, join
from octoprint.server.util.flask import restricted_access
from octoprint.events import Events

#~~ BVC custom API
api = Blueprint("beeapi", __name__)

@api.route("/printer", methods=["GET"])
def getConnectedPrinter():

	if printer is not None:
		printer_name = printer.get_printer_name()
	else:
		printer_name = ''

	profile = printer.getCurrentProfile()

	return jsonify({
		"printer": printer_name,
		"profile": profile
	})

@api.route("/beepanel/connect", methods=["POST"])
def connectBeePanelClient():
	"""
	This method is responsible for signaling when a beepanel client connects to the server
	in order to open the connection to the printer
	:return:
	"""
	if eventManager is not None:
		eventManager.fire(Events.CLIENT_OPENED, {"remoteAddress": 'beeconnect'})

		return jsonify({"result": "SUCCESS"})
	else:
		return jsonify({"result": "Error: could not signal beepanel connection"})

@api.route("/printer/serial", methods=["GET"])
def printerSerialNumber():
	if printer is not None:
		if not printer.is_operational():
			return make_response("Printer is not operational", 409)

		return jsonify({ "serial": printer.get_printer_serial()})
	else:
		return make_response("Printer is not operational", 409)

@api.route("/wifi/list", methods=["GET"])
def getAvailableHotspots():

	networks = get_ssid_list('wlan0')

	return jsonify({
		"wifi_networks": networks
	})

@api.route("/hostname", methods=["GET"])
def getCurrentHostname():

	hostname = get_hostname()

	return jsonify({
		"hostname": hostname
	})


@api.route("/netconfig/save", methods=["POST"])
def saveNetworkConfig():

	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	data = request.json
	network_name = data['network']
	password = data['password']
	custom_ssid = data['custom_ssid']

	hidden_network = False
	if custom_ssid:  # If a custom hidden SSID was specified uses it as the network name
		network_name = custom_ssid
		hidden_network = True

	# validates input data
	if network_name is None:
		return make_response("Invalid network name parameter.", 406)

	# Tries to switch the Wifi configuration to client mode
	switch_wifi_client_mode(network_name, password, hidden_network)

	return NO_CONTENT

@api.route("/hostname/save", methods=["POST"])
def hostnameSave():

	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	data = request.json
	new_hostname = data['hostname']

	if not new_hostname or not is_valid_hostname(new_hostname):
		return make_response("Invalid hostname parameter.", 406)

	# Updates the hostname
	# NOTE: This operation will force the server to reboot
	update_hostname(new_hostname)

	return NO_CONTENT

@api.route("/firmware/current/version", methods=["GET"])
def getCurrentFirwareVersion():

	version = printer.getCurrentFirmware()

	return jsonify({
		"version": version
	})

@api.route("/firmware/latest/version", methods=["GET"])
def getLatestFirwareVersion():

	version = '0.0.0' # default base version
	firmware_path = settings().getBaseFolder('firmware')
	if printer is not None:
		printer_name = printer.get_printer_name()

		if printer_name:
			printer_name = printer_name.replace(' ','')
			firmware_files = [f for f in listdir(firmware_path) if isfile(join(firmware_path, f))]

			for ff in firmware_files:
				file_parts = ff.split('-')
				if file_parts[1] == printer_name:
					version = file_parts[2].replace('.BIN', '')
					break

	return jsonify({
		"version": version
	})

@api.route("/firmware/<string:printer_name>/<string:version>", methods=["GET"])
def getFirmwareFileLink(printer_name, version):
	"""
	Gets the download link for a firmware file of a specific printer and version.
	If the file does not exist returns a NO_CONTENT response

	:param printer_name: The printer name must be the name without spaces. E.g: BEETHEFIRSTPLUSA
	:param version:
	:return:
	"""
	filename = 'BEEVC-' + printer_name + '-' + version + '.BIN'

	if printer_name:
		firmware_path = settings().getBaseFolder('firmware')

		for ff in listdir(firmware_path):
			if isfile(join(firmware_path, ff)):

				if ff == filename:
					link = url_for("index", _external=True) + "firmware/" + filename

					return jsonify({
						"file": link
					})

	return NO_CONTENT

@api.route("/print_from_memory", methods=["POST"])
@restricted_access
def printMemoryFile():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.printFromMemory()

	return NO_CONTENT

@api.route("/save_user_feedback", methods=["POST"])
@restricted_access
def saveUserFeedback():
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	data = request.json
	print_success = bool(data['print_success'])
	print_rating = data['print_rating']
	observations = data['observations']

	res, msg = printer.saveUserFeedback(print_success, print_rating, observations)

	return jsonify({
		"success": res,
		"message": msg
	})

@api.route("/no_user_feedback", methods=["POST"])
@restricted_access
def noUserFeedback():

	res, msg = printer.saveUserFeedback()

	return jsonify({
		"success": res,
		"message": msg
	})

@api.route("/save_model_information", methods=["POST"])
@restricted_access
def saveModelInformation():
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	data = request.json
	models_info = data['models_info']

	res = printer.saveModelsInformation(models_info)

	return jsonify({
		"success": res
	})
