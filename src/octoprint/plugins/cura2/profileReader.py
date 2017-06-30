# coding=utf-8
from __future__ import absolute_import

__author__ = "Bruno Andrade"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import json
import os
import logging

class ProfileReader(object):


	@classmethod
	def getSettingsToSlice(cls, printer, nozzle, filament, quality, overrides):
		extruder_settings = None
		from octoprint.server import slicingManager
		slicer_profile_path = slicingManager.get_slicer_profile_path("cura2")+'/'
		engine_settings = cls.getPrinterOverrides(printer, slicer_profile_path);

		if isinstance(nozzle, list) and isinstance(filament, list):
			extruder_settings = {}
			for count in range(0, len(filament)):
				extruder_settings[count] = cls.getFilamentOverrides(filament[count], printer, nozzle[count], slicer_profile_path, quality)
				extruder_settings[count] = cls.merge_dicts(extruder_settings[count], cls.getNozzleOverrides(nozzle[count], slicer_profile_path))
		else:
			filament_Overrides = cls.getFilamentOverrides(filament, printer, nozzle, slicer_profile_path, quality);
			nozzle_Overrides = cls.getNozzleOverrides(nozzle, slicer_profile_path);
			engine_settings = cls.merge_dicts(engine_settings, filament_Overrides, nozzle_Overrides)

			engine_settings = cls.overrideCustomValues(engine_settings,overrides)

		return engine_settings, extruder_settings

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

		if 'PrinterGroups' in filament_json:
			for list in filament_json['PrinterGroups']:
				if printer_id in list['group_printers']:
					if quality in list['quality']:
						overrides_Values = list['quality'][quality]

		if 'overrides' in filament_json:
			overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)

		if 'nozzles_supported' in filament_json:
			if nozzle_id not in str(filament_json['nozzles_supported']):
				print "Nozzle not supported"

		if 'inherits' in filament_json:
			overrides_Values = cls.merge_dicts(cls.getParentOverrides(filament_json['inherits'], nozzle_id, slicer_profile_path), overrides_Values)
		return overrides_Values

	@classmethod
	def getParentOverrides(cls, filament_id, nozzle_id,slicer_profile_path):
		overrides_Values = {}
		with open(slicer_profile_path +'Materials/' + filament_id + ".json") as data_file:
			filament_json = json.load(data_file)

		if 'overrides' in filament_json:
			overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)
		if 'inherits' in filament_json:
			overrides_Values = cls.merge_dicts(cls.getParentOverrides(filament_json['inherits'], nozzle_id, slicer_profile_path), overrides_Values)
		return overrides_Values

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

	@classmethod
	def pathToPrinter(cls, filament_id):
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

			if 'nozzles_supported' in filament_json:
				if str(float(nozzle_id)/1000) not in str(filament_json['nozzles_supported']):
					return False

			if 'PrinterGroups' in filament_json:
				for list in filament_json['PrinterGroups']:
					if printer_id.lower() in list['group_printers']:
						return True
		except:
			logger.exception("Error while getting Values from profile ")

		return False

	@classmethod
	def merge_dicts(cls, *dict_args):
		"""
		Given any number of dicts, shallow copy and merge into a new dict,
		precedence goes to key value pairs in latter dicts.
		"""
		result = {}
		for dictionary in dict_args:
			result.update(dictionary)
		return result

	@classmethod
	def merge_profile_key(cls, profile, key, value):
		if key in profile:
			profile[key]["default_value"] = value
		else :
			profile[key] = {'default_value': value}
		return profile
