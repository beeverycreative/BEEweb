# coding=utf-8
"""
In this module the slicing support of OctoPrint is encapsulated.

.. autoclass:: SlicingProfile
   :members:

.. autoclass:: TemporaryProfile
   :members:

.. autoclass:: SlicingManager
   :members:
"""

from __future__ import absolute_import, division, print_function

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import os
import time

try:
	from os import scandir
except ImportError:
	from scandir import scandir

import octoprint.plugin
import octoprint.events
import octoprint.util
from octoprint.settings import settings

import logging

from .exceptions import *


class SlicingProfile(object):
	"""
	A wrapper for slicing profiles, both meta data and actual profile data.

	Arguments:
	    slicer (str): Identifier of the slicer this profile belongs to.
	    name (str): Identifier of this slicing profile.
	    data (object): Profile data, actual structure depends on individual slicer implementation.
	    display_name (str): Displayable name for this slicing profile.
	    description (str): Description of this slicing profile.
	    default (bool): Whether this is the default slicing profile for the slicer.
	"""

	def __init__(self, slicer, name, data, display_name=None, description=None, default=False, brand=None):
		self.slicer = slicer
		self.name = name
		self.data = data
		self.display_name = display_name
		self.description = description
		self.brand = brand
		self.default = default


class TemporaryProfile(object):
	"""
	A wrapper for a temporary slicing profile to be used for a slicing job, based on a :class:`SlicingProfile` with
	optional ``overrides`` applied through the supplied ``save_profile`` method.

	Usage example:

	.. code-block:: python

	   temporary = TemporaryProfile(my_slicer.save_slicer_profile, my_default_profile,
	                                overrides=my_overrides)
	   with (temporary) as profile_path:
	       my_slicer.do_slice(..., profile_path=profile_path, ...)

	Arguments:
	    save_profile (callable): Method to use for saving the temporary profile, also responsible for applying the
	        supplied ``overrides``. This will be called according to the method signature of
	        :meth:`~octoprint.plugin.SlicerPlugin.save_slicer_profile`.
	    profile (SlicingProfile): The profile from which to derive the temporary profile.
	    overrides (dict): Optional overrides to apply to the ``profile`` for creation of the temporary profile.
	"""

	def __init__(self, save_profile, profile, overrides=None):
		self.save_profile = save_profile
		self.profile = profile
		self.overrides = overrides

	def __enter__(self):
		import tempfile
		temp_profile = tempfile.NamedTemporaryFile(prefix="slicing-profile-temp-", suffix=".profile", delete=False)
		temp_profile.close()

		self.temp_path = temp_profile.name
		self.save_profile(self.temp_path, self.profile, overrides=self.overrides)
		return self.temp_path

	def __exit__(self, type, value, traceback):
		import os
		try:
			os.remove(self.temp_path)
		except:
			pass


class SlicingManager(object):
	"""
	The :class:`SlicingManager` is responsible for managing available slicers and slicing profiles.

	Arguments:
	    profile_path (str): Absolute path to the base folder where all slicing profiles are stored.
	    printer_profile_manager (~octoprint.printer.profile.PrinterProfileManager): :class:`~octoprint.printer.profile.PrinterProfileManager`
	       instance to use for accessing available printer profiles, most importantly the currently selected one.
	"""

	def __init__(self, profile_path, printer_profile_manager):
		self._logger = logging.getLogger(__name__)

		self._profile_path = profile_path
		self._printer_profile_manager = printer_profile_manager

		self._slicers = dict()
		self._slicer_names = dict()

	def initialize(self):
		"""
		Initializes the slicing manager by loading and initializing all available
		:class:`~octoprint.plugin.SlicerPlugin` implementations.
		"""
		self.reload_slicers()

	def reload_slicers(self):
		"""
		Retrieves all registered :class:`~octoprint.plugin.SlicerPlugin` implementations and registers them as
		available slicers.
		"""
		plugins = octoprint.plugin.plugin_manager().get_implementations(octoprint.plugin.SlicerPlugin)
		slicers = dict()
		for plugin in plugins:
			try:
				slicers[plugin.get_slicer_properties()["type"]] = plugin
			except:
				self._logger.exception("Error while getting properties from slicer {}, ignoring it".format(plugin._identifier))
				continue
		self._slicers = slicers

	@property
	def slicing_enabled(self):
		"""
		Returns:
		    boolean: True if there is at least one configured slicer available, False otherwise.
		"""
		return len(self.configured_slicers) > 0

	@property
	def registered_slicers(self):
		"""
		Returns:
		    list of str: Identifiers of all available slicers.
		"""
		return self._slicers.keys()

	@property
	def configured_slicers(self):
		"""
		Returns:
		    list of str: Identifiers of all available configured slicers.
		"""
		return map(lambda slicer: slicer.get_slicer_properties()["type"], filter(lambda slicer: slicer.is_slicer_configured(), self._slicers.values()))

	@property
	def default_slicer(self):
		"""
		Retrieves the default slicer.

		Returns:
		    str: The identifier of the default slicer or ``None`` if the default slicer is not registered in the
		        system.
		"""
		slicer_name = settings().get(["slicing", "defaultSlicer"])
		if slicer_name in self.registered_slicers:
			return slicer_name
		else:
			return None

	def get_slicer(self, slicer, require_configured=True):
		"""
		Retrieves the slicer named ``slicer``. If ``require_configured`` is set to True (the default) an exception
		will be raised if the slicer is not yet configured.

		Arguments:
		    slicer (str): Identifier of the slicer to return
		    require_configured (boolean): Whether to raise an exception if the slicer has not been configured yet (True,
		        the default), or also return an unconfigured slicer (False).

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.SlicerNotConfigured: The ``slicer`` is not yet configured and ``require_configured`` was set to True.
		"""

		if not slicer in self._slicers:
			raise UnknownSlicer(slicer)

		if require_configured and not self._slicers[slicer].is_slicer_configured():
			raise SlicerNotConfigured(slicer)

		return self._slicers[slicer]

	def slice(self, slicer_name, source_path, dest_path, profile_name, callback,
	          callback_args=None, callback_kwargs=None, overrides=None, resolution=None, nozzle_size=None,
	          on_progress=None, on_progress_args=None, on_progress_kwargs=None, printer_profile_id=None, position=None):
		"""
		Slices ``source_path`` to ``dest_path`` using slicer ``slicer_name`` and slicing profile ``profile_name``.
		Since slicing happens asynchronously, ``callback`` will be called when slicing has finished (either successfully
		or not), with ``callback_args`` and ``callback_kwargs`` supplied.

		If ``callback_args`` is left out, an empty argument list will be assumed for the callback. If ``callback_kwargs``
		is left out, likewise an empty keyword argument list will be assumed for the callback. Note that in any case
		the callback *must* support being called with the following optional keyword arguments:

		_analysis
		    If the slicer returned analysis data of the created machine code as part of its slicing result, this keyword
		    argument will contain that data.
		_error
		    If there was an error while slicing this keyword argument will contain the error message as returned from
		    the slicer.
		_cancelled
		    If the slicing job was cancelled this keyword argument will be set to True.

		Additionally callees may specify ``overrides`` for the specified slicing profile, e.g. a different extrusion
		temperature than defined in the profile or a different layer height.

		With ``on_progress``, ``on_progress_args`` and ``on_progress_kwargs``, callees may specify a callback plus
		arguments and keyword arguments to call upon progress reports from the slicing job. The progress callback will
		be called with a keyword argument ``_progress`` containing the current slicing progress as a value between 0
		and 1 plus all additionally specified args and kwargs.

		If a different printer profile than the currently selected one is to be used for slicing, its id can be provided
		via the keyword argument ``printer_profile_id``.

		If the ``source_path`` is to be a sliced at a different position than the print bed center, this ``position`` can
		be supplied as a dictionary defining the ``x`` and ``y`` coordinate in print bed coordinates of the model's center.

		Arguments:
		    slicer_name (str): The identifier of the slicer to use for slicing.
		    source_path (str): The absolute path to the source file to slice.
		    dest_path (str): The absolute path to the destination file to slice to.
		    profile_name (str): The name of the slicing profile to use.
		    callback (callable): A callback to call after slicing has finished.
		    callback_args (list or tuple): Arguments of the callback to call after slicing has finished. Defaults to
		        an empty list.
		    callback_kwargs (dict): Keyword arguments for the callback to call after slicing has finished, will be
		        extended by ``_analysis``, ``_error`` or ``_cancelled`` as described above! Defaults to an empty
		        dictionary.
		    overrides (dict): Overrides for the printer profile to apply.
		    on_progress (callable): Callback to call upon slicing progress.
		    on_progress_args (list or tuple): Arguments of the progress callback. Defaults to an empty list.
		    on_progress_kwargs (dict): Keyword arguments of the progress callback, will be extended by ``_progress``
		        as described above! Defaults to an empty dictionary.
		    printer_profile_id (str): Identifier of the printer profile for which to slice, if another than the
		        one currently selected is to be used.
		    position (dict): Dictionary containing the ``x`` and ``y`` coordinate in the print bed's coordinate system
		        of the sliced model's center. If not provided the model will be positioned at the print bed's center.
		        Example: ``dict(x=10,y=20)``.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer specified via ``slicer_name`` is unknown.
		    ~octoprint.slicing.exceptions.SlicerNotConfigured: The slice specified via ``slicer_name`` is not configured yet.
		"""

		print(resolution);

		if callback_args is None:
			callback_args = ()
		if callback_kwargs is None:
			callback_kwargs = dict()

		if not slicer_name in self.configured_slicers:
			if not slicer_name in self.registered_slicers:
				error = "No such slicer: {slicer_name}".format(**locals())
				exc = UnknownSlicer(slicer_name)
			else:
				error = "Slicer not configured: {slicer_name}".format(**locals())
				exc = SlicerNotConfigured(slicer_name)
			callback_kwargs.update(dict(_error=error, _exc=exc))
			callback(*callback_args, **callback_kwargs)
			raise exc

		slicer = self.get_slicer(slicer_name)

		printer_profile = None
		if printer_profile_id is not None:
			printer_profile = self._printer_profile_manager.get(printer_profile_id)

		if printer_profile is None:
			printer_profile = self._printer_profile_manager.get_current_or_default()

		if slicer_name == "curaX":
			def slicer_worker(slicer, model_path, machinecode_path, profile_name, overrides, printer_profile, position, callback, callback_args, callback_kwargs):
				try:
					ok, result = slicer.do_slice(
						model_path,
						printer_profile,
						machinecode_path=machinecode_path,
						profile_path=profile_name,
						overrides=overrides,
						resolution=resolution,
						nozzle_size=nozzle_size,
						position=position,
						on_progress=on_progress,
						on_progress_args=on_progress_args,
						on_progress_kwargs=on_progress_kwargs
					)

					if not ok:
						callback_kwargs.update(dict(_error=result))
					elif result is not None and isinstance(result, dict) and "analysis" in result:
						callback_kwargs.update(dict(_analysis=result["analysis"]))
				except SlicingCancelled:
					callback_kwargs.update(dict(_cancelled=True))
				finally:
					callback(*callback_args, **callback_kwargs)

		else:
			def slicer_worker(slicer, model_path, machinecode_path, profile_name, overrides, printer_profile, position, callback, callback_args, callback_kwargs):
				try:
					slicer_name = slicer.get_slicer_properties()["type"]
					with self._temporary_profile(slicer_name, name=profile_name, overrides=overrides) as profile_path:
						ok, result = slicer.do_slice(
							model_path,
							printer_profile,
							machinecode_path=machinecode_path,
							profile_path=profile_path,
							position=position,
							on_progress=on_progress,
							on_progress_args=on_progress_args,
							on_progress_kwargs=on_progress_kwargs
						)

					if not ok:
						callback_kwargs.update(dict(_error=result))
					elif result is not None and isinstance(result, dict) and "analysis" in result:
						callback_kwargs.update(dict(_analysis=result["analysis"]))
				except SlicingCancelled:
					callback_kwargs.update(dict(_cancelled=True))
				finally:
					callback(*callback_args, **callback_kwargs)

		import threading
		slicer_worker_thread = threading.Thread(target=slicer_worker,
		                                        args=(slicer, source_path, dest_path, profile_name, overrides, printer_profile, position, callback, callback_args, callback_kwargs))
		slicer_worker_thread.daemon = True
		slicer_worker_thread.start()

	def cancel_slicing(self, slicer_name, source_path, dest_path):
		"""
		Cancels the slicing job on slicer ``slicer_name`` from ``source_path`` to ``dest_path``.

		Arguments:
		    slicer_name (str): Identifier of the slicer on which to cancel the job.
		    source_path (str): The absolute path to the source file being sliced.
		    dest_path (str): The absolute path to the destination file being sliced to.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer specified via ``slicer_name`` is unknown.
		"""

		slicer = self.get_slicer(slicer_name)
		slicer.cancel_slicing(dest_path)

	def load_profile(self, slicer, name, require_configured=True):
		"""
		Loads the slicing profile for ``slicer`` with the given profile ``name`` and returns it. If it can't be loaded
		due to an :class:`IOError` ``None`` will be returned instead.

		If ``require_configured`` is True (the default) a :class:`SlicerNotConfigured` exception will be raised
		if the indicated ``slicer`` has not yet been configured.

		Returns:
		    SlicingProfile: The requested slicing profile or None if it could not be loaded.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer specified via ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer specified via ``slicer`` has not yet been configured and
		        ``require_configured`` was True.
		    ~octoprint.slicing.exceptions.UnknownProfile: The profile for slicer ``slicer`` named ``name`` does not exist.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		try:
			path = self.get_profile_path(slicer, name, must_exist=True)
		except IOError:
			return None
		return self._load_profile_from_path(slicer, path, require_configured=require_configured)

	def save_profile(self, slicer, name, profile, overrides=None, allow_overwrite=True, display_name=None, description=None):
		"""
		Saves the slicer profile ``profile`` for slicer ``slicer`` under name ``name``.

		``profile`` may be either a :class:`SlicingProfile` or a :class:`dict`.

		If it's a :class:`SlicingProfile`, its :attr:`~SlicingProfile.slicer``, :attr:`~SlicingProfile.name` and - if
		provided - :attr:`~SlicingProfile.display_name` and :attr:`~SlicingProfile.description` attributes will be
		overwritten with the supplied values.

		If it's a :class:`dict`, a new :class:`SlicingProfile` instance will be created with the supplied meta data and
		the profile data as the :attr:`~SlicingProfile.data` attribute.

		Arguments:
		    slicer (str): Identifier of the slicer for which to save the ``profile``.
		    name (str): Identifier under which to save the ``profile``.
		    profile (SlicingProfile or dict): The :class:`SlicingProfile` or a :class:`dict` containing the profile
		        data of the profile the save.
		    overrides (dict): Overrides to apply to the ``profile`` before saving it.
		    allow_overwrite (boolean): If True (default) if a profile for the same ``slicer`` of the same ``name``
		        already exists, it will be overwritten. Otherwise an exception will be thrown.
		    display_name (str): The name to display to the user for the profile.
		    description (str): A description of the profile.

		Returns:
		    SlicingProfile: The saved profile (including the applied overrides).

		Raises:
		    ValueError: The supplied ``profile`` is neither a :class:`SlicingProfile` nor a :class:`dict`.
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.ProfileAlreadyExists: A profile with name ``name`` already exists for ``slicer`` and ``allow_overwrite`` is
		        False.
		"""
		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		if not isinstance(profile, SlicingProfile):
			if isinstance(profile, dict):
				profile = SlicingProfile(slicer, name, profile, display_name=display_name, description=description)
			else:
				raise ValueError("profile must be a SlicingProfile or a dict")
		else:
			profile.slicer = slicer
			profile.name = name
			if display_name is not None:
				profile.display_name = display_name
			if description is not None:
				profile.description = description

		path = self.get_profile_path(slicer, name)
		is_overwrite = os.path.exists(path)

		if is_overwrite and not allow_overwrite:
			raise ProfileAlreadyExists(slicer, profile.name)

		self._save_profile_to_path(slicer, path, profile, overrides=overrides, allow_overwrite=allow_overwrite)

		payload = dict(slicer=slicer,
		               profile=name)
		event = octoprint.events.Events.SLICING_PROFILE_MODIFIED if is_overwrite else octoprint.events.Events.SLICING_PROFILE_ADDED
		octoprint.events.eventManager().fire(event, payload)

		return profile

	def _temporary_profile(self, slicer, name=None, overrides=None):
		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		profile = self._get_default_profile(slicer)
		if name:
			try:
				profile = self.load_profile(slicer, name)
			except (UnknownProfile, IOError):
				# in that case we'll use the default profile
				pass

		return TemporaryProfile(self.get_slicer(slicer).save_slicer_profile, profile, overrides=overrides)

	def delete_material(self, slicer, name):

		slicer_object_curaX = self.get_slicer(slicer)
		slicer_object_curaX.removeInheritsProfile(self.get_slicer_profile_path(slicer),name)

		try:
			path = self.get_profile_path(slicer, name, must_exist=True)
		except UnknownProfile:
			return
		os.remove(path)

	def delete_quality_material(self,slicer,quality,name):
		slicer_object_curaX = self.get_slicer(slicer)

		slicer_object_curaX.delete_quality_material(self.get_slicer_profile_path(slicer),quality, name)



	def change_quality_name(self,slicer,filament_id,quality,name):
		slicer_object_curaX = self.get_slicer(slicer)
		slicer_object_curaX.change_quality_name(self.get_slicer_profile_path(slicer),filament_id,quality,name)


	def copy_quality_name(self,slicer,filament_id,quality,name):
		slicer_object_curaX = self.get_slicer(slicer)
		slicer_object_curaX.copy_quality_name(self.get_slicer_profile_path(slicer),filament_id,quality,name)


	def new_quality(self,slicer, filament_id,quality):
		slicer_object_curaX = self.get_slicer(slicer)
		slicer_object_curaX.new_quality(self.get_slicer_profile_path(slicer),filament_id,quality)


	def delete_profile(self, slicer, name):
		"""
		Deletes the profile ``name`` for the specified ``slicer``.

		If the profile does not exist, nothing will happen.

		Arguments:
		    slicer (str): Identifier of the slicer for which to delete the profile.
		    name (str): Identifier of the profile to delete.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.CouldNotDeleteProfile: There was an error while deleting the profile.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		if not name:
			raise ValueError("name must be set")

		try:
			try:
				path = self.get_profile_path(slicer, name, must_exist=True)
			except UnknownProfile:
				return
			os.remove(path)
		except ProfileException as e:
			raise e
		except Exception as e:
			raise CouldNotDeleteProfile(slicer, name, cause=e)
		else:
			octoprint.events.eventManager().fire(octoprint.events.Events.SLICING_PROFILE_DELETED, dict(slicer=slicer, profile=name))

	def set_default_profile(self, slicer, name, require_configured=False,
	                        require_exists=True):
		"""
		Sets the given profile as default profile for the slicer.

		Arguments:
		    slicer (str): Identifier of the slicer for which to set the default
		        profile.
		    name (str): Identifier of the profile to set as default.
		    require_configured (bool): Whether the slicer needs to be configured
		        for the action to succeed. Defaults to false. Will raise a
		        SlicerNotConfigured error if true and the slicer has not been
		        configured yet.
		    require_exists (bool): Whether the profile is required to exist in
		        order to be set as default. Defaults to true. Will raise a
		        UnknownProfile error if true and the profile is unknown.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer``
		        is unknown
		    ~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer ``slicer``
		        has not yet been configured and ``require_configured`` was true.
		    ~octoprint.slicing.exceptions.UnknownProfile: The profile ``name``
		        was unknown for slicer ``slicer`` and ``require_exists`` was
		        true.
		"""
		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)

		if not name:
			raise ValueError("name must be set")

		if require_exists and not name in self.all_profiles_list(slicer, require_configured=require_configured):
			raise UnknownProfile(slicer, name)

		default_profiles = settings().get(["slicing", "defaultProfiles"])
		if not default_profiles:
			default_profiles = dict()
		default_profiles[slicer] = name
		settings().set(["slicing", "defaultProfiles"], default_profiles)
		settings().save(force=True)

	def duplicate_profile(self, slicer, name):
		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		if not name:
			raise ValueError("name must be set")


		profile = self.load_profile(slicer, name)

		profile.slicer = slicer
		profile.name = name
		slicerPath = self.get_slicer_profile_path(slicer)

		tempPath = self.get_slicer_profile_path(slicer) + "/Variants/" + "{name}.json".format(name=name)
		count = 0

		while True:
			count = count + 1
			is_overwrite = os.path.exists(tempPath)

			if is_overwrite:
				tempPath = slicerPath + "/Variants/" + "{name} (copy {number} ).json".format(name=name, number=count)
			else:
				break

		destinationPath = tempPath
		self._save_profile_to_path(slicer, destinationPath, profile)

		payload = dict(slicer=slicer, profile=name)
		event =  octoprint.events.Events.SLICING_PROFILE_ADDED
		octoprint.events.eventManager().fire(event, payload)

		return profile

	def all_profiles(self, slicer, require_configured=False):
		"""
		Retrieves all profiles for slicer ``slicer``.

		If ``require_configured`` is set to True (default is False), only will return the profiles if the ``slicer``
		is already configured, otherwise a :class:`SlicerNotConfigured` exception will be raised.

		Arguments:
		    slicer (str): Identifier of the slicer for which to retrieve all slicer profiles
		    require_configured (boolean): Whether to require the slicer ``slicer`` to be already configured (True)
		        or not (False, default). If False and the slicer is not yet configured, a :class:`~octoprint.slicing.exceptions.SlicerNotConfigured`
		        exception will be raised.
		Returns:
		    dict of SlicingProfile: A dict of all :class:`SlicingProfile` instances available for the slicer ``slicer``, mapped by the identifier.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer ``slicer`` is not configured and ``require_configured`` was True.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)

		profiles = dict()
		slicer_profile_path = self.get_slicer_profile_path(slicer)
		self._logger.info("Retriving all profiles....")
		start_time = time.time()
		for entry in scandir(slicer_profile_path):
			if not entry.name.endswith(".profile") or octoprint.util.is_hidden_path(entry.name):
				# we are only interested in profiles and no hidden files
				continue

			profile_name = entry.name[:-len(".profile")]
			profiles[profile_name] = self._load_profile_from_path(slicer, entry.path, require_configured=require_configured)
		elapsed_time = time.time() - start_time
		self._logger.info("Retriving Profiles take "+ str(elapsed_time) +" s")
		return profiles


	def load_profile_quality(self,slicer, name):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer);
		except IOError:
			return None

		return slicer_object_curaX.getProfileQuality(path, name)

	def load_options(self, slicer):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer);
		except IOError:
			return None

		return slicer_object_curaX.getOptionSettings(path)


	def load_single_profile(self, slicer, name, quality , nozzle):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer)
		except IOError:
			return None

		return slicer_object_curaX.getProfileTeste(name, path, quality, nozzle)

	def load_raw_material(self,slicer):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer)
		except IOError:
			return None

		return slicer_object_curaX.getRawMaterial(path)


	def load_raw_profile(self,slicer, material):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer)
		except IOError:
			return None

		return slicer_object_curaX.getRawProfile(path,material)


	def load_material(self, slicer, name):
		slicer_object_curaX = self.get_slicer(slicer)
		try:
			path = self.get_slicer_profile_path(slicer)
		except IOError:
			return None

		return slicer_object_curaX.getMaterial(path, name)


	def edit_profile(self, slicer, name , data , quality, nozzle):
		profile = self.get_slicer(slicer).getSavedEditionFilament(name, self.get_slicer_profile_path(slicer))
		override_profile = self.get_slicer(slicer).getProfileTeste(name, self.get_slicer_profile_path(slicer), quality , nozzle)

		for current in data:
			if current in override_profile:
				if data[current] != override_profile[current]['default_value']:
					cnt = 0
					for list in profile['PrinterGroups']:
						if quality in list['quality']:
									profile['PrinterGroups'][cnt]['quality'][quality][current] = {'default_value':data[current]}
						cnt += 1
			else:
				cnt = 0
				for list in profile['PrinterGroups']:
					if quality in list['quality']:
						profile['PrinterGroups'][cnt]['quality'][quality][current] = {'default_value': data[current]}
					cnt += 1

		path = self.get_slicer_profile_path(slicer) + "/Variants/" + "{name}.json".format(name=name)
		self._save_edit_profile_to_path(slicer, path, profile)


	def saveNewMaterial(self, slicer, data):

		slicer_object_curaX = self.get_slicer(slicer)
		slicerPath = self.get_slicer_profile_path(slicer)

		profile = slicer_object_curaX.getRawCopyMaterial(slicerPath, data)

		tempPath = self.get_slicer_profile_path(slicer) + "/Materials/" + "{name}.json".format(name=profile['id'])
		count = 0;

		while True:
			count = count + 1
			is_overwrite = os.path.exists(tempPath)

			if is_overwrite:
				tempPath = slicerPath + "/Materials/" + "{name} (copy {number} ).json".format(name=profile['id'], number=count)
			else:
				break

		self._save_edit_profile_to_path(slicer, tempPath, profile)


	def saveNewProfile(self,slicer,data):
		slicer_object_curaX = self.get_slicer(slicer);
		slicerPath = self.get_slicer_profile_path(slicer);

		profile =slicer_object_curaX.getRawCopyProfile(slicerPath,data)

		tempPath = self.get_slicer_profile_path(slicer) + "/Variants/" + "{name}.json".format(name=data['name'])

		count = 0;

		while True:
			count = count + 1
			is_overwrite = os.path.exists(tempPath)

			if is_overwrite:
				tempPath = slicerPath + "/Variants/" + "{name} (copy {number} ).json".format(name=profile['id'],
																							  number=count)
			else:
				break


		self._save_edit_profile_to_path(slicer, tempPath, profile)



	def saveNewMaterialEdition(self,slicer, data,name):

		slicer_object_curaX = self.get_slicer(slicer)
		slicerPath = self.get_slicer_profile_path(slicer)


		profile = slicer_object_curaX.getRawCopyMaterial(slicerPath, data)

		if name != data['display_name']:

			path = self.get_slicer_profile_path(slicer)+ "/Materials/" + "{name}.json".format(name=name)
			os.remove(path)

			if data['display_name'] == "":
				tempPath = self.get_slicer_profile_path(slicer) + "/Materials/" + "{name}.json".format(name='Unknown')
				slicer_object_curaX.changeInheritsProfile(self.get_slicer_profile_path(slicer),'Unknown',name)
			else:
				tempPath = self.get_slicer_profile_path(slicer) + "/Materials/" + "{name}.json".format(name=data['display_name'])
				slicer_object_curaX.changeInheritsProfile(self.get_slicer_profile_path(slicer),data['display_name'],name)

			count = 0;

			while True:
				count = count + 1
				is_overwrite = os.path.exists(tempPath)

				if is_overwrite:
					if data['display_name'] == "":
						tempPath = slicerPath + "/Materials/" + "{name} (copy {number} ).json".format(name='Unknown', number=count)
					else:
						tempPath = slicerPath + "/Materials/" + "{name} (copy {number} ).json".format(name=data['display_name'],number=count)

				else:
					break
		else:
			tempPath = self.get_slicer_profile_path(slicer) + "/Materials/" + "{name}.json".format(name=profile['id'])


		self._save_edit_profile_to_path(slicer, tempPath, profile)

	def _save_edit_profile_to_path(self, slicer, path, profile, allow_overwrite=True, overrides=None,require_configured=False):
		self.get_slicer(slicer, require_configured=require_configured).save_edit_profile(path, profile,
																						 allow_overwrite=allow_overwrite,
																						 overrides=overrides)

	def all_profiles_list(self, slicer, require_configured=False, from_current_printer=True):
		"""
		Retrieves all profiles for slicer ``slicer`` but avoiding to parse every single profile file for better performance

		If ``require_configured`` is set to True (default is False), only will return the profiles if the ``slicer``
		is already configured, otherwise a :class:`SlicerNotConfigured` exception will be raised.

		Arguments:
			slicer (str): Identifier of the slicer for which to retrieve all slicer profiles
			require_configured (boolean): Whether to require the slicer ``slicer`` to be already configured (True)
				or not (False, default). If False and the slicer is not yet configured, a :class:`~octoprint.slicing.exceptions.SlicerNotConfigured`
				exception will be raised.
			from_current_printer (boolean): Whether to select only profiles from the current or default printer
		Returns:
			list of SlicingProfile: A list of all :class:`SlicingProfile` instances available for the slicer ``slicer``.

		Raises:
			~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
			~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer ``slicer`` is not configured and ``require_configured`` was True.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)

		profiles = dict()
		slicer_profile_path = self.get_slicer_profile_path(slicer)

		if from_current_printer:
			# adds an '_' to the end to avoid false positive string lookups for the printer names
			printer_name = self._printer_profile_manager.get_current_or_default()['name']
			printer_id = printer_name.replace(' ', '')
			# removes the A suffix of some models for filament lookup matching
			if printer_id.endswith('A'):
				printer_id = printer_id[:-1]

			printer_id = "_" + printer_id.lower() + "_"

		for entry in os.listdir(slicer_profile_path):
			if not entry.endswith(".profile") or octoprint.util.is_hidden_path(entry):
				# we are only interested in profiles and no hidden files
				continue

			if from_current_printer and printer_id not in entry.lower():
				continue

			#path = os.path.join(slicer_profile_path, entry)
			profile_name = entry[:-len(".profile")]

			# creates a shallow slicing profile
			profiles[profile_name] = self._create_shallow_profile(profile_name, slicer, ".profile", require_configured)
		return profiles

	def all_profiles_list_json(self, slicer, require_configured=False, from_current_printer=True, nozzle_size=None):
		"""
		Retrieves all profiles for slicer ``slicer`` but avoiding to parse every single profile file for better performance
		If ``require_configured`` is set to True (default is False), only will return the profiles if the ``slicer``
		is already configured, otherwise a :class:`SlicerNotConfigured` exception will be raised.
		Arguments:
			slicer (str): Identifier of the slicer for which to retrieve all slicer profiles
			require_configured (boolean): Whether to require the slicer ``slicer`` to be already configured (True)
				or not (False, default). If False and the slicer is not yet configured, a :class:`~octoprint.slicing.exceptions.SlicerNotConfigured`
				exception will be raised.
			from_current_printer (boolean): Whether to select only profiles from the current or default printer
			nozzle_size (string) : value of nozzle size (ex: 400 )
		Returns:
			list of SlicingProfile: A list of all :class:`SlicingProfile` instances available for the slicer ``slicer``.
		Raises:
			~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
			~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer ``slicer`` is not configured and ``require_configured`` was True.
		"""


		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)
		profiles = dict()
		slicer_profile_path = self.get_slicer_profile_path(slicer)

		if from_current_printer:
			printer_name = self._printer_profile_manager.get_current_or_default()['name']
			printer_id = self._printer_profile_manager.normalize_printer_name(printer_name)

		slicer_object_curaX = self.get_slicer(slicer)
		for folder in os.listdir(slicer_profile_path):
			if folder == "Quality" or folder == "Variants":
				for entry in os.listdir(slicer_profile_path +"/" +folder):
					if not entry.endswith(".json") or octoprint.util.is_hidden_path(entry):
						# we are only interested in profiles and no hidden files
						continue

					filament_name = entry[:-len(".json")]

					if from_current_printer:
						if not slicer_object_curaX.isPrinterAndNozzleCompatible(filament_name, printer_id, nozzle_size):
							continue

					#path = os.path.join(slicer_profile_path, entry)
					profile_name = entry[:-len(".json")]
					brand= slicer_object_curaX.getFilamentHeader("brand", entry, slicer_profile_path + "/")

					# filament_id  = slicer_object_curaX.getFilamentHeader("inherits", entry, slicer_profile_path + "/")

					# filament_name = slicer_object_curaX.getFilamentHeaderName("name", filament_id, slicer_profile_path + "/")

					# creates a shallow slicing profile
					temp_profile = self._create_shallow_profile(profile_name, slicer, "json", require_configured, brand)

					# temp_profile = self._create_shallow_profile(filament_name, slicer, "json", require_configured, brand)
					profiles[profile_name] = temp_profile

		return profiles

	def all_materials_list_json(self, slicer, require_configured=False, from_current_printer=True, nozzle_size=None):
		"""
		Retrieves all profiles for slicer ``slicer`` but avoiding to parse every single profile file for better performance
		If ``require_configured`` is set to True (default is False), only will return the profiles if the ``slicer``
		is already configured, otherwise a :class:`SlicerNotConfigured` exception will be raised.
		Arguments:
			slicer (str): Identifier of the slicer for which to retrieve all slicer profiles
			require_configured (boolean): Whether to require the slicer ``slicer`` to be already configured (True)
				or not (False, default). If False and the slicer is not yet configured, a :class:`~octoprint.slicing.exceptions.SlicerNotConfigured`
				exception will be raised.
			from_current_printer (boolean): Whether to select only profiles from the current or default printer
			nozzle_size (string) : value of nozzle size (ex: 400 )
		Returns:
			list of SlicingProfile: A list of all :class:`SlicingProfile` instances available for the slicer ``slicer``.
		Raises:
			~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
			~octoprint.slicing.exceptions.SlicerNotConfigured: The slicer ``slicer`` is not configured and ``require_configured`` was True.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)
		profiles = dict()
		slicer_profile_path = self.get_slicer_profile_path(slicer)

		if from_current_printer:
			# adds an '_' to the end to avoid false positive string lookups for the printer names
			printer_name = self._printer_profile_manager.get_current_or_default()['name']
			printer_id = printer_name.replace(' ', '')
			# removes the A suffix of some models for filament lookup matching
			if printer_id.endswith('A'):
				printer_id = printer_id[:-1]

			printer_id = printer_id.upper()

		slicer_object_curaX = self.get_slicer(slicer)
		for folder in os.listdir(slicer_profile_path):
			if folder == "Materials":
				for entry in os.listdir(slicer_profile_path + "/" + folder):
					if not entry.endswith(".json") or octoprint.util.is_hidden_path(entry):
						# we are only interested in profiles and no hidden files
						continue

					# if from_current_printer:
					# 	if not slicer_object_curaX.isPrinterAndNozzleCompatible(entry, printer_id, nozzle_size):
					# 		continue

					# path = os.path.join(slicer_profile_path, entry)
					print(entry);
					profile_name = entry[:-len(".json")]
					brand = slicer_object_curaX.getMaterialHeader("brand", entry, slicer_profile_path + "/")
					print(brand);
					# filament_id  = slicer_object_curaX.getFilamentHeader("inherits", entry, slicer_profile_path + "/")

					# filament_name = slicer_object_curaX.getFilamentHeaderName("name", filament_id, slicer_profile_path + "/")

					# creates a shallow slicing profile
					temp_profile = self._create_shallow_profile(profile_name, slicer, "json", require_configured, brand)

					# temp_profile = self._create_shallow_profile(filament_name, slicer, "json", require_configured, brand)
					profiles[profile_name] = temp_profile
		return profiles


	def all_Inherits_materials_list_json(self, slicer, material_id, require_configured=False, from_current_printer=True, nozzle_size=None):

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)
		if require_configured and not slicer in self.configured_slicers:
			raise SlicerNotConfigured(slicer)
		profiles = dict()
		slicer_profile_path = self.get_slicer_profile_path(slicer)

		if from_current_printer:
			# adds an '_' to the end to avoid false positive string lookups for the printer names
			printer_name = self._printer_profile_manager.get_current_or_default()['name']
			printer_id = printer_name.replace(' ', '')
			# removes the A suffix of some models for filament lookup matching
			if printer_id.endswith('A'):
				printer_id = printer_id[:-1]

			printer_id = printer_id.upper()

		slicer_object_curaX = self.get_slicer(slicer)
		for folder in os.listdir(slicer_profile_path):
			if folder == "Quality" or folder == "Variants":
				for entry in os.listdir(slicer_profile_path + "/" + folder):
					if not entry.endswith(".json") or octoprint.util.is_hidden_path(entry):
						# we are only interested in profiles and no hidden files
						continue

					# if from_current_printer:
					# 	if not slicer_object_curaX.isPrinterAndNozzleCompatible(entry, printer_id, nozzle_size):
					# 		continue

					# path = os.path.join(slicer_profile_path, entry)
					profile_name = entry[:-len(".json")]
					inherit = slicer_object_curaX.getFilamentHeader("inherits", entry, slicer_profile_path + "/")
					if inherit == material_id :
						brand   = slicer_object_curaX.getFilamentHeader("brand", entry, slicer_profile_path + "/")

						# filament_id  = slicer_object_curaX.getFilamentHeader("inherits", entry, slicer_profile_path + "/")

						# filament_name = slicer_object_curaX.getFilamentHeaderName("name", filament_id, slicer_profile_path + "/")

						# creates a shallow slicing profile
						temp_profile = self._create_shallow_profile(profile_name, slicer, "json", require_configured, brand)

						# temp_profile = self._create_shallow_profile(filament_name, slicer, "json", require_configured, brand)
						profiles[profile_name] = temp_profile
		return profiles


	def profiles_last_modified(self, slicer):
		"""
		Retrieves the last modification date of ``slicer``'s profiles.

		Args:
		    slicer (str): the slicer for which to retrieve the last modification date

		Returns:
		    (float) the time stamp of the last modification of the slicer's profiles
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		slicer_profile_path = self.get_slicer_profile_path(slicer)
		lms = [os.stat(slicer_profile_path).st_mtime]
		lms += [os.stat(entry.path).st_mtime for entry in scandir(slicer_profile_path) if entry.name.endswith(".profile")]
		return max(lms)

	def get_slicer_profile_path(self, slicer):
		"""
		Retrieves the path where the profiles for slicer ``slicer`` are stored.

		Arguments:
		    slicer (str): Identifier of the slicer for which to retrieve the path.

		Returns:
		    str: The absolute path to the folder where the slicer's profiles are stored.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		path = os.path.join(self._profile_path, slicer)
		if not os.path.exists(path):
			os.makedirs(path)
		return path

	def get_profile_path(self, slicer, name, must_exist=False):
		"""
		Retrieves the path to the profile named ``name`` for slicer ``slicer``.

		If ``must_exist`` is set to True (defaults to False) a :class:`UnknownProfile` exception will be raised if the
		profile doesn't exist yet.

		Arguments:
		    slicer (str): Identifier of the slicer to which the profile belongs to.
		    name (str): Identifier of the profile for which to retrieve the path.
		    must_exist (boolean): Whether the path must exist (True) or not (False, default).

		Returns:
		    str: The absolute path to the profile identified by ``name`` for slicer ``slicer``.

		Raises:
		    ~octoprint.slicing.exceptions.UnknownSlicer: The slicer ``slicer`` is unknown.
		    ~octoprint.slicing.exceptions.UnknownProfile: The profile named ``name`` doesn't exist and ``must_exist`` was True.
		"""

		if not slicer in self.registered_slicers:
			raise UnknownSlicer(slicer)

		if not name:
			raise ValueError("name must be set")

		if slicer == "curaX":
			slicer_object_curaX = self.get_slicer(slicer)
			path = slicer_object_curaX.pathToFilament(self._desanitize(name))
			if path is None:
				path = os.path.join(self.get_slicer_profile_path(slicer)+"/Variants", "{name}.json".format(name=name))
		else:
			name = self._sanitize(name)
			path = os.path.join(self.get_slicer_profile_path(slicer), "{name}.profile".format(name=name))

		if not os.path.realpath(path).startswith(os.path.realpath(self._profile_path)):
			raise IOError("Path to profile {name} tried to break out of allows sub path".format(**locals()))
		if must_exist and not (os.path.exists(path) and os.path.isfile(path)):
			raise UnknownProfile(slicer, name)
		return path

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
			return name

	def _load_profile_from_path(self, slicer, path, require_configured=False):
		profile = self.get_slicer(slicer, require_configured=require_configured).get_slicer_profile(path)
		default_profiles = settings().get(["slicing", "defaultProfiles"])
		if default_profiles and slicer in default_profiles:
			profile.default = default_profiles[slicer] == profile.name
		return profile

	def _save_profile_to_path(self, slicer, path, profile, allow_overwrite=True, overrides=None, require_configured=False):
		self.get_slicer(slicer, require_configured=require_configured).save_slicer_profile(path, profile, allow_overwrite=allow_overwrite, overrides=overrides)

	def _get_default_profile(self, slicer):
		default_profiles = settings().get(["slicing", "defaultProfiles"])
		if default_profiles and slicer in default_profiles:
			try:
				return self.load_profile(slicer, default_profiles[slicer])
			except (UnknownProfile, IOError):
				# in that case we'll use the slicers predefined default profile
				pass

		return self.get_slicer(slicer).get_slicer_default_profile()

	def _create_shallow_profile(self, profile_name, slicer, extensionFile, require_configured, brand=None):

		# reverses the name sanitization
		formatted_name = profile_name.replace('_', ' ').title()
		name_parts = formatted_name.split(' ')

		underscore_flag = False
		formatted_name = ''
		printer_models = settings().get(["printerModels"])
		nozzle_types = settings().get(["nozzleTypes"]).itervalues()
		nozzle_ids = []
		for nzt in nozzle_types:
			nozzle_ids.append(nzt['id'])

		for part in name_parts:
			part_upper_version = part.upper()
			if part == 'Pla' or part == 'Beesupply':
				part = part_upper_version

			if part_upper_version in printer_models or part_upper_version in nozzle_ids:
				formatted_name += '_' + part_upper_version
				underscore_flag = True
			else:
				if underscore_flag:
					formatted_name += '_' + part
				else:
					formatted_name += ' ' + part

		if extensionFile == "json":
			formatted_name = profile_name

		description = profile_name
		profile_dict = {'_display_name': formatted_name}

		properties = self.get_slicer(slicer, require_configured=require_configured).get_slicer_properties()

		return octoprint.slicing.SlicingProfile(properties["type"],
												"unknown", profile_dict, display_name=formatted_name,
												description=description, brand=brand)
