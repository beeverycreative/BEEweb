# coding=utf-8
from __future__ import absolute_import

__author__ = "Bruno Andrade"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import json
import os
import logging
import copy

class ProfileReader(object):

	# Profile in "Variants" override default profiles with the same name (in folder "Quality") "
	r"""
	ProfileReader Class

	This class reads json profiles of BEEVERYCREATIVE


	getSettingsToSlice					Get setting for slicing using all profiles: printer, nozzle filament, quality profiles

	overrideCustomValues				Connect interface choises with curaEngine 2 parameters
	getPrinterJson  					get Printer Overrides
	getPrinterOverrides					get Printer Overrides

	getNozzleOverrides					get Nozzle Overrides

	getFilamentOverrides 				get Filament and parents Overrides

	getParentOverrides							custom = True
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
						filament_json = json.load(data_file)	Get parent overrides. Because all parents are in materials folder

	getPrinterHeader					get values in header(id, name, metadata, electric_consumption, machine_cost, nozzles_supported, inherits)

	getFilamentHeader  					get values in header(id, name, brand, color, inherits, nozzles_supported, unload_temperature, cost)

	getParentHeader

	pathToFilament						Get local path to filament

	isPrinterAndNozzleCompatible		check if printer(printer_id) with a nozzle size (nozzle_id) on extruder can use a especific filament

	merge_dicts							Given any number of dicts, shallow copy and merge into a new dict, precedence goes to key value pairs in latter dicts.

	merge_profile_key                   Add or merge key in parameters profile list

	"""


	# Get setting for slicing using all profiles: printer, nozzle filament, quality profiles
	# Get from each profile the overrides and also in is parent
	@classmethod
	def getSettingsToSlice(cls, printer, nozzle, filament, quality, overrides):
		extruder_settings = None
		from octoprint.server import slicingManager
		profile_path = slicingManager.get_slicer_profile_path("curaX")+'/'

		#LOAD MACHINE DEFINITIONS
		machine_json = cls.getPrinterJsonByFileName(name=printer, slicer_profile_path=profile_path)
		inheritsList = []
		inheritPrinter = machine_json['inherits']
		done = False
		engine_settings = {}

		while not done:
			if inheritPrinter != 'fdmprinter':
				inheritsList.append(copy.copy(machine_json))
				machine_json = cls.getPrinterJsonFileByid(id=inheritPrinter, slicer_profile_path=profile_path)
				inheritPrinter = machine_json['inherits']
			else:
				inheritsList.append(machine_json)
				done = True

		raw_settings = None

		#Retrieve definitions from files and its inherits based in its groups
		for i in reversed(inheritsList):
			if raw_settings is None:
				raw_settings = i['overrides'].copy()
			else:
				for key in i['overrides'].keys():
					if key not in raw_settings.keys():
						raw_settings[key] = {}
					raw_settings[key].update(i['overrides'][key])

		# Check if it is a printer with more than one extruder
		# TODO Edit dictionaries merge for multi extruder printers
		if isinstance(nozzle, list) and isinstance(filament, list):
			extruder_settings = {}
			#for each extruder
			for count in range(0, len(filament)):
				# get filament and parent overrides
				extruder_settings[count] = cls.getFilamentOverrides(filament[count], printer, nozzle[count], profile_path, quality)
				# get nozzle overrides
				extruder_settings[count] = cls.merge_dicts(extruder_settings[count], cls.getNozzleOverrides(nozzle[count], profile_path))

		# if single extruder
		else:
			# get filament and parent overrides
			filament_Overrides = cls.getFilamentOverrides(filament, printer, nozzle, profile_path, quality)
			# get nozzle overrides
			nozzle_Overrides = cls.getNozzleOverrides(nozzle, profile_path)

			# merge everything together
			for key in filament_Overrides.keys():
				if key not in raw_settings.keys():
					raw_settings[key] = {}
				raw_settings[key].update(filament_Overrides[key])
			for key in nozzle_Overrides.keys():
				if key not in raw_settings.keys():
					raw_settings[key] = {}
				raw_settings[key].update(nozzle_Overrides[key])
			#engine_settings = cls.merge_dicts(engine_settings, filament_Overrides, nozzle_Overrides)
			# merge interface overrides

			for key in raw_settings.keys():
				if 'default_value' in raw_settings[key].keys():
					engine_settings[key] = raw_settings[key]
				else:
					for k in raw_settings[key].keys():
						if 'default_value' in raw_settings[key][k].keys():
							engine_settings[k] = raw_settings[key][k]

			interface_overrrides = cls.overrideCustomValues(engine_settings,overrides)
			# merge interface overrides
			engine_settings.update(interface_overrrides)

		return engine_settings, extruder_settings

	# Connect interface choices with curaEngine 2 parameters
	# Interfaces choices are: fill_density, platform_adhesion and support
	@classmethod
	def overrideCustomValues(cls, engine_settings,overrides):

		settings = {}
		for field in overrides:
			if field == "fill_density":
				settings['infill_sparse_density'] = {'default_value' : overrides[field]}

				infill_line_width = engine_settings['infill_line_width']['default_value']

				multiplier = 1
				if engine_settings['infill_pattern']['default_value'] == 'grid':
					multiplier = 2
				elif engine_settings['infill_pattern']['default_value'] in ['triangles','cubic','cubicsubdiv']:
					multiplier = 3
				elif engine_settings['infill_pattern']['default_value'] in ['tetrahedral','quarter_cubic']:
					multiplier = 2
				elif engine_settings['infill_pattern']['default_value'] in ['cross','cross_3d']:
					multiplier = 1

				infill_line_dist = (multiplier * infill_line_width * 100) / float(overrides[field])
				settings['infill_line_distance'] = {'default_value': infill_line_dist}


				#engine_settings = cls.merge_profile_key(engine_settings, "infill_sparse_density", overrides[field])

			if field == "platform_adhesion":
				if overrides[field] in ["none", "brim", "raft", "skirt"]:
					settings['adhesion_type'] = {'default_value': overrides[field]}
					#engine_settings = cls.merge_profile_key(engine_settings, "adhesion_type", overrides[field])

			if field == "support":
				if overrides[field] in [ "none", "everywhere", "buildplate"]:
					settings['support_type'] = {'default_value': overrides[field]}
					#engine_settings = cls.merge_profile_key(engine_settings, "support_type", overrides[field])
					if overrides[field] == "buildplate":
						settings['support_enable'] = {'default_value': True}
						#engine_settings = cls.merge_profile_key(engine_settings, "support_enable", True)
					elif overrides[field] == "everywhere":
						settings['support_enable'] = {'default_value': True}
						#engine_settings = cls.merge_profile_key(engine_settings, "support_enable", True)
						#engine_settings = cls.merge_profile_key(engine_settings, "support_bottom_distance", "0.15")
		return settings

	# get Printer Overrides
	@classmethod
	def getPrinterJsonByFileName(cls, name='', slicer_profile_path=''):

		if slicer_profile_path=='' or name=='':
			return None

		printer_json = None
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if name.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")]:
				continue

			with open(slicer_profile_path + 'Printers/' + entry) as data_file:
				printer_json = json.load(data_file)

		if printer_json is None:
			with open(slicer_profile_path + 'Printers/_default.json') as data_file:
				printer_json = json.load(data_file)

		return printer_json

	# get Printer Overrides
	@classmethod
	def getPrinterJsonFileByid(cls, id='', slicer_profile_path=''):

		if slicer_profile_path == '' or id == '':
			return None

		for entry in os.listdir(slicer_profile_path + "Printers/"):
			try:
				filePath = slicer_profile_path + 'Printers/' + entry
				if filePath.endswith('json'):
					json_file = json.load(open(slicer_profile_path +'Printers/' + entry))
					if(json_file['id']==id):
						return json_file
			except:
				pass

		return None


	# get Printer Overrides
	@classmethod
	def getPrinterOverrides(cls, printer_id, slicer_profile_path):
		printer_json = None
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")] :
				continue

			with open(slicer_profile_path +'Printers/' + entry) as data_file:
				printer_json = json.load(data_file)

		if printer_json is None:
			with open(slicer_profile_path + 'Printers/_default.json') as data_file:
				printer_json = json.load(data_file)

		return printer_json['overrides']

	# get Nozzle Overrides
	@classmethod
	def getNozzleOverrides(cls, nozzle_id, slicer_profile_path):
		overrides = None
		for entry in os.listdir(slicer_profile_path + "Nozzles/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if nozzle_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path +'Nozzles/' + entry) as data_file:
				nozzle_json = json.load(data_file)
				overrides = {}
				for key in nozzle_json['overrides']:
					overrides.update(nozzle_json['overrides'][key])



		return overrides

	# get Filament and parents Overrides
	# Must check in Quality folder for default profiles and Variants for user profiles
	@classmethod
	def getFilamentOverrides(cls, filament_id, printer_id, nozzle_id, slicer_profile_path, quality=None):
		overrides_Values = {}
		custom = False
		logger = logging.getLogger("octoprint.plugin.curaX.profileReader")
		filament_json = dict()

		for entry in os.listdir(slicer_profile_path + "Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path + 'Variants/' + entry) as data_file:
				filament_json = json.load(data_file)
				custom = True

		if not custom:
			for entry in os.listdir(slicer_profile_path + "Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + 'Quality/' + entry) as data_file:
					filament_json = json.load(data_file)

		# check if printer is compatible
		if 'PrinterGroups' in filament_json:
			for list in filament_json['PrinterGroups']:
				if printer_id.lower() in map(lambda x:x.lower(),list['group_printers']):
					if quality.lower() in list['quality']:
						overrides_Values = list['quality'][quality.lower()]

		# check for overrides that do not depend on quality
		if 'overrides' in filament_json:
			overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)

		# check if nozzle in printer is compatible
		if 'nozzles_supported' in filament_json:
			if nozzle_id not in str(filament_json['nozzles_supported']):
				logger.warning("Nozzle not supported")

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
			for key in filament_json['overrides'].keys():
				overrides_Values.update(filament_json['overrides'][key])
			#overrides_Values = cls.merge_dicts(filament_json['overrides'], overrides_Values)
		# check if it was parent, if so, get overrides
		if 'inherits' in filament_json:
			overrides_Values = cls.merge_dicts(cls.getParentOverrides(filament_json['inherits'], nozzle_id, slicer_profile_path), overrides_Values)
		return overrides_Values


	# get values in header
	# in printer: id, name, metadata, electric_consumption, machine_cost, nozzles_supported, inherits
	@classmethod
	def getPrinterHeader(cls, header_id, printer_id, slicer_profile_path):
		header_value = None
		printer_json = dict()
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")]:
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
		custom = False

		for entry in os.listdir(slicer_profile_path + "Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path + 'Variants/' + entry) as data_file:
				filament_json = json.load(data_file)
				custom = True

		if not custom:
			for entry in os.listdir(slicer_profile_path + "Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + 'Quality/' + entry) as data_file:
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
		slicer_profile_path = slicingManager.get_slicer_profile_path("curaX")+'/'

		for entry in os.listdir(slicer_profile_path + "Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			return slicer_profile_path + "Variants/" + entry

		for entry in os.listdir(slicer_profile_path + "Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			return slicer_profile_path + "Quality/" + entry
		return None

	#check if printer(printer_id) with a nozzle size (nozzle_id) on extruder can use a especific filament(filament_id)
	@classmethod
	def isPrinterAndNozzleCompatible(cls, filament_id, printer_id, nozzle_id):
		# check if printer is can use this filament profile
		from octoprint.server import slicingManager
		logger = logging.getLogger("octoprint.plugin.curaX.profileReader")
		slicer_profile_path= slicingManager.get_slicer_profile_path("curaX")+'/'

		try:
			#check nozzle
			for entry in os.listdir(slicer_profile_path + "Printers/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if printer_id.lower().replace(" ", "") != entry.lower().replace(" ", "")[:-len(".json")]:
					continue

				with open(slicer_profile_path + "Printers/" + entry) as data_file:
					printer_json = json.load(data_file)

					if 'nozzles_supported' in printer_json and printer_json is not None:
						if str(float(nozzle_id) / 1000) not in str(printer_json['nozzles_supported']):
							return False

			#Check filament with nozzle
			custom = False

			for entry in os.listdir(slicer_profile_path + "Variants/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + 'Variants/' + entry) as data_file:
					filament_json = json.load(data_file)
					custom = True

			if not custom:
				for entry in os.listdir(slicer_profile_path + "Quality/"):
					if not entry.endswith(".json"):
						# we are only interested in profiles and no hidden files
						continue

					if filament_id.lower() not in entry.lower():
						continue

					# creates a shallow slicing profile
					with open(slicer_profile_path + 'Quality/' + entry) as data_file:
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
