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
from octoprint.slicing import SlicingManager
from octoprint.settings import settings

@api.route("/maintenance/start_heating", methods=["POST"])
@restricted_access
def startHeating():
    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    selected_filament = None
    data = request.json
    if 'selected_filament' in data:
        selected_filament = data['selected_filament']

    if selected_filament is None:
        target_temp = printer.startHeating()
    else:
        # In the future we might pass the extruder identifier here in case of more than 1 extruder
        target_temp = printer.startHeating(selected_filament)

    return jsonify({
        "target_temperature": target_temp
    })

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


@api.route("/maintenance/finish_extruder_maintenance", methods=["POST"])
@restricted_access
def finishExtruderMaintenance():
    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    printer.finishExtruderMaintenance()

    return NO_CONTENT


@api.route("/maintenance/is_extruder_calibration_required", methods=["GET"])
@restricted_access
def isExtruderCalibrationRequired():
    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    resp = printer.isExtruderCalibrationRequired()

    return jsonify({"response": resp})


@api.route("/maintenance/extrudeCalibrationAmount", methods=["POST"])
@restricted_access
def extrudeCalibrationAmount():

    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    printer.extrude(250, feedrate=240)

    return NO_CONTENT

@api.route("/maintenance/resetExtruderSteps", methods=["POST"])
@restricted_access
def resetExtruderSteps():

    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    resp = printer.setExtruderStepsMM(measuredFilamentInput=None)

    return jsonify({"response": resp})

@api.route("/maintenance/defineExtruderSteps", methods=["POST"])
@restricted_access
def defineExtruderSteps():

    if not printer.is_operational():
        return make_response("Printer is not operational", 409)

    valid_commands = {
        "defineSteps": []
    }

    command, data, response = get_json_command_from_request(request, valid_commands)
    if response is not None:
        return response

    if 'Info' in data and len(data['Info']) == 2:
        selected_filament = data['Info'][1]
        measuredFilamentInput = data['Info'][0]

        resp = printer.setExtruderStepsMM(measuredFilamentInput=measuredFilamentInput,extrudedAmmount=250)
    else:
        resp = "Invalid input arguments."

    return jsonify({"response": resp})
