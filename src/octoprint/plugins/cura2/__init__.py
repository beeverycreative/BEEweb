# coding=utf-8
from __future__ import absolute_import

__author__ = "Bruno Andrade"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import logging
import logging.handlers
import os
import flask
import math
import json

import octoprint.plugin
import octoprint.util
import octoprint.slicing
from octoprint.settings import settings
from octoprint.util.paths import normalize as normalize_path

from .profileReader import ProfileReader

class CuraPlugin(octoprint.plugin.SlicerPlugin,
                 octoprint.plugin.SettingsPlugin,
                 octoprint.plugin.TemplatePlugin,
                 octoprint.plugin.AssetPlugin,
                 octoprint.plugin.BlueprintPlugin,
                 octoprint.plugin.StartupPlugin):

	def __init__(self):
		self._logger = logging.getLogger("octoprint.plugins.cura2")
		self._cura_logger = logging.getLogger("octoprint.plugins.cura2.engine")

		# setup job tracking across threads
		import threading
		self._slicing_commands = dict()
		self._cancelled_jobs = []
		self._job_mutex = threading.Lock()

	##~~ TemplatePlugin API

	def get_template_vars(self):
		return dict(
			homepage=__plugin_url__
		)

	##~~ StartupPlugin API

	def on_startup(self, host, port):
		# setup our custom logger
		from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
		cura_logging_handler = CleaningTimedRotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="engine"), when="D", backupCount=3)
		cura_logging_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
		cura_logging_handler.setLevel(logging.DEBUG)

		self._cura_logger.addHandler(cura_logging_handler)
		self._cura_logger.setLevel(logging.DEBUG if self._settings.get_boolean(["debug_logging"]) else logging.CRITICAL)
		self._cura_logger.propagate = False

	##~~ BlueprintPlugin API

	@octoprint.plugin.BlueprintPlugin.route("/import", methods=["POST"])
	def import_cura_profile(self):
		import datetime
		import tempfile

		from octoprint.server import slicingManager

		input_name = "file"
		input_upload_name = input_name + "." + self._settings.global_get(["server", "uploads", "nameSuffix"])
		input_upload_path = input_name + "." + self._settings.global_get(["server", "uploads", "pathSuffix"])

		if input_upload_name in flask.request.values and input_upload_path in flask.request.values:
			filename = flask.request.values[input_upload_name]
			try:
				profile_dict = self._load_profile(flask.request.values[input_upload_path])
			except Exception as e:
				self._logger.exception("Error while converting the imported profile")
				return flask.make_response("Something went wrong while converting imported profile: {message}".format(message=str(e)), 500)

		else:
			self._logger.warn("No profile file included for importing, aborting")
			return flask.make_response("No file included", 400)

		if profile_dict is None:
			self._logger.warn("Could not convert profile, aborting")
			return flask.make_response("Could not convert Cura profile", 400)

		name, _ = os.path.splitext(filename)

		# default values for name, display name and description
		profile_name = name
		profile_display_name = name
		profile_description = "Imported from {filename} on {date}".format(filename=filename, date=octoprint.util.get_formatted_datetime(datetime.datetime.now()))
		profile_allow_overwrite = False

		# overrides
		if "name" in flask.request.values:
			profile_name = flask.request.values["name"]
		if "displayName" in flask.request.values:
			profile_display_name = flask.request.values["displayName"]
		if "description" in flask.request.values:
			profile_description = flask.request.values["description"]
		if "allowOverwrite" in flask.request.values:
			from octoprint.server.api import valid_boolean_trues
			profile_allow_overwrite = flask.request.values["allowOverwrite"] in valid_boolean_trues

		try:
			slicingManager.save_profile("cura2",
			                            profile_name,
			                            profile_dict,
			                            allow_overwrite=profile_allow_overwrite,
			                            display_name=profile_display_name,
			                            description=profile_description)
		except octoprint.slicing.ProfileAlreadyExists:
			self._logger.warn("Profile {profile_name} already exists, aborting".format(**locals()))
			return flask.make_response("A profile named {profile_name} already exists for slicer cura".format(**locals()), 409)

		result = dict(
			resource=flask.url_for("api.slicingGetSlicerProfile", slicer="cura", name=profile_name, _external=True),
			displayName=profile_display_name,
			description=profile_description
		)
		r = flask.make_response(flask.jsonify(result), 201)
		r.headers["Location"] = result["resource"]
		return r

	##~~ AssetPlugin API

	def get_assets(self):
		return {
			"js": ["js/cura2.js"],
			"less": ["less/cura2.less"],
			"css": ["css/cura2.css"]
		}

	##~~ SettingsPlugin API

	def on_settings_save(self, data):
		old_debug_logging = self._settings.get_boolean(["debug_logging"])

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		new_debug_logging = self._settings.get_boolean(["debug_logging"])

		settings().set(["slicing", "cura2"], self._settings.get_boolean(["cura2"]))
		if old_debug_logging != new_debug_logging:
			if new_debug_logging:
				self._cura_logger.setLevel(logging.DEBUG)
			else:
				self._cura_logger.setLevel(logging.CRITICAL)


	def get_settings_defaults(self):
		return dict(
			cura_engine2=None,
			default_profile=None,
			debug_logging=False,
			cura2=settings().get(["slicing", "cura2"])
		)

	##~~ SlicerPlugin API

	def is_slicer_configured(self):
		cura_engine = self._settings.get(["cura_engine"])
		if cura_engine is not None and os.path.exists(cura_engine):
			return True
		else:
			self._logger.info("Path to CuraEngine has not been configured yet or does not exist (currently set to %r), Cura will not be selectable for slicing" % cura_engine)

	def get_slicer_properties(self):
		return dict(
			type="cura2",
			name="CuraEngine2",
			same_device=True,
			progress_report=True,
			source_file_types=["stl"],
			destination_extensions=["gco", "gcode", "g"]
		)

	def get_slicer_default_profile(self):
		path = self._settings.get(["default_profile"])
		if not path:
			path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "profiles/Printers", "_default.json")
		return self.get_slicer_profile(path)

	def get_slicer_profile(self, path):
		profile_dict = self._load_profile(path)

		display_name = None
		description = None
		if "name" in profile_dict:
			display_name = profile_dict["name"]
			del profile_dict["name"]
		if "description" in profile_dict:
			description = profile_dict["description"]
			del profile_dict["description"]
		if "id" in profile_dict:
			id = profile_dict["id"]
			del profile_dict["id"]

		properties = self.get_slicer_properties()
		return octoprint.slicing.SlicingProfile(properties["type"], "unknown", profile_dict, display_name=display_name, description=description)

	def save_slicer_profile(self, path, profile, allow_overwrite=True, overrides=None):
		new_profile = profile.data

		tmp=path.split("/")
		name= tmp[len(tmp)-1]
		new_profile["name"] = name[:-len(".json")]
		new_profile["id"] = self._sanitize (name[:-len(".json")])

		if profile.description is not None:
			new_profile["description"] = profile.description

		self._save_profile(path, new_profile, allow_overwrite=allow_overwrite)

	def do_slice(self, model_path, printer_profile, model_path1=None, machinecode_path=None, profile_path=None, position=None, overrides=None, resolution=None, nozzle_size=None, on_progress=None, on_progress_args=None, on_progress_kwargs=None):
		try:
			with self._job_mutex:
				if not profile_path:
					profile_path = self._settings.get(["default_profile"])
				else :
					profile_path = self._desanitize(profile_path)

				if not machinecode_path:
					path, _ = os.path.splitext(model_path)
					machinecode_path = path + ".gco"

				if position and isinstance(position, dict) and "x" in position and "y" in position:
					posX = position["x"]
					posY = position["y"]
				else:
					posX = None
					posY = None

				if on_progress:
					if not on_progress_args:
						on_progress_args = ()
					if not on_progress_kwargs:
						on_progress_kwargs = dict()

				self._cura_logger.info(u"### Slicing %s to %s using profile stored at %s" % (model_path, machinecode_path, profile_path))
				from octoprint.server import slicingManager
				profile_default_printer_path = slicingManager.get_slicer_profile_path("cura2") + '/Printers/fdmprinter.def.json'
				engine_settings, extruder_settings = ProfileReader.getSettingsToSlice(printer_profile["name"], str(nozzle_size), profile_path, resolution, overrides)

				executable = normalize_path(self._settings.get(["cura_engine"]))
				if not executable:
					return False, "Path to CuraEngine is not configured "

				working_dir, _ = os.path.split(executable)
				args = [executable, 'slice', '-v', '-p', '-j', profile_default_printer_path]
				for k, v in engine_settings.items():
					args += ["-s", "%s=%s" % (k, str(v['default_value']))]
				if extruder_settings is not None:
					args += ["-g"]
					for extruder in extruder_settings:
						args += ["-e" + str(extruder)]

						for k, v in extruder_settings[extruder].items():
							args += ["-s", "%s=%s" % (k, str(v['default_value']))]

					args += ["-o", machinecode_path, "-e0", "-l", model_path, "-e1", "-l", model_path1, "-s", "extruder_nr=1"]

				else:
					args += ["-o", machinecode_path, "-l", model_path]

				self._logger.info(u"Running %r in %s" % (" ".join(args), working_dir))

				import sarge
				p = sarge.run(args, cwd=working_dir, async=True, stdout=sarge.Capture(), stderr=sarge.Capture())
				p.wait_events()
				self._slicing_commands[machinecode_path] = p.commands[0]

			try:
				layer_count = None
				step_factor = dict(
					inset=0,
					skin=1,
					export=2
				)
				analysis = None
				while p.returncode is None:
					line = p.stderr.readline(timeout=0.5)
					if not line:
						p.commands[0].poll()
						continue

					line = octoprint.util.to_unicode(line, errors="replace")
					self._cura_logger.debug(line.strip())
					if on_progress is not None:
						# The Cura slicing process has three individual steps, each consisting of <layer_count> substeps:
						#
						#   - inset
						#   - skin
						#   - export
						#
						# So each layer will be processed three times, once for each step, resulting in a total amount of
						# substeps of 3 * <layer_count>.
						#
						# The CuraEngine reports the calculated layer count and the continuous progress on stderr.
						# The layer count gets reported right at the beginning in a line of the format:
						#
						#   Layer count: <layer_count>
						#
						# The individual progress per each of the three steps gets reported on stderr in a line of
						# the format:
						#
						#   Progress:<step>:<current_layer>:<layer_count>
						#
						# Thus, for determining the overall progress the following formula applies:
						#
						#   progress = <step_factor> * <layer_count> + <current_layer> / <layer_count> * 3
						#
						# with <step_factor> being 0 for "inset", 1 for "skin" and 2 for "export".

						if line.startswith(u"Layer count:") and layer_count is None:
							try:
								layer_count = float(line[len(u"Layer count:"):].strip())
							except:
								pass

						elif line.startswith(u"Progress:"):
							split_line = line[len(u"Progress:"):].strip().split(":")
							if len(split_line) == 3:
								step, current_layer, _ = split_line
								try:
									current_layer = float(current_layer)
								except:
									pass
								else:
									if not step in step_factor:
										continue
									on_progress_kwargs["_progress"] = (step_factor[step] * layer_count + current_layer) / (layer_count * 3)
									on_progress(*on_progress_args, **on_progress_kwargs)

						elif line.startswith(u"Print time:"):
							try:
								print_time = int(line[len(u"Print time:"):].strip())
								if analysis is None:
									analysis = dict()
								analysis["estimatedPrintTime"] = print_time
							except:
								pass

						elif line.startswith(u"Filament:") or line.startswith(u"Filament2:"):
							if line.startswith(u"Filament:"):
								filament_str = line[len(u"Filament:"):].strip()
								tool_key = "tool0"
							else:
								filament_str = line[len(u"Filament2:"):].strip()
								tool_key = "tool1"

							try:
								filament = int(filament_str)
								if analysis is None:
									analysis = dict()
								if not "filament" in analysis:
									analysis["filament"] = dict()
								if not tool_key in analysis["filament"]:
									analysis["filament"][tool_key] = dict()
								analysis["filament"][tool_key]["length"] = filament
								if "filamentDiameter" in engine_settings:
									radius_in_cm = float(int(engine_settings["filamentDiameter"]) / 10000.0) / 2.0
									filament_in_cm = filament / 10.0
									analysis["filament"][tool_key]["volume"] = filament_in_cm * math.pi * radius_in_cm * radius_in_cm
							except:
								pass
			finally:
				p.close()

			with self._job_mutex:
				if machinecode_path in self._cancelled_jobs:
					self._cura_logger.info(u"### Cancelled")
					raise octoprint.slicing.SlicingCancelled()

			self._cura_logger.info(u"### Finished, returncode %d" % p.returncode)
			if p.returncode == 0:
				return True, dict(analysis=analysis)
			else:
				self._logger.warn(u"Could not slice via Cura, got return code %r" % p.returncode)
				return False, "Got returncode %r" % p.returncode

		except octoprint.slicing.SlicingCancelled as e:
			raise e
		except:
			self._logger.exception(u"Could not slice via Cura, got an unknown error")
			return False, "Unknown error, please consult the log file"

		finally:
			with self._job_mutex:
				if machinecode_path in self._cancelled_jobs:
					self._cancelled_jobs.remove(machinecode_path)
				if machinecode_path in self._slicing_commands:
					del self._slicing_commands[machinecode_path]

			self._cura_logger.info("-" * 40)
		self._cura_logger.info("Slicing Ended")

	def cancel_slicing(self, machinecode_path):
		with self._job_mutex:
			if machinecode_path in self._slicing_commands:
				self._cancelled_jobs.append(machinecode_path)
				command = self._slicing_commands[machinecode_path]
				if command is not None:
					command.terminate()
				self._logger.info(u"Cancelled slicing of %s" % machinecode_path)

	def _load_profile(self, path):
		import json
		profile_dict = dict()
		with open(path, "r") as f:
			try:
				profile_dict = json.load(f)
			except:
				raise IOError("Couldn't read profile from {path}".format(path=path))
		return profile_dict

	def _save_profile(self, path, profile, allow_overwrite=True):
		import json
		with octoprint.util.atomic_write(path, "wb", max_permissions=0o666) as f:
			json.dump(profile, f)

	def _desanitize(self, name):
		if name is None:
			return None

		if "/" in name or "\\" in name:
			raise ValueError("name must not contain / or \\")
		try:
			import string
			valid_chars = "-_.() {ascii}{digits}".format(ascii=string.ascii_letters, digits=string.digits)
			sanitized_name = ''.join(c for c in name if c in valid_chars)
			sanitized_name = sanitized_name.replace("_", " ")
			pos= sanitized_name.index(' bee')
			sanitized_name =sanitized_name[:pos]
			return str(sanitized_name)
		except:
			pass

		return name

	def _sanitize(self, name):
		if name is None:
			return None

		if "/" in name or "\\" in name:
			raise ValueError("name must not contain / or \\")

		import string
		valid_chars = "-_.() {ascii}{digits}".format(ascii=string.ascii_letters, digits=string.digits)
		sanitized_name = ''.join(c for c in name if c in valid_chars)
		sanitized_name = sanitized_name.replace(" ", "_")
		return sanitized_name

	def isPrinterAndNozzleCompatible(self, filament_id, printer_id, nozzle_size):
		return ProfileReader.isPrinterAndNozzleCompatible(filament_id, printer_id, nozzle_size)

	def getFilamentHeader(self, brand_id, filament_id, slicer_profile_path):
		return ProfileReader.getFilamentHeader(brand_id, filament_id, slicer_profile_path )

	def pathToFilament(self, filament_id):
		return ProfileReader.pathToFilament(filament_id)

__plugin_name__ = "CuraEngine (<= 2.6)"
__plugin_author__ = "Bruno Andrade"
__plugin_url__ = "https://github.com/Beeverycreative"
__plugin_description__ = "Adds support for slicing via CuraEngine from versions 2.X from within OctoPrint"
__plugin_license__ = "AGPLv3"
__plugin_implementation__ = CuraPlugin()
