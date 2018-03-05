# coding=utf-8
from __future__ import absolute_import, division, print_function

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from flask import request, jsonify, make_response, url_for
from werkzeug.exceptions import BadRequest

from octoprint.server import slicingManager, printer
from octoprint.server.util.flask import restricted_access, with_revalidation_checking
from octoprint.server.api import api, NO_CONTENT

from octoprint.settings import settings as s, valid_boolean_trues

from octoprint.slicing import UnknownSlicer, SlicerNotConfigured, ProfileAlreadyExists, UnknownProfile, CouldNotDeleteProfile


def _lastmodified(configured):
	if configured:
		slicers = slicingManager.configured_slicers
	else:
		slicers = slicingManager.registered_slicers

	lms = [0]
	for slicer in slicers:
		lms.append(slicingManager.profiles_last_modified(slicer))

	return max(lms)


def _etag(configured, lm=None):
	if lm is None:
		lm = _lastmodified(configured)

	import hashlib
	hash = hashlib.sha1()
	hash.update(str(lm))

	if configured:
		hash.update(repr(sorted(slicingManager.configured_slicers)))
	else:
		hash.update(repr(sorted(slicingManager.registered_slicers)))

	hash.update("v2") # increment version if we change the API format

	return hash.hexdigest()


@api.route("/slicing", methods=["GET"])
@with_revalidation_checking(etag_factory=lambda lm=None: _etag(request.values.get("configured", "false") in valid_boolean_trues, lm=lm),
                            lastmodified_factory=lambda: _lastmodified(request.values.get("configured", "false") in valid_boolean_trues),
                            unless=lambda: request.values.get("force", "false") in valid_boolean_trues)
def slicingListAll():
	from octoprint.filemanager import get_extensions

	default_slicer = s().get(["slicing", "defaultSlicer"])

	if "configured" in request.values and request.values["configured"] in valid_boolean_trues:
		slicers = slicingManager.configured_slicers
	else:
		slicers = slicingManager.registered_slicers

	result = dict()
	for slicer in slicers:
		try:
			slicer_impl = slicingManager.get_slicer(slicer, require_configured=False)

			extensions = set()
			for source_file_type in slicer_impl.get_slicer_properties().get("source_file_types", ["model"]):
				extensions = extensions.union(get_extensions(source_file_type))

			result[slicer] = dict(
				key=slicer,
				displayName=slicer_impl.get_slicer_properties()["name"],
				sameDevice=slicer_impl.get_slicer_properties()["same_device"],
				default=default_slicer == slicer,
				configured=slicer_impl.is_slicer_configured(),
				profiles=_getSlicingProfilesData(slicer),
				extensions=dict(
					source=list(extensions),
					destination=slicer_impl.get_slicer_properties().get("destination_extensions", ["gco", "gcode", "g"])
				)
			)
		except (UnknownSlicer, SlicerNotConfigured):
			# this should never happen
			pass

	return jsonify(result)

@api.route("/slicing/<string:slicer>/getRawMaterial", methods=["GET"])
def slicingGetRawMaterial(slicer):
	try:
		profile = slicingManager.load_raw_material(slicer)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)

	return jsonify(profile)

@api.route("/slicing/<string:slicer>/getMaterial/<string:name>", methods=["GET"])
def slicingGetMaterial(slicer, name):
	try:
		profile = slicingManager.load_material(slicer,name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)

	return jsonify(profile)

@api.route("/slicing/<string:slicer>/getRawProfile/<string:material>", methods=["GET"])
def slicingGetRawProfile(slicer, material):
	try:
		profile = slicingManager.load_raw_profile(slicer,material)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)

	return jsonify(profile)

@api.route("/slicing/<string:slicer>/confirmEdition/<string:name>/<string:quality>/<string:nozzle>", methods=["PUT"])
def slicingEditSlicerProfile(slicer, name, quality, nozzle):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)
	try:
		json_data = request.json
		# slicingManager.edit_profile(slicer, name, printer_id, quality)
		slicingManager.edit_profile(slicer, name , json_data , quality,nozzle)
		return NO_CONTENT
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)

@api.route("/slicing/<string:slicer>/saveMaterial", methods=["PUT"])
def slicingSaveMaterial(slicer):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)
	try:
		json_data = request.json
		slicingManager.save_new_material(slicer, json_data )
		return NO_CONTENT
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)


@api.route("/slicing/<string:slicer>/saveRawProfile", methods=["PUT"])
def slicingSaveRawProfile(slicer):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)
	try:
		json_data = request.json
		slicingManager.save_new_profile(slicer, json_data )
		return NO_CONTENT
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)


@api.route("/slicing/<string:slicer>/saveMaterial/<string:name>", methods=["PUT"])
def slicingSaveMaterialEdition(slicer, name):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)
	try:
		json_data = request.json
		slicingManager.save_material(slicer, json_data,name)
		return NO_CONTENT
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)


@api.route("/slicing/<string:slicer>/getSingleProfile/<string:name>/<string:quality>/<string:nozzle>", methods=["GET"])
def slicingGetSingleProfile(slicer, name, quality,nozzle):
	try:
		profile = slicingManager.load_single_profile(slicer, name, quality, nozzle)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)
	return jsonify(profile)

@api.route("/slicing/<string:slicer>/getOptions", methods=["GET"])
def slicingGetOptions(slicer):
	try:
		profile = slicingManager.load_options(slicer)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)
	return  jsonify(profile)

@api.route("/slicing/<string:slicer>/getProfileQuality/<string:name>", methods=["GET"])
def slicingGetProfileQuality(slicer, name):
	try:
		profile = slicingManager.load_profile_quality( slicer, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)
	return  jsonify(profile)




@api.route("/slicing/<string:slicer>/profiles", methods=["GET"])
def slicingListSlicerProfiles(slicer):
	configured = False
	if "configured" in request.values and request.values["configured"] in valid_boolean_trues:
		configured = True

	try:
		return jsonify(_getSlicingProfilesData(slicer, require_configured=configured))
	except (UnknownSlicer, SlicerNotConfigured):
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)

@api.route("/slicing/<string:slicer>/materials", methods=["GET"])
def slicingListSlicerMaterials(slicer):
	configured = False
	if "configured" in request.values and request.values["configured"] in valid_boolean_trues:
		configured = True
	try:
		return jsonify(_getSlicingMaterialData(slicer, require_configured=configured))
	except (UnknownSlicer, SlicerNotConfigured):
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)

@api.route("/slicing/<string:slicer>/inheritsMaterials/<string:material>", methods=["GET"])
def slicingListInheritsMaterials(slicer,material):
	configured = False
	if "configured" in request.values and request.values["configured"] in valid_boolean_trues:
		configured = True
	try:
		return jsonify(_getSlicingInheritsMaterials(slicer, material , require_configured=configured))
	except (UnknownSlicer, SlicerNotConfigured):
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)

@api.route("/slicing/<string:slicer>/getMaterialInherits/<string:material>", methods=["GET"])
def slicingGetInheritsMaterials(slicer,material):
	try:
		profile = slicingManager.load_inherits_material(slicer,material)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)
	return jsonify(profile)


@api.route("/slicing/<string:slicer>/profiles/<string:name>", methods=["GET"])
def slicingGetSlicerProfile(slicer, name):
	try:
		profile = slicingManager.load_profile(slicer, name, require_configured=False)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile not found", 404)

	result = _getSlicingProfileData(slicer, name, profile)
	result["data"] = profile.data
	return jsonify(result)



@api.route("/slicing/<string:slicer>/profiles/<string:name>", methods=["PUT"])
@restricted_access
def slicingAddSlicerProfile(slicer, name):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	try:
		json_data = request.json
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)

	data = dict()
	display_name = None
	description = None
	if "data" in json_data:
		data = json_data["data"]
	if "displayName" in json_data:
		display_name = json_data["displayName"]
	if "description" in json_data:
		description = json_data["description"]

	try:
		profile = slicingManager.save_profile(slicer, name, data,
		                                      allow_overwrite=True, display_name=display_name, description=description)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)

	result = _getSlicingProfileData(slicer, name, profile)
	r = make_response(jsonify(result), 201)
	r.headers["Location"] = result["resource"]
	return r

@api.route("/slicing/<string:slicer>/profiles/<string:name>", methods=["PATCH"])
@restricted_access
def slicingPatchSlicerProfile(slicer, name):
	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content-type JSON", 400)

	try:
		profile = slicingManager.load_profile(slicer, name, require_configured=False)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except UnknownProfile:
		return make_response("Profile {name} for slicer {slicer} not found".format(**locals()), 404)

	try:
		json_data = request.json
	except BadRequest:
		return make_response("Malformed JSON body in request", 400)

	data = dict()
	display_name = None
	description = None
	if "data" in json_data:
		data = json_data["data"]
	if "displayName" in json_data:
		display_name = json_data["displayName"]
	if "description" in json_data:
		description = json_data["description"]

	saved_profile = slicingManager.save_profile(slicer, name, profile,
	                                            allow_overwrite=True,
	                                            overrides=data,
	                                            display_name=display_name,
	                                            description=description)

	from octoprint.server.api import valid_boolean_trues
	if "default" in json_data and json_data["default"] in valid_boolean_trues:
		slicingManager.set_default_profile(slicer, name, require_exists=False)

	return jsonify(_getSlicingProfileData(slicer, name, saved_profile))

@api.route("/slicing/<string:slicer>/profiles/<string:name>", methods=["DELETE"])
@restricted_access
def slicingDelSlicerProfile(slicer, name):
	try:
		slicingManager.delete_profile(slicer, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response("Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer, cause=str(e.cause)), 500)

	return NO_CONTENT

@api.route("/slicing/<string:slicer>/deleteMaterial/<string:name>", methods=["DELETE"])
@restricted_access
def slicingDelMaterialProfile(slicer, name):
	try:
		slicingManager.delete_material(slicer, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response("Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer, cause=str(e.cause)), 500)

	return NO_CONTENT

@api.route("/slicing/<string:slicer>/delete_quality/<string:quality>/<string:name>", methods=["DELETE"])
@restricted_access
def slicingDelQualityInProfile(slicer,quality,name):
	try:
		slicingManager.delete_quality_material(slicer,quality,name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response(
			"Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer,
																					 cause=str(e.cause)), 500)
	return NO_CONTENT


@api.route("/slicing/<string:slicer>/change_quality_profile/<string:filament_id>/<string:quality>/<string:name>", methods=["POST"])
@restricted_access
def slicingChangeQualityProfile(slicer,filament_id,quality,name):
	try:
		slicingManager.change_quality_name(slicer, filament_id,quality, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response(
			"Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer,
																					 cause=str(e.cause)), 500)
	return NO_CONTENT


@api.route("/slicing/<string:slicer>/copy_quality_profile/<string:filament_id>/<string:quality>/<string:name>", methods=["POST"])
@restricted_access
def slicingCopyQualityProfile(slicer,filament_id,quality,name):
	try:
		slicingManager.copy_quality_name(slicer, filament_id,quality, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response(
			"Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer,
																					 cause=str(e.cause)), 500)
	return NO_CONTENT

@api.route("/slicing/<string:slicer>/new_quality/<string:filament_id>/<string:quality>", methods=["POST"])
@restricted_access
def slicingNewQuality(slicer,filament_id,quality):
	try:
		slicingManager.new_quality(slicer, filament_id,quality)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response(
			"Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer,
																					 cause=str(e.cause)), 500)
	return NO_CONTENT


@api.route("/slicing/<string:slicer>/duplicate_profile/<string:name>", methods=["POST"])
@restricted_access
def pluginDuplicateProfile(slicer,name):
	try:
		result = slicingManager.duplicate_plugin_profile(slicer, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response(
			"Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer,
																					 cause=str(e.cause)), 500)
	return NO_CONTENT

@api.route("/slicing/<string:slicer>/profiles/<string:name>", methods=["POST"])
@restricted_access
def slicingDuplicateSlicerProfile(slicer, name):
	try:
		result = slicingManager.duplicate_profile(slicer, name)
	except UnknownSlicer:
		return make_response("Unknown slicer {slicer}".format(**locals()), 404)
	except CouldNotDeleteProfile as e:
		return make_response("Could not delete profile {profile} for slicer {slicer}: {cause}".format(profile=name, slicer=slicer, cause=str(e.cause)), 500)

	return NO_CONTENT

def _getSlicingProfilesData(slicer, require_configured=False):
	result = dict()
	if slicer == "curaX":
		profiles = slicingManager.all_profiles_list_json(slicer,
													require_configured=require_configured,
													nozzle_size=printer.getNozzleTypeString().replace("nz", ""),
													from_current_printer=True)
		for name, profile in profiles.items():
			result[name] = _getSlicingProfileData(slicer, name, profile)
	else:
		profiles = slicingManager.all_profiles_list(slicer,
													require_configured=require_configured,
													from_current_printer=True)
		# gets the nozzle size to filter the slicing profiles by nozzle type
		nozzle = printer.getNozzleTypeString()
		printer_name = printer.getPrinterNameNormalized()

		for name, profile in profiles.items():
			if nozzle is not None and not nozzle in name:
				continue

			if printer_name is not None and not printer_name in name:
				continue

			result[name] = _getSlicingProfileData(slicer, name, profile)
	return result


def _getSlicingMaterialData(slicer, require_configured = False):
	result = dict()
	if slicer == "curaX":
		profiles = slicingManager.all_materials_list_json(slicer,
													require_configured=require_configured,
													nozzle_size=printer.getNozzleTypeString().replace("nz", ""),
													from_current_printer=True)
		for name, profile in profiles.items():
			result[name] = _getSlicingProfileData(slicer, name, profile)
	return result

def _getSlicingInheritsMaterials(slicer, material_id, require_configured = False):
	result = dict()
	if slicer == "curaX":
		profiles = slicingManager.all_Inherits_materials_list_json(slicer,material_id,
													require_configured=require_configured,
													nozzle_size=printer.getNozzleTypeString().replace("nz", ""),
													from_current_printer=True)
		for name, profile in profiles.items():
			result[name] = _getSlicingProfileData(slicer, name, profile)
	return result


def _getSlicingProfileData(slicer, name, profile, brand=None):
	defaultProfiles = s().get(["slicing", "defaultProfiles"])
	result = dict(
		key=name,
		default=defaultProfiles and slicer in defaultProfiles and defaultProfiles[slicer] == name,
		resource=url_for(".slicingGetSlicerProfile", slicer=slicer, name=name, _external=True)
	)
	if profile.display_name is not None:
		result["displayName"] = profile.display_name
	if profile.description is not None:
		result["description"] = profile.description
	if profile.brand is not None:
		result["brand"] = profile.brand
	return result
