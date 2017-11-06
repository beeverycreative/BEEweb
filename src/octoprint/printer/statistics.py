
from __future__ import absolute_import

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

import os
import json
import logging
import uuid
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
		"model_file_origin": "stl",
		"user_feedback": {"print_success": False, "print_rating": 0, "obs": None}
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
				"name": name,
				"type": filament_type,
				"color": color,
				"brand": brand,
				"quantity": quantity
			}
			self._dirty = True

	def remove_filament_used(self):
		if self._stats is not None and "filament_used" in self._stats:
			del self._stats["filament_used"]
			self._dirty = True

	def remove_model_information(self):
		if self._stats is not None and "model_information" in self._stats:
			del self._stats["model_information"]
			self._dirty = True

	def set_model_information(self, number_of_pieces=0, models=None):
		if self._stats is not None:
			self._stats["model_information"] = {
				"number_of_pieces": number_of_pieces,
				"models": models
			}

			# validates the models information
			valid_models = []
			if models is not None and len(models) > 0:
				for m in models:
					if "name" in m and "dimensions" in m:
						valid_models.append(m)

			self._dirty = True

	def set_user_feedback(self, print_success=True, print_rating=5, obs=None):
		if self._stats is not None:
			self._stats["user_feedback"] = {
				"print_success": print_success,
				"print_rating": print_rating,
				"obs": obs
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

	def remove_redundant_information(self):
		"""
		This method is used to remove unnecessary information that is stored during the 'start' event
		and would only be redundant in the following events for the print
		:return:
		"""
		self.remove_filament_used()
		self.remove_model_information()
		self.remove_software_version()
		self.remove_firmware_version()

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
