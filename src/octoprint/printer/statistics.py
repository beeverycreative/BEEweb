
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
			with atomic_write(self._stats_file, "wb", prefix="bee-stats-", suffix=".json", permissions=0o600, max_permissions=0o666) as configFile:
				json.dump(self._stats, configFile)
				self._dirty = False
		except:
			self._logger.exception("Error while saving config.yaml!")
			raise
		else:
			self.load()
			return True

class PrintStatistics:
	_base_stats = {
		"printer_serial_number": "00000",
		"model_informations": {
			"number_of_pieces": 0,
			"models": [
				{
				"name": None,
				"dimensions": {'x': 0, 'y': 0, 'z': 0}
				}
			]
		},
		"filament_used": {"name": None, "type": None, "color": None, "brand": None, "quantity": None},
		"print_options": {"layer_height": 0, "heat_temperature": 210, "infill": None},
		"model_file_origin": "stl",
		"user_feedback": {"print_finished_successfully": False, "result_satisfaction": 0, "obs": None}
	}


	def __init__(self):
		self._stats = self.base_stats
