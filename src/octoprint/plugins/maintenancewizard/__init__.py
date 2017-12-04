# coding=utf-8
from __future__ import absolute_import, division, print_function

__author__ = "BEEVC - Electronic Systems"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"


import octoprint.plugin


from flask.ext.babel import gettext


class MaintenanceWizardPlugin(octoprint.plugin.AssetPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.WizardPlugin,
                       octoprint.plugin.SettingsPlugin,
                       octoprint.plugin.BlueprintPlugin):

	#~~ TemplatePlugin API

	def get_template_configs(self):
		required = self._get_subwizard_attrs("_is_", "_wizard_required")
		names = self._get_subwizard_attrs("_get_", "_wizard_name")
		additional = self._get_subwizard_attrs("_get_", "_additional_wizard_template_data")

		result = list()
		for key, method in required.items():
			if not method():
				continue

			if not key in names:
				continue

			name = names[key]()
			if not name:
				continue

			config = dict(type="wizard", name=name, template="maintenancewizard_{}_wizard.jinja2".format(key), div="wizard_plugin_maintenancewizard_{}".format(key))
			if key in additional:
				additional_result = additional[key]()
				if additional_result:
					config.update(additional_result)
			result.append(config)

		return result

	#~~ AssetPlugin API

	def get_assets(self):
		return dict(
			js=["js/maintenancewizard.js"]
		)

	#~~ WizardPlugin API
	def is_wizard_required(self):
		methods = self._get_subwizard_attrs("_is_", "_wizard_required")
		return any(map(lambda m: m(), methods.values()))

	def get_wizard_details(self):
		result = dict()

		def add_result(key, method):
			result[key] = method()
		self._get_subwizard_attrs("_get_", "_wizard_details", add_result)

		return result



	#~~ Extruder calibration subwizard

	def _is_extrudercalibration_wizard_required(self):
		return self._printer.isExtruderCalibrationRequired()

	def _get_extrudercalibration_wizard_details(self):
		return dict()

	def _get_extrudercalibration_wizard_name(self):
		return gettext("Extruder Calibration")

	#~~ helpers

	def _get_subwizard_attrs(self, start, end, callback=None):
		result = dict()

		for item in dir(self):
			if not item.startswith(start) or not item.endswith(end):
				continue

			key = item[len(start):-len(end)]
			if not key:
				continue

			attr = getattr(self, item)
			if callable(callback):
				callback(key, attr)
			result[key] = attr

		return result


__plugin_name__ = "Maintenance Wizard"
__plugin_author__ = "BEEVC - Electronic Systems"
__plugin_description__ = "Provides wizard dialogs for maintenance operations"
__plugin_license__ = "AGPLv3"
__plugin_implementation__ = MaintenanceWizardPlugin()
