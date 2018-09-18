# coding=utf-8
from __future__ import absolute_import

__author__ = "Bruno Andrade"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import json
import os
import logging
import copy

from octoprint.printer.profile import PrinterProfileManager

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
		printer_id = PrinterProfileManager.normalize_printer_name(printer)

		#LOAD MACHINE DEFINITIONS
		machine_json = cls.getPrinterJsonByFileName(name=printer, slicer_profile_path=profile_path)
		inheritsList = []
		inheritPrinter = machine_json['inherits']
		done = False
		engine_settings = {}

		while not done:
			if inheritPrinter != 'fdmprinter':
				inheritsList.append(copy.copy(machine_json))
				machine_json = cls.getPrinterJsonFileByid(printer_id=inheritPrinter, slicer_profile_path=profile_path)
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
				extruder_settings[count] = cls.getFilamentOverrides(filament[count], profile_path, quality, nozzle[count])
				# get nozzle overrides
				extruder_settings[count] = cls.merge_dicts(extruder_settings[count], cls.getNozzleOverrides(nozzle[count], profile_path))

		# if single extruder
		else:
			# get filament and parent overrides
			filament_Overrides = cls.getFilamentOverrides(filament, profile_path, quality, nozzle)
			# get nozzle overrides
			nozzle_Overrides = cls.getNozzleOverrides(nozzle, profile_path)

			# populates the final engine_settings with the values from the fdmprinter and specific printer settings
			for key in raw_settings.keys():
				if 'default_value' in raw_settings[key].keys():
					engine_settings[key] = raw_settings[key]
				else:
					for k in raw_settings[key].keys():
						if 'default_value' in raw_settings[key][k].keys():
							engine_settings[k] = raw_settings[key][k]

			# merge the filament and nozzle overrides with the engine_settings
			for key in nozzle_Overrides.keys():
				if key not in engine_settings.keys():
					engine_settings[key] = {}
				engine_settings[key].update(nozzle_Overrides[key])

			for key in filament_Overrides.keys():
				if key not in engine_settings.keys():
					engine_settings[key] = {}
				engine_settings[key].update(filament_Overrides[key])

			interface_overrides = cls.overrideCustomValues(engine_settings,overrides)

			# merge interface overrides
			engine_settings.update(interface_overrides)
		return engine_settings, extruder_settings

	# Connect interface choices with curaEngine 2 parameters
	# Interfaces choices are: fill_density, platform_adhesion and support
	@classmethod
	def overrideCustomValues(cls, engine_settings,overrides):
		settings = {}

		for field in overrides:
			if field == "infill_sparse_density":
				fill_density_value = float(overrides[field])
				settings['infill_sparse_density'] = {'default_value' : fill_density_value}

				infill_line_width = engine_settings['infill_line_width']['default_value']

				multiplier = 1
				if engine_settings['infill_pattern']['default_value'] == 'grid':
					multiplier = 2
				elif engine_settings['infill_pattern']['default_value'] in ['triangles','cubic', 'cubicsubdiv']:
					multiplier = 3
				elif engine_settings['infill_pattern']['default_value'] in ['tetrahedral','quarter_cubic']:
					multiplier = 2
				elif engine_settings['infill_pattern']['default_value'] in ['cross','cross_3d']:
					multiplier = 1

				if fill_density_value == 0:
					infill_line_dist = 0
				else:
					infill_line_dist = (multiplier * infill_line_width * 100) / fill_density_value

				settings['infill_line_distance'] = {'default_value': infill_line_dist}

				#engine_settings = cls.merge_profile_key(engine_settings, "infill_sparse_density", overrides[field])

			if field == "adhesion_type":
				if overrides[field] in ["none", "brim", "raft", "skirt"]:
					settings['adhesion_type'] = {'default_value': overrides[field]}
					#engine_settings = cls.merge_profile_key(engine_settings, "adhesion_type", overrides[field])

			if field == "support_type":
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

		for field in overrides:
			if field == "retraction_speed":
				settings['retraction_retract_speed'] = {'default_value': overrides[field]}
				settings['retraction_prime_speed']   = {'default_value': overrides[field]}

			if field == "cool_fan_speed":
				settings['cool_fan_speed_min'] = {'default_value': overrides[field]}
				settings['cool_fan_speed_max'] = {'default_value': overrides[field]}

			if field == "speed_layer_0":
				settings['speed_print_layer_0']  = {'default_value': overrides[field]}
				settings['speed_travel_layer_0'] = {'default_value': overrides[field]}

			if field == "retraction_speed":
				settings['retraction_retract_speed'] = {'default_value': overrides[field]}
				settings['retraction_prime_speed']   = {'default_value': overrides[field]}

			if field == "infill_sparse_density":

				infill_line_width = engine_settings['infill_line_width']['default_value']

				multiplier = 1
				if 'infill_pattern' in overrides:
					infill_pattern = overrides['infill_pattern']
				else:
					infill_pattern = engine_settings['infill_pattern']

				if infill_pattern == 'grid':
					multiplier = 2
				elif infill_pattern in ['triangles', 'cubic', 'cubicsubdiv']:
					multiplier = 3
				elif infill_pattern in ['tetrahedral', 'quarter_cubic']:
					multiplier = 2
				elif infill_pattern in ['cross', 'cross_3d']:
					multiplier = 1

				if overrides[field] == 0:
					infill_line_dist = 0
				else:
					infill_line_dist = (multiplier * infill_line_width * 100) / float(overrides[field])

				settings['infill_line_distance'] = {'default_value': infill_line_dist}

			if field == "support_type":
				if overrides[field] == "buildplate":
					settings['support_enable'] = {'default_value': True}
				elif overrides[field] == "everywhere":
					settings['support_enable'] = {'default_value': True}
				else:
					settings['support_enable'] = {'default_value': False}


			settings[field] = {'default_value': overrides[field]}


		return settings

	# get Printer Overrides
	@classmethod
	def getPrinterJsonByFileName(cls, name='', slicer_profile_path=''):

		if not slicer_profile_path or not name:
			return None

		printer_json = None
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if name != entry[:-len(".json")]:
				continue

			with open(slicer_profile_path + 'Printers/' + entry) as data_file:
				printer_json = json.load(data_file)

		if printer_json is None:
			with open(slicer_profile_path + 'Printers/_default.json') as data_file:
				printer_json = json.load(data_file)

		return printer_json

	# get Printer Settings
	@classmethod
	def getPrinterJsonFileByid(cls, printer_id = '', slicer_profile_path = '', load_parents_inherits=False):
		logger = logging.getLogger("octoprint.plugin.curaX.profileReader")
		if slicer_profile_path == '' or printer_id == '':
			return None

		for entry in os.listdir(slicer_profile_path + "Printers/"):
			try:
				filePath = slicer_profile_path + 'Printers/' + entry
				if filePath.endswith('json'):
					json_file = json.load(open(slicer_profile_path +'Printers/' + entry))
					if json_file['id'] == printer_id:
						# loads any important information from parent profile
						if load_parents_inherits and 'inherits' in json_file:
							json_file['inherits'] = ProfileReader.getPrinterJsonFileByid(json_file['inherits'], slicer_profile_path)
						return json_file
			except Exception as ex:
				logger.error(ex)

		return None


	# get Printer Overrides
	@classmethod
	def getPrinterOverrides(cls, printer_id, slicer_profile_path):
		printer_json = None
		for entry in os.listdir(slicer_profile_path + "Printers/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if printer_id == entry[:-len(".json")]:
				with open(slicer_profile_path +'Printers/' + entry) as data_file:
					printer_json = json.load(data_file)
				break

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

			if nozzle_id.lower() == entry.lower()[:-len(".json")]:
				with open(slicer_profile_path +'Nozzles/' + entry) as data_file:
					nozzle_json = json.load(data_file)
					overrides = {}
					for key in nozzle_json['overrides']:
						overrides.update(nozzle_json['overrides'][key])
				break

		return overrides

	# get Filament and parents Overrides
	# Must check in Quality folder for default profiles and Variants for user profiles
	@classmethod
	def getFilamentDensity(cls, filament_id):
		logger = logging.getLogger("octoprint.plugin.curaX.profileReader")
		from octoprint.server import slicingManager
		slicer_profile_path = slicingManager.get_slicer_profile_path("curaX") + '/'
		filament_json = dict()
		default_value = 1.24

		for entry in os.listdir(slicer_profile_path + "Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() == entry.lower()[:-len(".json")]:
				with open(slicer_profile_path + 'Quality/' + entry) as data_file:
					filament_json = json.load(data_file)
				break

		if 'filament_density' not in filament_json:
			logger.warning('Filament density setting not present in %s' % filament_id)
			return default_value

		return filament_json['filament_density']

	# Get parent overrides
	# all parents are in materials folder
	@classmethod
	def getParentOverrides(cls, filament_id, nozzle_id, slicer_profile_path):
		overrides_values = {}
		with open(slicer_profile_path +'Materials/' + filament_id + ".json") as data_file:
			material_json = json.load(data_file)

		# check for overrides
		if 'overrides' in material_json:
			for key in material_json['overrides'].keys():
				overrides_values.update(material_json['overrides'][key])
		# check if has parent, if so, gets overrides
		if 'inherits' in material_json:
			overrides_values = cls.merge_dicts(cls.getParentOverrides(material_json['inherits'], nozzle_id, slicer_profile_path), overrides_values)

		return overrides_values


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

			if printer_id == entry.lower()[:-len(".json")]:
				with open(slicer_profile_path +'Printers/' + entry) as data_file:
					printer_json = json.load(data_file)
				break

		if header_id in printer_json:
			header_value = printer_json[header_id]

		return header_value

	# get values in header
	# in filament: id, name, brand, color, inherits, nozzles_supported, unload_temperature, cost
	@classmethod
	def getFilamentHeaderName(cls, header_id, filament_id, slicer_profile_path):
		header_value = None

		for entry in os.listdir(slicer_profile_path + "Materials"):
			if not entry.endswith(".json"):
				continue

			if filament_id.lower() not in entry.lower():
				continue

			with open(slicer_profile_path + 'Materials/' + entry) as data_file:
				filament_json = json.load(data_file)

			header_value = filament_json[header_id]

		return header_value

	@classmethod
	def getMaterialHeader(cls,header_id, filament_id, slicer_profile_path):
		header_value = None

		with open(slicer_profile_path + 'Materials/' + filament_id) as data_file:
			filament_json = json.load(data_file)

		if header_id in filament_json:
			header_value = filament_json[header_id]

		return header_value

	@classmethod
	def getFilamentHeader(cls, header_id, filament_id, slicer_profile_path):
		header_value = None
		custom = False
		filament_json = dict()

		for entry in os.listdir(slicer_profile_path + "Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower()[:-len(".json")] == entry.lower()[:-len(".json")]:
				with open(slicer_profile_path + 'Variants/' + entry) as data_file:
					filament_json = json.load(data_file)
					custom = True
				break

		if not custom:
			for entry in os.listdir(slicer_profile_path + "Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower()[:-len(".json")] == entry.lower()[:-len(".json")]:
					with open(slicer_profile_path + 'Quality/' + entry) as data_file:
						filament_json = json.load(data_file)
					break

		if header_id in filament_json:
			header_value = filament_json[header_id]

		if header_value is None and 'inherits' in filament_json:
			header_value = cls.getParentHeader(header_id, filament_json['inherits'], slicer_profile_path)

		return header_value


	@classmethod
	def getParentHeader(cls, header_id, filament_id, slicer_profile_path):
		header_value = None
		filament_json = dict()


		for entry in os.listdir(slicer_profile_path + "Materials/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id == entry.lower()[:-len(".json")]:
				with open(slicer_profile_path + 'Materials/' + entry) as data_file:
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

			if filament_id.lower() == entry.lower()[:-len(".json")]:
				return slicer_profile_path + "Variants/" + filament_id +".json"

		for entry in os.listdir(slicer_profile_path + "Quality/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() == entry.lower()[:-len(".json")]:
				return slicer_profile_path + "Quality/" + filament_id +".json"

		for entry in os.listdir(slicer_profile_path + "Materials/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			return slicer_profile_path + "Materials/" + entry

		return None

	#check if printer(printer_id) with a nozzle size (nozzle_id) on extruder can use a especific filament(filament_id)
	@classmethod
	def isPrinterAndNozzleCompatible(cls, filament_id, printer_id, nozzle_id='400'):
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

				if printer_id == entry.lower()[:-len(".json")]:
					with open(slicer_profile_path + "Printers/" + entry) as data_file:
						printer_json = json.load(data_file)

						if 'nozzles_supported' in printer_json and printer_json is not None:
							if str(float(nozzle_id) / 1000) not in str(printer_json['nozzles_supported']):
								return False
					break

			#Check filament with nozzle
			custom = False
			filament_json = dict()
			for entry in os.listdir(slicer_profile_path + "Variants/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() == entry.lower()[:-len(".json")]:
					with open(slicer_profile_path + 'Variants/' + entry) as data_file:
						filament_json = json.load(data_file)
						custom = True
					break

			if not custom:
				for entry in os.listdir(slicer_profile_path + "Quality/"):
					if not entry.endswith(".json"):
						# we are only interested in profiles and no hidden files
						continue

					if filament_id.lower() == entry.lower()[:-len(".json")]:
						with open(slicer_profile_path + 'Quality/' + entry) as data_file:
							filament_json = json.load(data_file)
						break

			#Check if nozzle is supported
			if 'nozzles_supported' in filament_json:
				if str(float(nozzle_id)/1000) not in str(filament_json['nozzles_supported']):
					return False

			# Check if printer is supported
			if 'PrinterGroups' in filament_json:
				for printer_list in filament_json['PrinterGroups']:
					if printer_id.lower() in printer_list['group_printers']:
						return True
		except Exception:
			logger.error("Error while getting Values from profile", exc_info=True)

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

	@classmethod
	def getFilamentQuality(cls, slicer_profile_path, filament_id):
		overrides_values = {}
		filament_json = {}
		custom = False

		for entry in os.listdir(slicer_profile_path + "/Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id not in entry:
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path + '/Variants/' + filament_id + '.json') as data_file:
				filament_json = json.load(data_file)
				custom = True

		if not custom:
			for entry in os.listdir(slicer_profile_path + "/Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + '/Quality/' + filament_id + '.json') as data_file:
					filament_json = json.load(data_file)

		if 'PrinterGroups' in filament_json:
			for printer_groups in filament_json['PrinterGroups']:
				overrides_values = printer_groups['quality']

		return overrides_values

	@classmethod
	def getOptions(cls, slicer_profile_path):

		with open(slicer_profile_path + "/optionsAvailable.json") as data_file:
			available_options = json.load(data_file)

		return available_options

	@classmethod
	def getRawCopyMaterial(cls,path,data):

		with open(path + "/Materials/" + "generic_material.json") as data_file:
			filament_json = json.load(data_file)

		if 'id' in filament_json:
			if data['display_name'] != "":
				filament_json['id'] = data['display_name']
			else:
				filament_json['id'] = "Unknown"

		if 'name' in filament_json:
			if data['display_name'] != "":
				filament_json['name'] = data['display_name']
			else:
				filament_json['name'] = "Unknown"

		if 'brand' in filament_json:
			if data['brand'] != "":
				filament_json['brand'] = data['brand']
			else:
				filament_json['brand'] = "Unknown"

		if 'material_information' in filament_json:
			for key in filament_json['material_information'].keys():
				if key in data:
					if key == 'display_name':
						if data['display_name'] == "":
							filament_json['material_information'][key] = {'default_value': 'Unknown'}
						else:
							filament_json['material_information'][key] = {'default_value': data[key]}
					elif key == 'brand':
						if data['brand'] == "":
							filament_json['material_information'][key] = {'default_value': 'Unknown'}
						else:
							filament_json['material_information'][key] = {'default_value': data[key]}
					else:
						filament_json['material_information'][key] = {'default_value': data[key]}

		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				for info in filament_json['overrides'][key]:
					if info in data:
						filament_json['overrides'][key][info]['default_value'] = int(data[info])

		return filament_json


	@classmethod
	def getRawCopyProfile(cls,path,data):
		with open(path + "/generic_profile.json") as data_file:
			filament_json = json.load(data_file)

			if 'id' in filament_json:
				filament_json['id'] = data['name']

			if 'name' in filament_json:
				filament_json['name'] = data['name']

			if 'inherits' in filament_json:
				filament_json['inherits'] = data['inherits']

			filament_json['PrinterGroups'][0]['quality'][data['quality']] = filament_json['PrinterGroups'][0]['quality'].pop('normal')

			cnt = 0

			for printer_groups in filament_json['PrinterGroups']:
				for key in filament_json['PrinterGroups'][cnt]:
					if 'quality' == key:
						overrides_values = filament_json['PrinterGroups'][cnt][key][data['quality']]
				cnt  += 1

			overrides_values = cls.merge_dicts(cls.getParentOverridesTeste(filament_json['inherits'], path), overrides_values)

			overrides_values = cls.merge_dicts(cls.getParentPrinterOverrides(path), overrides_values)

			for current in overrides_values:
				if current in data:
					if float(data[current]) != float(overrides_values[current]['default_value']):
						cnt = 0
						for list in filament_json['PrinterGroups']:
							if data['quality'] in list['quality']:
								filament_json['PrinterGroups'][cnt]['quality'][data['quality']][current] = {'default_value': data[current]}
							cnt += 1

		return filament_json


	@classmethod
	def getMaterial(cls,path,name):
		material_Values = {}
		filament_json = {}
		for entry in os.listdir(path + "/Materials/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if name.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(path + "/Materials/" + name +".json") as data_file:
				filament_json = json.load(data_file)

		if 'material_information' in filament_json:
			material_Values = filament_json['material_information']

		overrides_values = {}
		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				overrides_values.update(filament_json['overrides'][key])

		material_Values = cls.merge_dicts(overrides_values,material_Values)

		return material_Values


	@classmethod
	def getRawMaterial(cls, path):
		material_Values = {}
		with open(path + "/Materials/"+ "generic_material.json") as data_file:
			filament_json = json.load(data_file)

		if 'material_information' in filament_json:
			material_Values = filament_json['material_information']

		overrides_values = {}
		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				overrides_values.update(filament_json['overrides'][key])

		material_Values = cls.merge_dicts(overrides_values,material_Values)

		return material_Values

	@classmethod
	def getRawProfile(cls, path, material):


		overrides_values = {}
		with open(path + "/generic_profile.json") as data_file:
			filament_json = json.load(data_file)

		if 'PrinterGroups' in filament_json:
			for list in filament_json['PrinterGroups']:
				overrides_values = list['quality']['normal']

		# check for overrides that do not depend on quality
		if 'overrides' in filament_json:
			overrides_values = cls.merge_dicts(filament_json['overrides'], overrides_values)

		# check if it was parent, if so, get overrides

		overrides_values = cls.merge_dicts(cls.getParentOverridesTeste(material, path), overrides_values)

		overrides_values = cls.merge_dicts(cls.getParentPrinterOverrides(path), overrides_values)

		return overrides_values

	@classmethod
	def getSaveEditionFilament(cls,filament_id, slicer_profile_path):
		filament_json = {}
		custom = False

		for entry in os.listdir(slicer_profile_path + "/Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path + '/Variants/' + entry) as data_file:
				filament_json = json.load(data_file)
				custom = True

		if not custom:
			for entry in os.listdir(slicer_profile_path + "/Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + '/Quality/' + entry) as data_file:
					filament_json = json.load(data_file)

		return  filament_json


	@classmethod
	def getFilamentOverrides(cls, filament_id, slicer_profile_path, quality, nozzle):
		overrides_values = {}
		filament_json = {}
		custom = False

		for entry in os.listdir(slicer_profile_path + "/Variants/"):
			if not entry.endswith(".json"):
				# we are only interested in profiles and no hidden files
				continue

			if filament_id.lower() not in entry.lower():
				continue

			# creates a shallow slicing profile
			with open(slicer_profile_path + '/Variants/' + filament_id + ".json") as data_file:
				filament_json = json.load(data_file)
				custom = True

		if not custom:
			for entry in os.listdir(slicer_profile_path + "/Quality/"):
				if not entry.endswith(".json"):
					# we are only interested in profiles and no hidden files
					continue

				if filament_id.lower() not in entry.lower():
					continue

				# creates a shallow slicing profile
				with open(slicer_profile_path + '/Quality/' + filament_id + ".json") as data_file:
					filament_json = json.load(data_file)

		if 'PrinterGroups' in filament_json:
			for list in filament_json['PrinterGroups']:
				if quality.lower() in list['quality']:
					overrides_values = list['quality'][quality.lower()]

		# check for overrides that do not depend on quality
		if 'overrides' in filament_json:
			overrides_values = cls.merge_dicts(filament_json['overrides'], overrides_values)

		# check if it was parent, if so, get overrides
		if 'inherits' in filament_json:
			overrides_values = cls.merge_dicts(cls.getParentOverridesTeste(filament_json['inherits'], slicer_profile_path), overrides_values)

		overrides_values = cls.merge_dicts(cls.getParentPrinterOverrides(slicer_profile_path),overrides_values)

		overrides_values = cls.merge_dicts(cls.getParentNozzleOverrides(slicer_profile_path,nozzle),overrides_values)

		return overrides_values

	@classmethod
	def getParentPrinterOverrides(cls,slicer_profile_path):
		overrides_values = {}
		with open(slicer_profile_path + '/Printers/' + 'beevc_btf_series.json') as data_file:
			filament_json = json.load(data_file)

		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				overrides_values.update(filament_json['overrides'][key])

		return overrides_values

	@classmethod
	def getParentNozzleOverrides(cls,slicer_profile_path,nozzle):
		overrides_values = {}
		with open(slicer_profile_path + '/Nozzles/' + nozzle +'.json') as data_file:
			filament_json = json.load(data_file)

		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				overrides_values.update(filament_json['overrides'][key])

		return overrides_values

	@classmethod
	def getParentOverridesTeste(cls, filament_id, slicer_profile_path):

		overrides_values = {}
		filament_json = dict()

		with open(slicer_profile_path + '/Materials/' + filament_id + ".json") as data_file:
			filament_json = json.load(data_file)

		# check for overrides
		if 'overrides' in filament_json:
			for key in filament_json['overrides'].keys():
				overrides_values.update(filament_json['overrides'][key])
			# overrides_values = cls.merge_dicts(filament_json['overrides'], overrides_values)
		# check if it was parent, if so, get overrides
		if 'inherits' in filament_json:
			if filament_json['inherits'] != '':
				overrides_values = cls.merge_dicts(
					cls.getParentOverridesTeste(filament_json['inherits'], slicer_profile_path), overrides_values)
		return overrides_values
