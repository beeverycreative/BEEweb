
from __future__ import absolute_import

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

import os
import json
import logging
import uuid
import requests
from octoprint.settings import settings

class BaseStatistics:
	BASE_STATS = {
		"software_id": str(uuid.uuid1()),
		"total_prints": 0,
		"total_cancelled_prints": 0,
		"total_filament_changes": 0,
		"avg_prints_per_calibration": 0,
		"total_calibrations": 0,
		"total_prints_since_last_calibration": 0,
		"total_nozzle_changes": 0,
		"total_extruder_maintenance": 0,
		"total_calibration_tests": 0,
		# "workbench_move": 0,
		# "workbench_rotate": 0,
		# "workbench_scale": 0
	}

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._stats_file = os.path.join(settings().getBaseFolder('statistics'), "base_stats.json")
		self._stats = None
		self._dirty = False
		self.load()

	def get_software_id(self):
		if self._stats is not None and "software_id" in self._stats:
			return self._stats["software_id"]

		return None

	def load(self):
		if os.path.exists(self._stats_file) and os.path.isfile(self._stats_file):
			with open(self._stats_file, "r") as f:
				try:
					self._stats = json.load(f)
				except Exception as e:
					self._logger.exception(e)

		# changed from else to handle cases where the file exists, but is empty / 0 bytes
		if not self._stats:
			self._stats = self.BASE_STATS.copy()

	def save(self, force=False):
		if not self._dirty and not force:
			return False

		from octoprint.util import atomic_write
		try:
			with atomic_write(self._stats_file, "wb", prefix="bee-stats-", suffix=".json", permissions=0o600, max_permissions=0o666) as statsFile:
				json.dump(self._stats, statsFile)
				self._dirty = False
		except Exception as ex:
			self._logger.error("Error while saving base_stats.json: %s" % str(ex))
			raise
		else:
			self.load()
			return True

	def register_print(self):
		"""
		Logs a print operation.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_prints"] = self._stats["total_prints"] + 1
			self._stats["total_prints_since_last_calibration"] = self._stats["total_prints_since_last_calibration"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register print statistics. Error: %s" % str(ex))
			return False

		return True

	def register_print_canceled(self):
		"""
		Logs a canceled print. The input must be a valid PrintStatistics object
		:return boolean True if the stats were successfully saved
		"""

		try:
			self._stats["total_cancelled_prints"] = self._stats["total_cancelled_prints"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register print statistics. Error: %s" % str(ex))
			return False

		return True

	def register_filament_change(self):
		"""
		Logs a filament change operation.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_filament_changes"] = self._stats["total_filament_changes"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register filament change statistics. Error: %s" % str(ex))
			return False

		return True

	def register_calibration(self):
		"""
		Logs a calibration operation.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_calibrations"] = self._stats["total_calibrations"] + 1
			if self._stats["total_calibrations"] > 0:
				self._stats["avg_prints_per_calibration"] = \
					round(float(self._stats["total_prints"]) / float(self._stats["total_calibrations"]), 2)
			self._stats["total_prints_since_last_calibration"] = 0
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register calibration statistics. Error: %s" % str(ex))
			return False

		return True


	def register_calibration_test(self):
		"""
		Logs a calibration test.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_calibration_tests"] = self._stats["total_calibration_tests"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register calibration test statistics. Error: %s" % str(ex))
			return False

		return True

	def register_extruder_maintenance(self):
		"""
		Logs an extruder maintenance operation.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_extruder_maintenance"] = self._stats["total_extruder_maintenance"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register extruder maintenance statistics. Error: %s" % str(ex))
			return False

		return True

	def register_nozzle_change(self):
		"""
		Logs a nozzle change operation.
		:return boolean True if the stats were successfully saved
		"""
		try:
			self._stats["total_nozzle_changes"] = self._stats["total_nozzle_changes"] + 1
			self._dirty = True

		except Exception as ex:
			self._logger.error("Unable to register nozzle change statistics. Error: %s" % str(ex))
			return False

		return True

class PrinterStatistics(BaseStatistics):
	BASE_STATS = {
		"printer_serial_number": "00000",
		"total_prints": 0,
		"total_cancelled_prints": 0,
		"total_filament_changes": 0,
		"avg_prints_per_calibration": 0,
		"total_calibrations": 0,
		"total_prints_since_last_calibration": 0,
		"total_nozzle_changes": 0,
		"total_extruder_maintenance": 0,
		"total_calibration_tests": 0
	}

	def __init__(self, printer_serial_number):
		self._logger = logging.getLogger(__name__)
		stats_filename = "printer_stats_" + printer_serial_number + ".json"
		self._stats_file = os.path.join(settings().getBaseFolder('statistics'), stats_filename)
		self._stats = None
		self.load()
		self._stats["printer_serial_number"] = printer_serial_number
		self._dirty = False

	def get_printer_serial_number(self):
		if self._stats is not None and "printer_serial_number" in self._stats:
			return self._stats["printer_serial_number"]

		return None

class PrintEventStatistics:
	"""
	PRINT_BASE_STATS = {
		"printer_serial_number": "00000",
		"software_version: "1.2",
		"firmware_version: "10.2.30",
		"software_id": None,
		"timestamp": None,
		"total_print_time": None,
		"model_information": {
			"number_of_pieces": 1,
			"models": [
				{
				"name": None,
				"dimensions": {'x': 0, 'y': 0, 'z': 0}
				}
			]
		},
		"filament_used": {"name": None, "type": None, "color": None, "brand": None, "quantity": 0.0},
		"print_options": {"layer_height": 0, "heat_temperature": 210, "infill": None},
		"user_feedback": {"print_success": False, "print_rating": 0, "observations": None}
	}
	"""
	PRINT_BASE_STATS = {
		"print_id": "0",
		"printer_serial_number": "00000",
		"software_id": None,
		"timestamp": None,
		"event": None,
	}

	PRINT_START = "start"
	PRINT_PAUSED = "pause"
	PRINT_CANCELLED = "cancel"
	PRINT_RESUMED = "resume"
	PRINT_FINISHED = "finish"

	def __init__(self, printer_serial_number, software_id):
		self._logger = logging.getLogger(__name__)
		self._stats = self.PRINT_BASE_STATS.copy()
		self._dirty = False

		self._stats["print_id"] = str(uuid.uuid4())

		if printer_serial_number is not None:
			self._stats["printer_serial_number"] = printer_serial_number
		if software_id is not None:
			self._stats["software_id"] = software_id

		self._stats_file = os.path.join(settings().getBaseFolder('statistics'), "print_stats.json")


	def set_print_start(self, timestamp):
		if self._stats is not None:
			self._stats["timestamp"] = timestamp
			self._stats["event"] = PrintEventStatistics.PRINT_START
			self._dirty = True

	def set_print_paused(self, timestamp):
		if self._stats is not None:
			self._stats["timestamp"] = timestamp
			self._stats["event"] = PrintEventStatistics.PRINT_PAUSED
			self._dirty = True

	def set_print_resumed(self, timestamp):
		if self._stats is not None:
			self._stats["timestamp"] = timestamp
			self._stats["event"] = PrintEventStatistics.PRINT_RESUMED
			self._dirty = True

	def set_print_cancelled(self, timestamp):
		if self._stats is not None:
			self._stats["timestamp"] = timestamp
			self._stats["event"] = PrintEventStatistics.PRINT_CANCELLED
			self._dirty = True

	def set_print_finished(self, timestamp):
		if self._stats is not None:
			self._stats["timestamp"] = timestamp
			self._stats["event"] = PrintEventStatistics.PRINT_FINISHED
			self._dirty = True

	def set_total_print_time(self, timestamp):
		if self._stats is not None:
			self._stats["total_print_time"] = timestamp
			self._dirty = True

	def set_filament_used(self, name, filament_type=None, color=None, brand=None, quantity=0.0):
		if self._stats is not None:
			self._stats["filament_used"] = {
				"filament": {
					"name": name,
					"type": filament_type,
					"color": color,
					"brand": brand,
				},
				"quantity": quantity
			}
			self._dirty = True

	def set_print_options(self, resolution, density, platform_adhesion, support, advanced_options=None):
		"""
		Saves the options used for the print
		:param resolution:
		:param density:
		:param platform_adhesion:
		:param support:
		:param advanced_options: dict object ready to be json serialized into a string
		:return:
		"""
		import json
		if self._stats is not None:
			self._stats["print_options"] = {
				"resolution": resolution,
				"density": density,
				"platform_adhesion": platform_adhesion,
				"support": support,
				"advanced_options": json.dumps(advanced_options)
			}
			self._dirty = True

	def remove_print_options(self):
		if self._stats is not None and "print_options" in self._stats:
			del self._stats["print_options"]
			self._dirty = True

	def remove_filament_used(self):
		if self._stats is not None and "filament_used" in self._stats:
			del self._stats["filament_used"]
			self._dirty = True

	def remove_model_information(self):
		if self._stats is not None and "models" in self._stats:
			del self._stats["models"]
			self._dirty = True

	def remove_total_print_time(self):
		if self._stats is not None and "total_print_time" in self._stats:
			del self._stats["total_print_time"]
			self._dirty = True

	def set_model_information(self, models=None):
		if self._stats is not None:
			# validates the models information
			valid_models = []
			if models is not None and len(models) > 0:
				for m in models:
					if "name" in m and "dimension_x" in m and "dimension_y" in m and "dimension_z" in m:
						valid_models.append(m)

			self._stats["models"] = valid_models
			self._dirty = True

	def set_user_feedback(self, print_success=True, print_rating=5, obs=None):
		if self._stats is not None:
			self._stats["user_feedback"] = {
				"print_success": print_success,
				"print_rating": print_rating,
				"observations": obs
			}
			self._dirty = True

	def set_software_version(self, version):
		if self._stats is not None:
			self._stats["software_version"] = version
			self._dirty = True

	def set_firmware_version(self, version):
		if self._stats is not None:
			self._stats["firmware_version"] = version
			self._dirty = True

	def remove_software_version(self):
		if self._stats is not None and "software_version" in self._stats:
			del self._stats["software_version"]
			self._dirty = True

	def remove_firmware_version(self):
		if self._stats is not None and "firmware_version" in self._stats:
			del self._stats["firmware_version"]
			self._dirty = True

	def remove_print_options(self):
		if self._stats is not None and "print_options" in self._stats:
			del self._stats["print_options"]
			self._dirty = True

	def remove_redundant_information(self):
		"""
		This method is used to remove unnecessary information that is stored during the 'start' event
		and would only be redundant in the following events for the print
		:return:
		"""
		self.remove_filament_used()
		self.remove_model_information()
		self.remove_print_options()

	def save(self, force=False):
		if not self._dirty and not force:
			return False

		try:
			# if the file already exists and is not empty removes the last ] from the file to append the new object
			if os.path.exists(self._stats_file) and os.path.getsize(self._stats_file) > 0:
				with open(self._stats_file, "rb+") as printStatsFile:
					printStatsFile.seek(-1, os.SEEK_END)
					printStatsFile.truncate()
					printStatsFile.write(',\n')
					json.dump(self._stats, printStatsFile)
					printStatsFile.write(']')
			else:
				with open(self._stats_file, "a") as printStatsFile:
					printStatsFile.write('[')
					json.dump(self._stats, printStatsFile)
					printStatsFile.write(']')

		except Exception as ex:
			self._logger.error("Error while saving print information to print_stats.json: %s" % str(ex))
			raise
		else:
			return True


class StatisticsServerClient:
	"""
	Class used as communication interface with the statistics server
	"""
	STATS_HOST = 'https://beestats.beeverycreative.local'
	STATS_PORT = 443
	STATS_AUTH = '0d676254058389e6a06c903a2e7d8897f7d05dde'

	_conn = None

	def __init__(self):
		self._logger = logging.getLogger(__name__)


	def _send_base_statistics(self):
		try:
			base_stats_file = os.path.join(settings().getBaseFolder('statistics'), "base_stats.json")

			url = self.STATS_HOST + ':' + str(self.STATS_PORT) + '/api/general_stats'
			request_headers = {'Content-type': 'application/json','Authorization': 'Token ' + self.STATS_AUTH}
			with open(base_stats_file) as json_data:
				payload = json.load(json_data)

				resp = requests.post(url, json=payload, headers=request_headers, verify=False)

				if resp.status_code != requests.codes.created:
					self._logger.error('Error uploading general usage statistics. Server response code: %s' % resp.status_code)
					return

				self._logger.info('General usage statistics uploaded with success')
		except Exception as ex:
			self._logger.error('Error sending general usage statistics: ' + str(ex))
			raise ex

	def _send_printer_statistics(self):
		try:
			import glob
			url = self.STATS_HOST + ':' + str(self.STATS_PORT) + '/api/printer_stats'
			request_headers = {'Content-type': 'application/json', 'Authorization': 'Token ' + self.STATS_AUTH}

			path = os.path.join(settings().getBaseFolder('statistics'), "printer_stats_*.json")
			for printer_stats_file in glob.glob(path):
				with open(printer_stats_file) as json_data:
					payload = json.load(json_data)

					resp = requests.post(url, json=payload, headers=request_headers, verify=False)

					if resp.status_code != requests.codes.created:
						self._logger.error('Error uploading printer (%s) usage statistics. Server response code: %s' %
						(printer_stats_file, resp.status_code))
					else:
						self._logger.info('Printer (%s) usage statistics uploaded with success' % printer_stats_file)
		except Exception as ex:
			self._logger.error('Error sending printer usage statistics: ' + str(ex))
			raise ex

	def _send_print_events_statistics(self):
		try:
			url = self.STATS_HOST + ':' + str(self.STATS_PORT) + '/api/print_events'
			request_headers = {'Content-type': 'application/json', 'Authorization': 'Token ' + self.STATS_AUTH}

			print_events_filepath = os.path.join(settings().getBaseFolder('statistics'), "print_stats.json")
			with open(print_events_filepath) as json_data:
				payload = json.load(json_data)

				resp = requests.post(url, json=payload, headers=request_headers, verify=False)

				if resp.status_code != requests.codes.created:
					self._logger.error('Error uploading print events usage statistics. Server response code: %s' %
					resp.status_code)
				else:
					self._logger.info('Print events usage statistics uploaded with success')
					# if the upload was ok, erases the file contents
					open(print_events_filepath, 'w').close()
		except Exception as ex:
			self._logger.error('Error sending print events usage statistics: ' + str(ex))
			raise ex


	def gather_and_send_statistics(self):
		try:
			import datetime
			lastStatsUploadDate = settings().get(['lastStatisticsUpload'])
			sendThreshold = datetime.datetime.today() - datetime.timedelta(days=7)  # on week ago
			# Checks if the send threshold was already reached, and if so sends a new batch of usage statistics

			if lastStatsUploadDate is None or sendThreshold > lastStatsUploadDate:

				self._send_base_statistics()
				self._send_printer_statistics()
				self._send_print_events_statistics()

				self._logger.info('Usage statistics sent to BVC server!')

				settings().set(['lastStatisticsUpload'], datetime.datetime.today())
				settings().save()
		except Exception as ex:
			self._logger.error('Failed sending statistics to server.')