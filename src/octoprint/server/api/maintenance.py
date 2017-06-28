# coding=utf-8
from __future__ import absolute_import
import re

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

from flask import request, make_response, jsonify, url_for

from octoprint.server import printer, printerProfileManager, NO_CONTENT
from octoprint.server.util.flask import restricted_access, get_json_command_from_request
from octoprint.server.api import api
from octoprint.settings import settings as s
from octoprint.server.api.slicing import _getSlicingProfilesData as getSlicingProfilesData

@api.route("/maintenance/start_heating", methods=["POST"])
@restricted_access
def startHeating():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	try:
		profile_name = printer.getSelectedFilamentProfile().display_name
		if "petg" in profile_name.lower() or "nylon" in profile_name.lower():
			printer.startHeating(230)
		elif "tpu" in profile_name.lower() :
			printer.startHeating(225)
		else:
			printer.startHeating()  # In the future we might pass the extruder identifier here in case of more than 1 extruder
	except:
		# if no filament in printer
		printer.startHeating()
	return NO_CONTENT

@api.route("/maintenance/cancel_heating", methods=["POST"])
@restricted_access
def cancelHeating():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.cancelHeating()

	return NO_CONTENT

@api.route("/maintenance/temperature", methods=["GET"])
def getTemperature():
	current_temp = printer.get_current_temperature()
	return jsonify({
		"temperature": current_temp
	})

@api.route("/maintenance/heating_done", methods=["POST"])
def heatingDone():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.heatingDone()

	return NO_CONTENT

@api.route("/maintenance/unload", methods=["POST"])
@restricted_access
def unloadFilament():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.unload()

	return NO_CONTENT

@api.route("/maintenance/load", methods=["POST"])
@restricted_access
def loadFilament():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.load()

	return NO_CONTENT

@api.route("/maintenance/start_calibration", methods=["POST"])
@restricted_access
def startCalibration():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.startCalibration()

	return NO_CONTENT

@api.route("/maintenance/calibration_next", methods=["POST"])
@restricted_access
def nextCalibrationStep():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.nextCalibrationStep()

	return NO_CONTENT

@api.route("/maintenance/running_calibration_test", methods=["GET"])
@restricted_access
def inCalibrationTest():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	res = printer.isRunningCalibrationTest()

	return jsonify({
		"response": res
	})

@api.route("/maintenance/start_calibration_test", methods=["POST"])
@restricted_access
def startCalibrationTest():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.startCalibrationTest()

	return NO_CONTENT

@api.route("/maintenance/cancel_calibration_test", methods=["POST"])
@restricted_access
def cancelCalibrationTest():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.cancelCalibrationTest()

	return NO_CONTENT

@api.route("/maintenance/repeat_calibration", methods=["POST"])
@restricted_access
def repeatCalibration():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	printer.startCalibration(repeat=True)

	return NO_CONTENT

@api.route("/maintenance/filament_profiles", methods=["GET"])
@restricted_access
def filamentProfiles():
	"""
	Gets the slicing profiles (Filament colors) configured for Cura engine
	:return:
	"""
	if s().get(["slicing", "cura2"]):
		default_slicer = "cura2"
	else:
		default_slicer = s().get(["slicing", "defaultSlicer"])

	return jsonify(getSlicingProfilesData(default_slicer))

@api.route("/maintenance/nozzle_sizes", methods=["GET"])
@restricted_access
def nozzleSizes():
	"""
	Gets the nozzle sizes available
	:return:
	"""
	nozzles = s().get(["nozzleTypes"])

	return jsonify(nozzles)

@api.route("/maintenance/save_filament", methods=["POST"])
@restricted_access
def saveFilament():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"filament": ["filamentStr"]
	}
	command, data, response = get_json_command_from_request(request, valid_commands)
	if response is not None:
		return response

	filamentStr = data['filamentStr']

	try:
		#Get temperature of filament in printer
		profile_name_printer = printer.getSelectedFilamentProfile().display_name
		temperature_profile_printer = 210
		if "petg" in profile_name_printer.lower() or "nylon" in profile_name_printer.lower():
			temperature_profile_printer=230
		elif "tpu" in profile_name_printer.lower() :
			temperature_profile_printer=225

		# Get temperature of filament being loaded
		temperature_new_filament =210
		if "petg" in filamentStr.lower() or "nylon" in filamentStr.lower():
			temperature_new_filament = 230
		elif "tpu" in filamentStr.lower():
			temperature_new_filament = 225

		#compare temperatures
		if (temperature_new_filament > temperature_profile_printer):
			printer.set_nozzle_temperature(temperature_new_filament)

	except Exception as e:
		print("No temperature defined for filament selected %r" % e)

	resp = printer.setFilamentString(filamentStr)

	return jsonify({
		"response": resp
	})

@api.route("/maintenance/get_filament", methods=["GET"])
@restricted_access
def getFilament():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	resp = printer.getFilamentString()

	return jsonify({
		"filament": resp
	})


@api.route("/maintenance/get_nozzles_and_filament", methods=["GET"])
@restricted_access
def getNozzlesAndFilament():
	"""
	Returns the list of available nozzles, the current selected nozzle, the current selected filament
	and the amount of filament left in spool
	:return:
	"""
	nozzle_list = s().get(["nozzleTypes"])

	if not printer.is_operational():
		return jsonify({
			"nozzle": '0.4',
			"nozzleList": nozzle_list,
			"filament": 'A023 - Black',
			"filamentInSpool": 0.0
		})

	filament = printer.getFilamentString()
	filamentInSpool = printer.getFilamentWeightInSpool()
	nozzle = printer.getNozzleSize()
	# converts the nozzle size to float
	nozzle = float(nozzle) / 1000.0

	return jsonify({
		"nozzle": nozzle,
		"nozzleList": nozzle_list,
		"filament": filament,
		"filamentInSpool": filamentInSpool
	})

@api.route("/maintenance/save_nozzle", methods=["POST"])
@restricted_access
def saveNozzle():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"nozzle": ["nozzleType"]
	}
	command, data, response = get_json_command_from_request(request, valid_commands)
	if response is not None:
		return response

	nozzle = data['nozzleType']

	if not printer.isValidNozzleSize(nozzle):
		return make_response("Invalid nozzle size", 409)

	# converts the nozzle to integer
	nozzle = int(nozzle * 1000)
	resp = printer.setNozzleSize(nozzle)

	printer_profile = printerProfileManager.get_current()
	if printer_profile is not None:
		printer_profile['extruder']['nozzleDiameter'] = nozzle
		printerProfileManager.save(printer_profile, allow_overwrite=True)
	else:
		return jsonify({
			"response": "Could not find printer profile for saving."
		})

	return jsonify({
		"response": resp
	})

@api.route("/maintenance/get_nozzle", methods=["GET"])
@restricted_access
def getSavedNozzle():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	resp = printer.getNozzleSize()
	resp = float(resp / 1000)

	return jsonify({
		"nozzle": resp
	})

@api.route("/maintenance/get_nozzle_list", methods=["GET"])
@restricted_access
def getNozzleList():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	nozzles = printer.getNozzleTypes()

	return jsonify(nozzles)


@api.route("/maintenance/get_filament_spool", methods=["GET"])
@restricted_access
def getFilamentInSpool():
	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	resp = printer.getFilamentWeightInSpool()

	return jsonify({
		"filament": resp
	})

@api.route("/maintenance/set_filament_weight", methods=["POST"])
@restricted_access
def setFilamentWeight():

	if not printer.is_operational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"filament": ["filamentWeight"]
	}
	command, data, response = get_json_command_from_request(request, valid_commands)
	if response is not None:
		return response

	filamentWeight = data['filamentWeight']

	resp = "Invalid filament weight"

	if filamentWeight and float(filamentWeight) >= 0:
		resp = printer.setFilamentInSpool(float(filamentWeight))

	return jsonify({
		"response": resp
	})
