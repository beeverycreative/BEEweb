# coding=utf-8
from __future__ import absolute_import

__author__ = "Bruno Andrade"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import json
import os
import logging

class ProfileReader(object):


	# Get setting for slicing using all profiles: printer, nozzle filament, quality profiles
	# Get from each profile the overrides and also in is parent
	@classmethod
	def getSettingsToSlice(cls, printer, nozzle, filament, quality, overrides):
		extruder_settings = None
		from octoprint.server import slicingManager
		slicer_profile_path = slicingManager.get_slicer_profile_path("cura2")+'/'
		engine_settings = cls.getPrinterOverrides(printer, slicer_profile_path);

		#Check if it is a printer with more than one extruder
		if isinstance(nozzle, list) and isinstance(filament, list):
			extruder_settings = {}
			#for each extruder
			for count in range(0, len(filament)):
				# get filament and parent overrides
				extruder_settings[count] = cls.getFilamentOverrides(filament[count], printer, nozzle[count], slicer_profile_path, quality)
				# get nozzle overrides
				extruder_settings[count] = cls.merge_dicts(extruder_settings[count], cls.getNozzleOverrides(nozzle[count], slicer_profile_path))

		# if single extruder
		else:
			# get filament and parent overrides
			filament_Overrides = cls.getFilamentOverrides(filament, printer, nozzle, slicer_profile_path, quality);
			# get nozzle overrides
			nozzle_Overrides = cls.getNozzleOverrides(nozzle, slicer_profile_path);
			# merge everything toghether
			engine_settings = cls.merge_dicts(engine_settings, filament_Overrides, nozzle_Overrides)
			# merge interface overrides
			engine_settings = cls.overrideCustomValues(engine_settings,overrides)

		return engine_settings, extruder_settings

	# Connect interface choises with curaEngine 2 parameters
	# Interfaces choises are: fill_density, platform_adhesion and support
	@classmethod
	def overrideCustomValues(cls, engine_settings, overrides):
		for field in overrides:
			if field == "fill_density":
				engine_settings = cls.merge_profile_key(engine_settings, "infill_sparse_density", overrides[field])

			if field == "platform_adhesion":
				if overrides[field] in ["none", "brim", "raft", "skirt"]:
					engine_settings = cls.merge_profile_key(engine_settings, "adhesion_type", overrides[field])

			if field == "support":
				if overrides[field] in [ "none" "everywhere", "buildplate"]:
					engine_settings = cls.merge_profile_key(engine_settings, "support_type", overrides[field])
					if overrides[field] == "buildplate":
						engine_settings = cls.merge_profile_key(engine_settings, "support_enable", True)
					elif overrides[field] == "everywhere":
						engine_settings = cls.merge_profile_key(engine_settings, "support_enable", True)
						engine_settings = cls.merge_profile_key(engine_settings, "support_bottom_distance", "0.15")
		return engine_settings

	# get Printer Overrides
	@classmethod
	def getPrinterOverrides(cls, printer_id, slicer_profile_path):
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")] :
				continue

			with open(slicer_profile_path +'Printers/' + entry) as data_file:
				printer_json = json.load(data_file)

		return printer_json['overrides']

	# get Nozzle Overrides
	@classmethod
	def getNozzleOverrides(cls, nozzle_id, slicer_profile_path):
		for entry in os.listdir(slicer_profile_path + "Nozzles/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if nozzle_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path +'Nozzles/' + entry) as data_file:
				nozzle_json = json.load(data_file)

		return nozzle_json['overrides']

	# get Filament and parents Overrides
	# Must check in Quality folder for default profiles and Variants for user profiles
	@classmethod
	def getFilamentOverrides(cls, filament_id, printer_id, nozzle_id, slicer_profile_path, quality=None):
		overrides_Values = {}
		custom = True
		for entry in os.listdir(slicer_profile_path + "Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path +'Quality/' + entry) as data_file:
				filament_json = json.load(data_file)
				custom = False
		if custom:
			for entry in os.listdir(slicer_profile_path + "Variants/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path +'Variants/' + entry) as data_file:
					filament_json = json.load(data_file)

		# check if printer is compatible
		if 'PrinterGroups' in filament_json:
			for list in filament_json['PrinterGroups']:
				if printer_id in list['group_printers']:
					if quality in list['quality']:
						overrides_Values = list['quality'][quality]

		# check for overrides that do not depend on quality
		if 'overrides' in filament_json:
			overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)

		# check if nozzle in printer is compatible
		if 'nozzles_supported' in filament_json:
			if nozzle_id not in str(filament_json['nozzles_supported']):
				print "Nozzle not supported"

		# check if it was parent, if so, get overrides
		if 'inherits' in filament_json:
			overrides_Values = cls.merge_dicts(cls.getParentOverrides(filament_json['inherits'], nozzle_id, slicer_profile_path), overrides_Values)
		return overrides_Values

	# Get parent overrides
	# all parents are in materials folder
	@classmethod
	def getParentOverrides(cls, filament_id, nozzle_id,slicer_profile_path):
		overrides_Values = {}
		with open(slicer_profile_path +'Materials/' + filament_id + ".json") as data_file:
			filament_json = json.load(data_file)

		# check for overrides
		if 'overrides' in filament_json:
			overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)
		# check if it was parent, if so, get overrides
		if 'inherits' in filament_json:
			overrides_Values = cls.merge_dicts(cls.getParentOverrides(filament_json['inherits'], nozzle_id, slicer_profile_path), overrides_Values)
		return overrides_Values


	# get values in header
	# in printer: id, name, metadata, electric_consumption, machine_cost, nozzles_supported, inherits
	@classmethod
	def getFilamentHeader(cls, header_id, printer_id, slicer_profile_path):
		header_value = None
		custom = True
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")] :
				continue

			with open(slicer_profile_path +'Printers/' + entry) as data_file:
				printer_json = json.load(data_file)


		if header_id in printer_json:
			header_value = printer_json[header_id]

		return header_value

	# get values in header
	# in filament: id, name, brand, color, inherits, nozzles_supported, unload_temperature, cost
	@classmethod
	def getFilamentHeader(cls, header_id, filament_id, slicer_profile_path):
		header_value = None
		custom = True
		for entry in os.listdir(slicer_profile_path + "Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path +'Quality/' + entry) as data_file:
				filament_json = json.load(data_file)
				custom = False
		if custom:
			for entry in os.listdir(slicer_profile_path + "Variants/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path +'Variants/' + entry) as data_file:
					filament_json = json.load(data_file)

		if header_id in filament_json:
			header_value = filament_json[header_id]

		if header_value is None and 'inherits' in filament_json:
			header_value = cls.getParentHeader(header_id, filament_json['inherits'], slicer_profile_path)
		return header_value

	@classmethod
	def getParentHeader(cls, header_id, filament_id, slicer_profile_path):
		header_value = None
		with open(slicer_profile_path +'Materials/' + filament_id + ".json") as data_file:
			filament_json = json.load(data_file)

		if header_id in filament_json:
			header_value = filament_json[header_id]
		if header_value is None and 'inherits' in filament_json:
			header_value = cls.getParentHeader(header_id, filament_json['inherits'], slicer_profile_path)
		return header_value

	#Get local path to filament
	@classmethod
	def pathToFilament(cls, filament_id):
		from octoprint.server import slicingManager
		slicer_profile_path = slicingManager.get_slicer_profile_path("cura2")
		custom = True
		for entry in os.listdir(slicer_profile_path + "/Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			return slicer_profile_path + "/Quality/" + entry
		if custom:
			for entry in os.listdir(slicer_profile_path + "/Variants/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				return slicer_profile_path + "/Variants/" + entry
		return None

	#check if printer(printer_id) with a nozzle size (nozzle_id) on extruder can use a especific filament(filament_id)
	@classmethod
	def isPrinterAndNozzleCompatible(cls, filament_id, printer_id, nozzle_id):
		# check if printer is can use this filament profile
		from octoprint.server import slicingManager
		logger = logging.getLogger("octoprint.plugin.cura2.profileReader")
		slicer_profile_path= slicingManager.get_slicer_profile_path("cura2")
		try:
			#check nozzle
			for entry in os.listdir(slicer_profile_path + "/Printers/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")]:
					continue

				with open(slicer_profile_path + "/Printers/" + entry) as data_file:
					printer_json = json.load(data_file)

					if 'nozzles_supported' in printer_json:
						if str(float(nozzle_id) / 1000) not in str(printer_json['nozzles_supported']):
							return False

			#Check filament with nozzle
			custom = True
			for entry in os.listdir(slicer_profile_path + "/Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + "/Quality/"+ entry) as data_file:
					filament_json = json.load(data_file)
					custom = False
			if custom:
				for entry in os.listdir(slicer_profile_path + "/Variants/"):
					if not entry.endswith(".json"):
						# we are only interested in profiles and no hidden files
						continue

					if filament_id.lower() not in entry.lower():
						continue

					# creates a shallow slicing profile
					with open(slicer_profile_path + "/Variants/" + entry) as data_file:
						filament_json = json.load(data_file)

			#Check if nozzle is supported
			if 'nozzles_supported' in filament_json:
				if str(float(nozzle_id)/1000) not in str(filament_json['nozzles_supported']):
					return False

			# Check if printer is supported
			if 'PrinterGroups' in filament_json:
				for list in filament_json['PrinterGroups']:
					if printer_id.lower() in list['group_printers']:
						return True
		except:
			logger.exception("Error while getting Values from profile ")

		return False

	# Given any number of dicts, shallow copy and merge into a new dict, precedence goes to key value pairs in latter dicts.
	@classmethod
	def merge_dicts(cls, *dict_args):
		result = {}
		for dictionary in dict_args:
			result.update(dictionary)
		return result

	# Add or merge key in parameters profile list
	@classmethod
	def merge_profile_key(cls, profile, key, value):
		if key in profile:
			profile[key]["default_value"] = value
		else :
			profile[key] = {'default_value': value}
		return profile
