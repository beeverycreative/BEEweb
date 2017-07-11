
from __future__ import absolute_import

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

import os
import json
import logging
from octoprint.settings import settings

class BaseStatistics:
	_base_stats = {
		"total_prints": 0,
		"total_cancelled_prints": 0,
		"total_filament_changes": 0,
		"avg_prints_per_calibration": 0,
		"total_calibrations": 0,
		"total_prints_since_last_calibration": 0,
		"total_nozzle_changes": 0,
		"total_extruder_maintenance": 0,
		"total_calibration_tests": 0,
		"workbench_move": 0,
		"workbench_rotate": 0,
		"workbench_scale": 0
	}

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._stats_file = os.path.join(settings().getBaseFolder('statistics'), "base_stats.json")
		self._stats = None
		self.load()
		self._dirty = False

	def load(self):
		if os.path.exists(self._stats_file) and os.path.isfile(self._stats_file):
			with open(self._stats_file, "r") as f:
				try:
					self._stats = json.load(f)
				except Exception as e:
					self._logger.exception(e)

		# changed from else to handle cases where the file exists, but is empty / 0 bytes
		if not self._stats:
			self._stats = self._base_stats

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

	def register_print(self, print_statistics):
		"""
		Logs a print operation. The input must be a valid PrintStatistics object
		:return boolean True if the stats were successfully saved
		"""
		if print_statistics is None or not isinstance(print_statistics, PrintStatistics):
			return False

		try:
			self._stats["total_prints"] = self._stats["total_prints"] + 1
			self._stats["total_prints_since_last_calibration"] = self._stats["total_prints_since_last_calibration"] + 1
			self._dirty = True
			self.save()

			# saves the print statistics details
			print_statistics.save()
		except Exception as ex:
			self._logger.error("Unable to register print statistics. Error: %s" % str(ex))
			return False

		return True

	def register_print_canceled(self, print_statistics):
		"""
		Logs a canceled print. The input must be a valid PrintStatistics object
		:return boolean True if the stats were successfully saved
		"""
		if print_statistics is None or not isinstance(print_statistics, PrintStatistics):
			return False

		try:
			self._stats["total_cancelled_prints"] = self._stats["total_cancelled_prints"] + 1
			self._dirty = True
			self.save()

			# saves the print statistics details
			print_statistics.save()
		except Exception as ex:
			self._logger.error("Unable to register print statistics. Error: %s" % str(ex))
			return False

		return True

class PrintStatistics:
	_base_stats = {
		"printer_serial_number": "00000",
		"start_time": None,
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
		"user_feedback": {"print_finished_successfully": False, "result_satisfaction": 0, "obs": None}
	}

	def __init__(self):
		self._stats = self._base_stats
		self._logger = logging.getLogger(__name__)
		self._stats_file = os.path.join(settings().getBaseFolder('statistics'), "print_stats.json")

	def set_printer_serial_number(self, sn):
		if self._stats is not None and "printer_serial_number" in self._stats:
			self._stats["printer_serial_number"] = sn

	def set_start_time(self, timestamp):
		if self._stats is not None and "start_time" in self._stats:
			self._stats["start_time"] = timestamp

	def set_total_print_time(self, timestamp):
		if self._stats is not None and "total_print_time" in self._stats:
			self._stats["total_print_time"] = timestamp

	def set_filament_used(self, name, filament_type=None, color=None, brand=None, quantity=0.0):
		if self._stats is not None and "filament_used" in self._stats:
			self._stats["filament_used"] = {
				"name": name,
				"type": filament_type,
				"color": color,
				"brand": brand,
				"quantity": quantity
			}

	def set_user_feedback(self, success=True, user_satisfaction=5, obs=None):
		if self._stats is not None and "user_feedback" in self._stats:
			self._stats["user_feedback"] = {
				"print_finished_successfully": success,
				"result_satisfaction": user_satisfaction,
				"obs": obs
			}

	def save(self):
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
