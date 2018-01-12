# coding=utf-8

from __future__ import absolute_import

import math
import time
import logging

import datetime
from octoprint.util import deprecated
from octoprint.util.bee_comm import BeeCom
import os
from octoprint.printer.standard import Printer
from octoprint.printer import PrinterInterface
from octoprint.settings import settings
from octoprint.server.util.connection_util import ConnectionMonitorThread
from octoprint.server.util.printer_status_detection_util import StatusDetectionMonitorThread
from octoprint.events import eventManager, Events
from octoprint.slicing import SlicingManager
from octoprint.filemanager import FileDestinations
from octoprint.util.comm import PrintingFileInformation
from octoprint.printer.statistics import BaseStatistics, PrintEventStatistics, PrinterStatistics
from octoprint.printer.estimation import TimeEstimationHelper
from octoprint.plugins.curaX import ProfileReader

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"


class BeePrinter(Printer):
    """
    BVC implementation of the :class:`PrinterInterface`. Manages the communication layer object and registers
    itself with it as a callback to react to changes on the communication layer.
    """
    TMP_FILE_MARKER = '__tmp-scn'


    def __init__(self, fileManager, analysisQueue, printerProfileManager):
        self._estimatedTime = None
        self._elapsedTime = None
        self._numberLines = None
        self._executedLines = None
        self._currentFeedRate = None
        self._runningCalibrationTest = False
        self._insufficientFilamentForCurrent = False
        self._isConnecting = False
        self._bvc_conn_thread = None
        self._bvc_status_thread = None
        self._current_temperature = 0.0
        self._lastJogTime = None
        self._calibration_step_counter = 0
        self._stats = BaseStatistics()
        self._printerStats = None
        self._currentPrintStatistics = None
        self._currentFileAnalysis = None  # Kept for simple access to send estimations to the printer
        self._targetTemperature = None
        self._printAfterSelect = False

        # Initializes the slicing manager for filament profile information
        self._slicingManager = SlicingManager(settings().getBaseFolder("slicingProfiles"), printerProfileManager)
        self._slicingManager.reload_slicers()
        self._currentFilamentProfile = None
        self._currentNozzle = None
        self._currentFirmware = None
        self._currentPrintOptions = None

        # We must keep a copy of the _currentFile variable (from the comm layer) to allow the situation of
        # disconnecting the printer and maintaining any selected file information after a reconnect is done
        self._currentPrintJobFile = None

        # This list contains the addresses of the clients connected to the server
        self._connectedClients = []

        # Subscribes to the CLIENT_OPENED and CLIENT_CLOSED events to handle each time a client (browser)
        # connects or disconnects
        eventManager().subscribe(Events.CLIENT_OPENED, self.on_client_connected)
        eventManager().subscribe(Events.CLIENT_CLOSED, self.on_client_disconnected)

        # subscribes to FIRMWARE_UPDATE_STARTED and FIRMWARE_UPDATE_FINISHED events in order to signal to the
        # user when either of these operations are triggered
        eventManager().subscribe(Events.FIRMWARE_UPDATE_STARTED, self.on_flash_firmware_started)
        eventManager().subscribe(Events.FIRMWARE_UPDATE_FINISHED, self.on_flash_firmware_finished)
        eventManager().subscribe(Events.FIRMWARE_UPDATE_AVAILABLE, self.on_firmware_update_available)

        # subscribes print event handlers
        eventManager().subscribe(Events.PRINT_STARTED, self.on_print_started)
        eventManager().subscribe(Events.PRINT_PAUSED, self.on_print_paused)
        eventManager().subscribe(Events.PRINT_RESUMED, self.on_print_resumed)
        eventManager().subscribe(Events.PRINT_CANCELLED, self.on_print_cancelled)
        eventManager().subscribe(Events.PRINT_CANCELLED_DELETE_FILE, self.on_print_cancelled_delete_file)
        eventManager().subscribe(Events.PRINT_DONE, self.on_print_finished)

        super(BeePrinter, self).__init__(fileManager, analysisQueue, printerProfileManager)


    def connect(self, port=None, baudrate=None, profile=None):
        """
         This method is responsible for establishing the connection to the printer when there are
         any connected clients (browser or beepanel) to the server.

         Ignores port, baudrate parameters. They are kept just for interface compatibility
        """
        try:
            self._isConnecting = True
            # if there are no connected clients returns
            if len(self._connectedClients) == 0:
                self._isConnecting = False
                return False

            # makes sure the status monitor thread is stopped
            if self._bvc_status_thread is not None:
                self._bvc_status_thread.stop_status_monitor()
                self._bvc_status_thread = None

            if self._comm is not None:
                if not self._comm.isBusy():
                    self._comm.close()
                else:
                    # if the connection is active and the printer is busy aborts a new connection
                    self._isConnecting = False
                    return False

            self._comm = BeeCom(callbackObject=self, printerProfileManager=self._printerProfileManager)

            # returns in case the connection with the printer was not established
            if self._comm is None:
                self._isConnecting = False
                return False

            # If a critical error occurred while establishing the connection (e.g: libusb problems), stops the connection
            # monitor thread
            if self._comm.isError():
                if self._bvc_conn_thread is not None:
                    self._bvc_conn_thread.stop_connection_monitor()
                    self._bvc_conn_thread = None
                self._isConnecting = False
                # forces setState to send the message to the UI
                self._setState(BeeCom.STATE_ERROR)
                return False

            # Stores the object pointer to the main command interface from BEEcom
            bee_commands = self._comm.getCommandsInterface()

            # homes all axis
            if bee_commands is not None and bee_commands.isPrinting() is False:
                bee_commands.home()

            # Updates the printer connection state
            self._comm.updatePrinterState()

            self._isConnecting = False

            printer_name = self.get_printer_name()
            # converts the name to the id
            printer_id = None
            if printer_name is not None:
                printer_id = printer_name.lower().replace(' ', '')

            # selects the printer profile based on the connected printer name
            self._printerProfileManager.select(printer_id)

            # if the printer is printing or in shutdown mode selects the last selected file for print
            # and starts the progress monitor
            lastFile = settings().get(['lastPrintJobFile'])
            if lastFile is not None and (self.is_shutdown() or self.is_printing() or self.is_paused()):
                # Gets the name of the file currently being printed from the printer's memory
                currentPrinterFile = self._comm.getCurrentFileNameFromPrinter()

                if currentPrinterFile is not None and lastFile != currentPrinterFile:
                    # This means the the connection was established with a different printer than before or
                    # the file is missing so we must create a generic (empty) file information with just
                    # the name returned by the printer
                    self.select_file(PrintingFileInformation(currentPrinterFile), False)
                else:
                    # Calls the select_file with the real previous PrintFileInformation object to recover the print status
                    if self._currentPrintJobFile is not None:
                        self.select_file(self._currentPrintJobFile, False)
                    else:
                        self.select_file(lastFile, False)

            elif lastFile is not None and (not self.is_printing() and not self.is_shutdown() and not self.is_paused()):
                # if a connection is established with a printer that is not printing, unselects any previous file
                self._comm.unselectFile()

            # starts the progress monitor if a print is on going
            if self.is_printing():
                self._comm.startPrintStatusProgressMonitor()

            # gets current Filament profile data
            self._currentFilamentProfile = None
            self._currentFilamentProfile = self.getSelectedFilamentProfile()

            # gets the printer nozzle size
            self._currentNozzle = None
            self._currentNozzle = self.getNozzleTypeString()

            # gets the firmware version from the printer
            self._currentFirmware = self.getCurrentFirmware()

            # Starts the printer status monitor thread
            if self._bvc_status_thread is None:
                self._bvc_status_thread = StatusDetectionMonitorThread(self._comm)
                self._bvc_status_thread.start()

            # make sure the connection monitor thread is null so we are able to instantiate a new thread later on
            if self._bvc_conn_thread is not None:
                self._bvc_conn_thread.stop_connection_monitor()
                self._bvc_conn_thread = None

            # instantiates the printer statistics object
            if self._printerStats is None:
                self._printerStats = PrinterStatistics(self.get_printer_serial())

            if self._comm is not None and self._comm.isOperational():
                self._logger.info("Connected to %s!" % printer_name)
                return True

        except Exception as ex:
            self._handleConnectionException(ex)

        return False

    def disconnect(self):
        """
        Closes the connection to the printer.
        """
        self._logger.info("Closing USB printer connection.")
        super(BeePrinter, self).disconnect()

        # Starts the connection monitor thread only if there are any connected clients
        if len(self._connectedClients) > 0 and self._bvc_conn_thread is None:
            self._bvc_conn_thread = ConnectionMonitorThread(self.connect)
            self._bvc_conn_thread.start()

        if self._bvc_status_thread is not None:
            self._bvc_status_thread.stop_status_monitor()
            self._bvc_status_thread = None

    def select_file(self, path, sd, printAfterSelect=False, pos=None):
        """
        Selects a file in the selected filesystem and loads it before printing

        :param path: Absolute path to the file
        :param sd: storage system: SD or LOCAL
        :param printAfterSelect: Flag to signal if the print should start after the selection
        :param pos: currently used to signal calibration test
        :return:
        """
        if self._comm is None:
            self._logger.info("Cannot load file: printer not connected or currently busy")
            return

        if path is not None and isinstance(path, PrintingFileInformation):
            self._comm._currentFile = path
            return

        self._printAfterSelect = printAfterSelect

        # saves the selected file analysis info to be later passed to the printer in the communications layer
        if pos != 'calibration' and self._fileManager.has_analysis(FileDestinations.LOCAL, path):
            self._currentFileAnalysis = self._fileManager.get_metadata(FileDestinations.LOCAL, path)['analysis']

        self._comm.selectFile("/" + path if sd and not settings().getBoolean(["feature", "sdRelativePath"]) else path, sd)

        if not self._comm.isPrinting() and not self._comm.isShutdown():
            self._setProgressData(completion=0)
            self._setCurrentZ(None)

        # saves the path to the selected file
        settings().set(['lastPrintJobFile'], path)
        settings().save()


    # # # # # # # # # # # # # # # # # # # # # # #
    ############# PRINTER ACTIONS ###############
    # # # # # # # # # # # # # # # # # # # # # # #
    def start_print(self, pos=None, printTemperature=None):
        """
        Starts a new print job
        :param pos: Kept for interface purposes (Used in BVC implementation for extra info: in_memory file or gcode analysis data)
        :param printTemperature: The temperature target for the print job
        :return:
        """
        ######## INHERITED CODE FROM STANDARD INTERFACE ########
        if self._comm is None or not self._comm.isOperational() or self._comm.isPrinting():
            return
        with self._selectedFileMutex:
            if self._selectedFile is None:
                return

        # we are happy if the average of the estimates stays within 60s of the prior one
        threshold = settings().getFloat(["estimation", "printTime", "stableThreshold"])
        rolling_window = None
        countdown = None

        with self._selectedFileMutex:
            if self._selectedFile["sd"]:
                # we are interesting in a rolling window of roughly the last 15s, so the number of entries has to be derived
                # by that divided by the sd status polling interval
                rolling_window = 15 / settings().get(["serial", "timeout", "sdStatus"])

                # we are happy when one rolling window has been stable
                countdown = rolling_window
        self._timeEstimationData = TimeEstimationHelper(rolling_window=rolling_window,
                                                        threshold=threshold,
                                                        countdown=countdown)

        self._fileManager.delete_recovery_data()

        self._lastProgressReport = None
        self._updateProgressData()
        self._setCurrentZ(None)
        ######## END INHERITED CODE FROM STANDARD INTERFACE ########

        # Uses the pos parameter to pass the analysis of the file to be printed
        if self._currentFileAnalysis is not None:
            pos = self._currentFileAnalysis

        if printTemperature is None:
            self._targetTemperature = self._get_preheat_temperature_from_filament()
        else:
            self._targetTemperature = printTemperature

        self._comm.startPrint(pos=pos, printTemperature=self._targetTemperature)

        # saves the current PrintFileInformation object so we can later recover it if the printer is disconnected
        self._currentPrintJobFile = self._comm.getCurrentFile()


    def cancel_print(self):
        """
         Cancels the current print job.
        """
        if self._comm is None:
            return

        try:
            self._comm.cancelPrint()

            # reset progress, height, print time
            self._setCurrentZ(None)
            self._setProgressData()
            self._resetPrintProgress()
            self._currentPrintJobFile = None

            # mark print as failure
            if self._selectedFile is not None:
                self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL,
                                            self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), False,
                                            self._printerProfileManager.get_current_or_default()["id"])
                payload = {
                    "file": self._selectedFile["filename"],
                    "origin": FileDestinations.LOCAL
                }
                if self._selectedFile["sd"]:
                    payload["origin"] = FileDestinations.SDCARD

                # deletes the file if it was created with the temporary file name marker
                if BeePrinter.TMP_FILE_MARKER in self._selectedFile["filename"]:
                    eventManager().fire(Events.PRINT_CANCELLED_DELETE_FILE, payload)
                else:
                    eventManager().fire(Events.PRINT_CANCELLED, payload)

                eventManager().fire(Events.PRINT_FAILED, payload)
        except Exception as ex:
            self._logger.error("Error canceling print job: %s" % str(ex))
            eventManager().fire(Events.PRINT_CANCELLED, None)

    def jog(self, axes, relative=True, speed=None, *args, **kwargs):
        """
        Jogs the tool a selected amount in the choosen axis
        :param axes:
        :param relative:
        :param speed:
        :param args:
        :param kwargs:
        :return:
        """
        if isinstance(axes, basestring):
            # legacy parameter format, there should be an amount as first anonymous positional arguments too
            axis = axes

            if not len(args) >= 1:
                raise ValueError("amount not set")
            amount = args[0]
            if not isinstance(amount, (int, long, float)):
                raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

            axes = dict()
            axes[axis] = amount

        if not axes:
            raise ValueError("At least one axis to jog must be provided")

        for axis in axes:
            if not axis in PrinterInterface.valid_axes:
                raise ValueError(
                    "Invalid axis {}, valid axes are {}".format(axis, ", ".join(PrinterInterface.valid_axes)))

        axis = axis.lower()
        if not axis in PrinterInterface.valid_axes:
            raise ValueError("axis must be any of {axes}: {axis}".format(axes=", ".join(PrinterInterface.valid_axes), axis=axis))
        if not isinstance(axes[axis], (int, long, float)):
            raise ValueError("amount must be a valid number: {amount}".format(amount=axes[axis]))

        printer_profile = self._printerProfileManager.get_current_or_default()

        # if the feed rate was manually set uses it
        if self._currentFeedRate is not None:
            movement_speed = self._currentFeedRate * 60
        else:
            movement_speed = printer_profile["axes"][axis]["speed"]

        bee_commands = self._comm.getCommandsInterface()


        # protection against several repeated jog moves within a short period of time
        if self._lastJogTime is not None:
            while (time.time() - self._lastJogTime) < 0.5:
                time.sleep(0.25)
        try:
            if axis == 'x':
                bee_commands.move(axes[axis], 0, 0, None, movement_speed)
            elif axis == 'y':
                bee_commands.move(0, axes[axis], 0, None, movement_speed)
            elif axis == 'z':
                bee_commands.move(0, 0, axes[axis], None, movement_speed)
        except Exception as ex:
            self._logger.exception(ex)

        self._lastJogTime = time.time()

    def home(self, axes):
        """
        Moves the select axes to their home position
        :param axes:
        :return:
        """
        if not isinstance(axes, (list, tuple)):
            if isinstance(axes, (str, unicode)):
                axes = [axes]
            else:
                raise ValueError("axes is neither a list nor a string: {axes}".format(axes=axes))

        validated_axes = filter(lambda x: x in PrinterInterface.valid_axes, map(lambda x: x.lower(), axes))
        if len(axes) != len(validated_axes):
            raise ValueError("axes contains invalid axes: {axes}".format(axes=axes))

        bee_commands = self._comm.getCommandsInterface()

        try:
            if 'z' in axes:
                bee_commands.homeZ()
            elif 'x' in axes and 'y' in axes:
                bee_commands.homeXY()
        except Exception as ex:
            self._logger.exception(ex)

    def extrude(self, amount,feedrate=None):
        """
        Extrudes the defined amount
        :param amount:
        :return:
        """
        if not isinstance(amount, (int, long, float)):
            raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

        printer_profile = self._printerProfileManager.get_current_or_default()
        if feedrate is None:
            extrusion_speed = printer_profile["axes"]["e"]["speed"]
        else:
            extrusion_speed = feedrate

        bee_commands = self._comm.getCommandsInterface()
        bee_commands.move(0, 0, 0, amount, extrusion_speed,wait='3')


    def startHeating(self, selected_filament=None):
        """
        Starts the heating procedure
        :param selected_filament:
        :return:
        """
        try:
            # finds the target temperature based on the selected filament
            if selected_filament:
                filamentProfile = self._slicingManager.load_profile(self._slicingManager.default_slicer, selected_filament,
                                                                    require_configured=False)
            else:
                filamentProfile = self.getSelectedFilamentProfile()

            targetTemperature = 210  # default target temperature
            if filamentProfile is not None and 'unload_temperature' in filamentProfile.data:
                targetTemperature = filamentProfile.data['unload_temperature']

            # resets the current temperature
            self._current_temperature = self._comm.getCommandsInterface().getNozzleTemperature()

            self._targetTemperature = targetTemperature
            self._comm.startHeating(self._targetTemperature)

            return targetTemperature
        except Exception as ex:
            self._logger.error('Error when starting the heating operation: %s' % str(ex))


    def cancelHeating(self):
        """
        Cancels the heating procedure
        :return:
        """
        try:
            return self._comm.cancelHeating()
        except Exception as ex:
            self._logger.error(ex)


    def heatingDone(self):
        """
        Runs the necessary commands after the heating operation is finished
        :return:
        """
        try:
            return self._comm.heatingDone()
        except Exception as ex:
            self._logger.error(ex)


    def unload(self):
        """
        Unloads the filament from the printer
        :return:
        """
        try:
            return self._comm.unload()
        except Exception as ex:
            self._logger.error(ex)


    def load(self):
        """
        Loads the filament to the printer
        :return:
        """
        try:
            return self._comm.load()
        except Exception as ex:
            self._logger.error(ex)


    def setFilamentString(self, filamentStr):
        """
        Saves the filament reference string in the printer memory
        :param filamentStr:
        :return:
        """
        try:
            resp = self._comm.getCommandsInterface().setFilamentString(filamentStr)

            # updates the current filament profile selected in memory
            self._currentFilamentProfile = None
            self.getSelectedFilamentProfile()

            # registers the filament change statistics
            self._stats.register_filament_change()
            self._printerStats.register_filament_change()
            self._save_usage_statistics()

            return resp
        except Exception as ex:
            self._logger.error('Error saving filament string in printer: %s' % str(ex))


    def getSelectedFilamentProfile(self):
        """
        Gets the slicing profile for the currently selected filament in the printer
        Returns the first occurrence of filament name and printer. Ignores resolution and nozzle size.
        :return: Profile or None
        """
        try:
            if self._currentFilamentProfile is None:
                filamentStr = self._comm.getCommandsInterface().getFilamentString()
                if not filamentStr:
                    return None

                #filamentNormalizedName = filamentStr.lower().replace(' ', '_') + '_' + self.getPrinterNameNormalized()
                profiles = self._slicingManager.all_profiles_list_json(self._slicingManager.default_slicer,
                                                        require_configured=False,
                                                        nozzle_size=self.getNozzleTypeString().replace("nz", ""),
                                                        from_current_printer=True)

                if len(profiles) > 0:
                    for key,value in profiles.items():
                        if filamentStr in key:
                            filamentProfile = self._slicingManager.load_profile(self._slicingManager.default_slicer, key,require_configured=False)

                            self._currentFilamentProfile = filamentProfile
                            break

        except Exception as ex:
            self._logger.error('Error getting the current selected filament profile: %s' % str(ex))

        return self._currentFilamentProfile

    def getFilamentString(self):
        """
        Gets the current filament reference string in the printer memory
        :return: string
        """
        try:
            return self._comm.getCommandsInterface().getFilamentString()
        except Exception as ex:
            self._logger.error('Error getting filament string from printer: %s' % str(ex))


    def getFilamentInSpool(self):
        """
        Gets the current amount of filament left in spool
        :return: float filament amount in mm
        """
        try:
            filament = self._comm.getCommandsInterface().getFilamentInSpool()
            if filament < 0:
                # In case the value returned from the printer is not valid returns a high value to prevent false
                # positives of not enough filament available
                return 1000000.0

            return filament
        except Exception as ex:
            self._logger.error('Error getting amount of filament in spool: %s' % str(ex))


    def getFilamentWeightInSpool(self):
        """
        Gets the current amount of filament left in spool
        :return: float filament amount in grams
        """
        # if the setting is disabled, returns null in order to signal the frontend to disable
        # the frontend related UI
        if not settings().get(['feature', 'checkSufficientFilament']):
            return None

        try:
            filament_mm = self._comm.getCommandsInterface().getFilamentInSpool()

            if filament_mm >= 0:
                filament_cm = filament_mm / 10.0

                filament_diameter, filament_density = self.getFilamentSettings()

                filament_radius = float(int(filament_diameter) / 10000.0) / 2.0
                filament_volume = filament_cm * (math.pi * filament_radius * filament_radius)

                filament_weight = filament_volume * filament_density
                return round(filament_weight, 2)
            else:
                # In case the value returned from the printer is not valid returns a high value to prevent false
                # positives of not enough filament available
                return 350.0
        except Exception as ex:
            self._logger.error('Error getting filament weight in spool: %s' % str(ex))


    def setFilamentInSpool(self, filamentInSpool):
        """
        Passes to the printer the amount of filament left in spool
        :param filamentInSpool: Amount of filament in grams
        :return: string Command return value
        """
        try:
            if filamentInSpool < 0:
                self._logger.error('Unable to set invalid filament weight: %s' % filamentInSpool)
                return

            filament_diameter, filament_density = self.getFilamentSettings()

            filament_volume = filamentInSpool / filament_density
            filament_radius = float(int(filament_diameter) / 10000.0) / 2.0
            filament_cm = filament_volume / (math.pi * filament_radius * filament_radius)
            filament_mm = filament_cm * 10.0

            comm_return = self._comm.getCommandsInterface().setFilamentInSpool(filament_mm)

            # updates the current print job information with availability of filament
            self._checkSufficientFilamentForPrint()

            return comm_return
        except Exception as ex:
            self._logger.error('Error setting amount of filament in spool: %s' % str(ex))


    def finishExtruderMaintenance(self):
        """
        This function is only used at the moment for statistics logging because the extruder maintenance operation
        has no need for a final operation
        :return:
        """
        self._stats.register_extruder_maintenance()
        self._printerStats.register_extruder_maintenance()
        self._save_usage_statistics()


    def setNozzleSize(self, nozzleSize):
        """
        Saves the selected nozzle size
        :param nozzleSize:
        :return:
        """
        try:
            res = self._comm.getCommandsInterface().setNozzleSize(nozzleSize)

            # updates the current nozzle size saved in memory
            self._currentNozzle = None
            self.getNozzleTypeString()

            # registers the nozzle change statistics
            self._stats.register_nozzle_change()
            self._printerStats.register_nozzle_change()
            self._save_usage_statistics()

            return res
        except Exception as ex:
            self._logger.error(ex)


    def getNozzleSize(self):
        """
        Gets the current selected nozzle size in the printer memory
        :return: float
        """
        try:
            default_nozzle = 400

            printer_nozzle = self._comm.getCommandsInterface().getNozzleSize()
            if printer_nozzle is not None:
                return printer_nozzle
        except Exception as ex:
            self._logger.error(ex)

        return default_nozzle

    def getNozzleTypes(self):
        """
        Gets the list of nozzles available for the printer connected
        :return:
        """
        if self.getPrinterNameNormalized() == "beethefirst":
            return {'nz1': {'id': 'NZ400', 'value': 0.4}}
        return settings().get(["nozzleTypes"])

    def getNozzleTypeString(self):
        """
        Gets the current selected nozzle type string to use for filament filtering
        If not printer is connected returns 'nz400'
        :return: string
        """
        try:
            if self._currentNozzle is None:
                nozzle_type_prefix = 'nz'
                default_nozzle_size = 400

                if self._comm and self._comm.getCommandsInterface():
                    valid_nozzle_sizes = [400, 600]
                    current_nozzle = self._comm.getCommandsInterface().getNozzleSize()

                    if current_nozzle is not None and current_nozzle in valid_nozzle_sizes:
                        self._currentNozzle = nozzle_type_prefix + str(current_nozzle)

                self._currentNozzle = nozzle_type_prefix + str(default_nozzle_size)
        except Exception as ex:
            self._logger.error(ex)

        return self._currentNozzle

    def startCalibration(self, repeat=False):
        """
        Starts the calibration procedure
        :param repeat:
        :return:
        """
        try:
            self._calibration_step_counter = 0
            return self._comm.getCommandsInterface().startCalibration(repeat=repeat)
        except Exception as ex:
            self._logger.error(ex)


    def nextCalibrationStep(self):
        """
        Goes to the next calibration step
        :return:
        """
        try:
            res = self._comm.getCommandsInterface().goToNextCalibrationPoint()
            self._calibration_step_counter += 1
            # registers the calibration statistics
            if self._calibration_step_counter == 2:
                self._stats.register_calibration()
                self._printerStats.register_calibration()
                self._save_usage_statistics()

            return res
        except Exception as ex:
            self._logger.error(ex)


    def startCalibrationTest(self):
        """
        Starts the printer calibration test
        :return:
        """
        try:
            """
            TODO: For now we will hard-code a fixed string to fetch the calibration GCODE, since it is the same for all
            the "first version" printers. In the future this function call must use the printer name for dynamic fetch
            of the correct GCODE, using self._printerProfileManager.get_current_or_default()['name'] to get the current
            printer name
            """
            test_gcode = CalibrationGCoder.get_calibration_gcode('BVC_BEETHEFIRST_V1')
            lines = test_gcode.split(',')

            file_path = os.path.join(settings().getBaseFolder("uploads"), 'BEETHEFIRST_calib_test.gcode')
            calibtest_file = open(file_path, 'w')
            for line in lines:
                calibtest_file.write(line + '\n')
            calibtest_file.close()

            self._runningCalibrationTest = True
            self.select_file(file_path, False, pos='calibration')
            self.start_print()

            # registers the calibration statistics
            self._stats.register_calibration_test()
            self._printerStats.register_calibration_test()
            self._save_usage_statistics()

        except Exception as ex:
            self._logger.error('Error printing calibration test : %s' % str(ex))

        return None


    def cancelCalibrationTest(self):
        """
        Cancels the running calibration test
        :return:
        """
        self.cancel_print()
        self.endCalibrationTest()

        return None

    def endCalibrationTest(self):
        """
        Runs the necessary cleanups after the calibration test
        :return:
        """
        try:
            self._runningCalibrationTest = False
            file_path = os.path.join(settings().getBaseFolder("uploads"), 'BEETHEFIRST_calib_test.gcode')
            self._fileManager.remove_file(FileDestinations.LOCAL, file_path)
        except Exception as ex:
            self._logger.error('Error finishing calibration test : %s' % str(ex))


    def toggle_pause_print(self):
        """
        Pauses the current print job if it is currently running or resumes it if it is currently paused.
        """
        if self.is_printing():
            self.pause_print()
        elif self.is_paused() or self.is_shutdown():
            self.resume_print()


    def resume_print(self):
        """
        Resume the current printjob.
        """
        if self._comm is None:
            return

        if not self._comm.isPaused() and not self._comm.isShutdown():
            return

        self._comm.setPause(False)

    def unselect_file(self):
        """
        Unselects the current file ready for print and removes it if it's a temporary one
        :return:
        """
        if self._selectedFile is not None:
            payload = {
                "file": self._selectedFile["filename"],
                "origin": FileDestinations.LOCAL
            }
            if self._selectedFile["sd"]:
                payload["origin"] = FileDestinations.SDCARD

            # deletes the file if it was created with the temporary file name marker
            if BeePrinter.TMP_FILE_MARKER in self._selectedFile["filename"]:
                eventManager().fire(Events.PRINT_CANCELLED_DELETE_FILE, payload)
            else:
                eventManager().fire(Events.PRINT_CANCELLED, payload)


    # # # # # # # # # # # # # # # # # # # # # # #
    ########  GETTER/SETTER FUNCTIONS  ##########
    # # # # # # # # # # # # # # # # # # # # # # #

    def getPrintProgress(self):
        """
        Gets the current progress of the print job
        :return:
        """
        if self._numberLines is not None and self._executedLines is not None and self._numberLines > 0:
            return float(self._executedLines) / float(self._numberLines)
        else:
            return -1


    def getPrintFilepos(self):
        """
        Gets the current position in file being printed
        :return:
        """
        if self._executedLines is not None:
            return self._executedLines
        else:
            return 0


    def getCurrentProfile(self):
        """
        Returns current printer profile
        :return:
        """
        if self._printerProfileManager is not None:
            return self._printerProfileManager.get_current_or_default()
        else:
            return None


    def getPrinterName(self):
        """
        Returns the name of the connected printer
        :return:
        """
        if self._comm is not None:
            return self._comm.getConnectedPrinterName()
        else:
            return None

    def getPrinterNameNormalized(self):
        """
        Returns the name of the connected printer with lower case and without spaces
        the same way it's used in the filament profile names
        :return:
        """
        printer_name = self.getPrinterName()
        if printer_name:
            printer_name = self.getPrinterName().replace(' ', '').lower()
            #printers with older bootloader
            if printer_name == 'beethefirst-bootloader':
                return "beethefirst"
            #prototype printer beethefirst+A
            elif printer_name == 'beethefirstplusa':
                return "beethefirstplus"
            # prototype printer beeinschoolA
            elif printer_name == 'beeinschoola':
                return "beeinschool"
            return printer_name

        return None

    def feed_rate(self, factor):
        """
        Updates the feed rate factor
        :param factor:
        :return:
        """
        factor = self._convert_rate_value(factor, min=50, max=200)
        self._currentFeedRate = factor


    def get_current_temperature(self):
        """
        Returns the current extruder temperature
        :return:
        """
        try:
            temp = self._comm.getCommandsInterface().getNozzleTemperature()

            if not self.is_heating():
                self._current_temperature = temp
            else:
                # small verification to prevent temperature update errors coming from the printer due to sensor noise
                # the temperature is only updated to a new value if it's greater than the previous when the printer is
                # heating
                if temp > 0 and temp > self._current_temperature:
                    self._current_temperature = temp

            return self._current_temperature
        except Exception as ex:
            self._logger.error(ex)

    def set_nozzle_temperature(self, temperature):
        """
        Saves the selected nozzle temperature
        :param temperature:
        :return:
        """
        try:
            return self._comm.getCommandsInterface().setNozzleTemperature(temperature)
        except Exception as ex:
            self._logger.error(ex)

    def isRunningCalibrationTest(self):
        """
        Updates the running calibration test flag
        :return:
        """
        return self._runningCalibrationTest


    def isValidNozzleSize(self, nozzleSize):
        """
        Checks if the passed nozzleSize value is valid
        :param nozzleSize:
        :return:
        """
        for k,v in settings().get(['nozzleTypes']).iteritems():
            if v['value'] == nozzleSize:
                return True

        return False


    def is_preparing_print(self):
        return self._comm is not None and self._comm.isPreparingPrint()

    def is_transferring(self):
        return self._comm is not None and self._comm.isTransferring()

    def is_heating(self):
        return self._comm is not None and (self._comm.isHeating() or self._comm.isPreparingPrint())


    def is_shutdown(self):
        return self._comm is not None and self._comm.isShutdown()


    def is_resuming(self):
        return self._comm is not None and self._comm.isResuming()

    def is_connecting(self):
        return self._isConnecting

    def get_state_string(self, state=None):
        """
         Returns a human readable string corresponding to the current communication state.
        """
        if self._comm is None:
            if self.is_connecting():
                return "Connecting..."
            else:
                return "Disconnected"
        else:
            return self._comm.getStateString()


    def getCurrentFirmware(self):
        """
        Gets the current printer firmware version
        :return: string
        """
        try:
            if self._comm is not None and self._comm.getCommandsInterface() is not None:
                firmware_v = self._comm.getCommandsInterface().getFirmwareVersion()

                if firmware_v is not None:
                    return firmware_v
                else:
                    return 'Not available'
            else:
                return 'Not available'
        except Exception as ex:
            self._logger.exception(ex)

    def get_printer_serial(self):
        """
         Returns a human readable string corresponding to name of the connected printer.
        """
        if self._comm is None:
            return ""
        else:
            return self._comm.getConnectedPrinterSN()

    def getFilamentSettingsForPrinter(self):
        """
        Gets the necessary filament settings for weight/size conversions
        Returns tuple with (diameter,density)
        """
        # Normalizes the printer ID to be found in the CuraX profiles
        printerId = self.getPrinterName().replace(' ', '').replace('-bootloader', '').lower()
        printerId = 'BEEVERYCREATIVE-' + printerId

        printerProfileSettings = ProfileReader.getPrinterJsonFileByid(
            printerId,
            self._slicingManager.get_slicer_profile_path(self._slicingManager.default_slicer) + '/',
            load_parents_inherits=True
        )

        try:
            filament_diameter = printerProfileSettings['inherits']['overrides']['material']['material_diameter']['default_value'] * 1000
        except KeyError:
            filament_diameter = 1.75 * 1000  # default value in microns

        # TODO: The filament density should be set based on profile data
        filament_density = 1.275  # default value

        return filament_diameter, filament_density

    def printFromMemory(self):
        """
        Prints the file currently in the printer memory
        :param self:
        :return:
        """
        try:
            if self._comm is None:
                self._logger.info("Cannot print from memory: printer not connected or currently busy")
                return

            # bypasses normal octoprint workflow to print from memory "special" file
            self._comm.selectFile('Memory File', False)

            self._setProgressData(completion=0)
            self._setCurrentZ(None)  # determines preheat temperature for filament

            self._targetTemperature = self._get_preheat_temperature_from_filament()

            return self._comm.startPrint('from_memory', self._targetTemperature)
        except Exception as ex:
            self._logger.error(ex)

    def saveUserFeedback(self, print_success=True, print_rating=0, observations=None):
        """
        Saves the user feedback sent from the API through the user interface
        :param print_success:
        :param print_rating:
        :param observations:
        :return:
        """
        try:
            if self._currentPrintStatistics is not None:
                self._currentPrintStatistics.set_user_feedback(print_success, print_rating, observations)
                self._save_usage_statistics()

                # we must "close" the statistics for this print operation since after the user feedback there is no more info to collect
                self._currentPrintStatistics = None

            return True, "feedback saved"
        except Exception as ex:
            self._logger.error('Error saving user feedback after print finished: %s' % str(ex))

            return False, str(ex)

    def saveModelsInformation(self, models_info):
        """
        Saves the information about the 3D models currently being printed
        :param models_info:
        :return:
        """
        try:
            if self._currentPrintStatistics is None:
                self._currentPrintStatistics = PrintEventStatistics(self.get_printer_serial(),
                                                                    self._stats.get_software_id())

            self._currentPrintStatistics.set_model_information(models_info)

            return True
        except Exception as ex:
            self._logger.error('Error saving 3D model information statistics: %s' % str(ex))

            return False

    def savePrintOptions(self, resolution, density, platform_adhesion, support, advanced_options=None):
        """
        Saves the print options information about the print/slicing job
        :param resolution:
        :param density:
        :param platform_adhesion:
        :param support:
        :param advanced_options:
        :return:
        """
        try:
            if self._currentPrintStatistics is None:
                self._currentPrintStatistics = PrintEventStatistics(self.get_printer_serial(),
                                                                    self._stats.get_software_id())
            self._currentPrintStatistics.set_print_options(resolution, density, platform_adhesion, support, advanced_options)

            return True

        except Exception as ex:
            self._logger.error('Error saving Print options information for statistics: %s' % str(ex))

        return False

    def getExtruderStepsMM(self):
        """
        Gets extruder steps per mm
        :return:
        """
        try:
            if self._comm is None:
                self._logger.info("Cannot get extruder steps: printer not connected or currently busy")
                return

            return self._comm.getExtruderStepsMM()
        except Exception as ex:
            self._logger.error(ex)

        return

    def setExtruderStepsMM(self, measuredFilamentInput=None, extrudedAmmount=250):
        """
        Sets extruder steps per mm
        :param extrudedAmmount: expected extruded ammount
        :param measuredFilamentInput:
        :return:
        """
        try:
            if self._comm is None:
                self._logger.info("Cannot set extruder steps: printer not connected or currently busy")
                return

            if measuredFilamentInput and measuredFilamentInput >= 100:
                currSteps = float(self.getExtruderStepsMM())
                newSteps = currSteps * float(extrudedAmmount) / float(measuredFilamentInput)
                return self._comm.setExtruderStepsMM('{0:.2f}'.format(newSteps))
            elif measuredFilamentInput is None:
                return self._comm.setExtruderStepsMM('{0:.4f}'.format(441.3897))
            else:
                raise Exception('Invalid Extruder value input')
        except Exception as ex:
            self._logger.error(ex)

        return

    def isExtruderCalibrationRequired(self):
        try:
            if self._comm is None:
                self._logger.info("Cannot get extruder calibration status: printer not connected or currently busy")
                return False

            return self._comm.isExtruderCalibrationRequired()

        except Exception as ex:
            self._logger.error(ex)

        return False

    def resetPrinterSettings(self):
        try:
            if self._comm is None:
                self._logger.info("Cannot reset printer configuration settings: printer not connected or currently busy")
                return False

            return self._comm.reset_printer_settings()

        except Exception as ex:
            self._logger.error(ex)

        return False

    # # # # # # # # # # # # # # # # # # # # # # #
    ##########  CALLBACK FUNCTIONS  #############
    # # # # # # # # # # # # # # # # # # # # # # #
    def updateProgress(self, progressData):
        """
        Receives a progress data object from the BVC communication layer
        and updates the progress attributes

        :param progressData:
        :return:
        """
        if progressData is not None and self._selectedFile is not None:
            if 'Elapsed Time' in progressData:
                self._elapsedTime = progressData['Elapsed Time']
            if 'Estimated Time' in progressData:
                self._estimatedTime = progressData['Estimated Time']
            if 'Executed Lines' in progressData:
                self._executedLines = progressData['Executed Lines']
            if 'Lines' in progressData:
                self._numberLines = progressData['Lines']


    def on_comm_progress(self):
        """
         Callback method for the comm object, called upon any change in progress of the print job.
         Triggers storage of new values for printTime, printTimeLeft and the current progress.
        """
        if self._comm is not None:
            progress = self.getPrintProgress()
            self._setProgressData(progress, self.getPrintFilepos(),
                                  self._comm.getPrintTime(), self._comm.getCleanedPrintTime())

            # If the status from the printer is no longer printing runs the post-print trigger
            try:
                if progress >= 1:
                    # Runs the print finish communications callback
                    self._comm.triggerPrintFinished()

                    if self._runningCalibrationTest:
                        self.endCalibrationTest()

                    self._setProgressData()
                    self._resetPrintProgress()

                    # makes sure the thread that is communicating with the print progress is stopped
                    self._comm.getCommandsInterface().stopPrintStatusMonitor()

            except Exception as ex:
                self._logger.error(ex)


    def on_comm_file_selected(self, filename, filesize, sd):
        """
        Override callback function to allow for print halt when there is not enough filament
        :param filename:
        :param filesize:
        :param sd:
        :return:
        """
        self._setJobData(filename, filesize, sd)
        self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

        # If the checkSufficientFilament flag is set in the settings, checks for sufficient filament for the print job
        if settings().get(['features', 'checkSufficientFilament']):
            self._checkSufficientFilamentForPrint()

            # checks if the insufficient filament flag is true and halts the print process
            if self._insufficientFilamentForCurrent:
                self._printAfterSelect = False

        if self._printAfterSelect:
            self._printAfterSelect = False
            self.start_print(pos=self._posAfterSelect)

    def on_print_started(self, event, payload):
        """
        Print paused callback for the EventManager.
        """
        # logs a new print statistics
        if not self.isRunningCalibrationTest():
            self._stats.register_print() # logs software statistics
            self._printerStats.register_print() # logs printer specific statistics

            if self._currentPrintStatistics is None:
                self._currentPrintStatistics = PrintEventStatistics(self.get_printer_serial(), self._stats.get_software_id())

            self._currentPrintStatistics.set_print_start(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
            self._register_filament_statistics()

            self._currentPrintStatistics.set_firmware_version(self._currentFirmware)
            from octoprint import  __display_version__
            self._currentPrintStatistics.set_software_version(__display_version__)

            self._save_usage_statistics()

    def on_print_paused(self, event, payload):
        """
        Print paused callback for the EventManager.
        """
        if self._currentPrintStatistics is not None:
            self._currentPrintStatistics.set_print_paused(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
            # removes redundant information
            self._currentPrintStatistics.remove_redundant_information()

            self._save_usage_statistics()

    def on_print_resumed(self, event, payload):
        """
        Print resume callback for the EventManager.
        """
        if self._currentPrintStatistics is not None:
            self._currentPrintStatistics.set_print_resumed(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
            self._register_filament_statistics()

            self._save_usage_statistics()

    def on_print_cancelled(self, event, payload):
        """
        Print cancelled callback for the EventManager.
        """
        super(BeePrinter, self).unselect_file()

        if self._currentPrintStatistics is not None:
            self._currentPrintStatistics.set_print_cancelled(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
            # removes redundant information
            self._currentPrintStatistics.remove_redundant_information()
            self._save_usage_statistics()

            # we can close the current print job statistics
            self._currentPrintStatistics = None
            self._currentPrintOptions = None


    def on_print_cancelled_delete_file(self, event, payload):
        """
        Print cancelled callback for the EventManager.
        """
        try:
            self.on_print_cancelled(event, payload)

            self._fileManager.remove_file(payload['origin'], payload['file'])
        except RuntimeError as re:
            self._logger.exception(re)
        except Exception as e:
            self._logger.exception('Error deleting temporary GCode file: %s' % str(e))

    def on_comm_state_change(self, state):
        """
        Callback method for the comm object, called if the connection state changes.
        """
        if state == BeeCom.STATE_CLOSED or state == BeeCom.STATE_CLOSED_WITH_ERROR:
            if self._comm is not None:
                self._comm = None

        self._setState(state)


    def on_print_finished(self, event, payload):
        """
        Event listener to when a print job finishes
        :return:
        """
        # log print statistics
        if not self.isRunningCalibrationTest() and self._currentPrintStatistics is not None:
            # total print time in seconds
            total_print_time = self._comm.getCleanedPrintTime()
            if total_print_time is None or total_print_time <= 0:
                #this means that probably the printer was disconnected during the print the actual print job lost it's information
                total_print_time = self._elapsedTime
            self._currentPrintStatistics.set_total_print_time(round(total_print_time, 1))

            self._currentPrintStatistics.set_print_finished(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
            # removes redundant information
            self._currentPrintStatistics.remove_redundant_information()

            # TODO: This line should be removed after saveUserFeedback is re-activated again
            self._save_usage_statistics()
            self._currentPrintOptions = None

        # un-selects the current file
        super(BeePrinter, self).unselect_file()
        self._currentPrintJobFile = None

        if BeePrinter.TMP_FILE_MARKER in payload["file"]:
            try:
                self._fileManager.remove_file(payload['origin'], payload['file'])
            except RuntimeError as re:
                self._logger.exception(re)
            except Exception as e:
                self._logger.exception('Error deleting temporary GCode file: %s' % str(e))


    def on_client_connected(self, event, payload):
        """
        Event listener to execute when a client (browser) connects to the server
        :param event:
        :param payload:
        :return:
        """
        # Only appends the client address to the list. The connection monitor thread will automatically handle
        # the connection itself
        if payload['remoteAddress'] not in self._connectedClients:
            self._connectedClients.append(payload['remoteAddress'])

            # Starts the connection monitor thread
            if self._bvc_conn_thread is None and (self._comm is None or (self._comm is not None and not self._comm.isOperational())):
                self._bvc_conn_thread = ConnectionMonitorThread(self.connect)
                self._bvc_conn_thread.start()


    def on_client_disconnected(self, event, payload):
        """
        Event listener to execute when a client (browser) disconnects from the server
        :param event:
        :param payload:
        :return:
        """
        if payload['remoteAddress'] in self._connectedClients:
            self._connectedClients.remove(payload['remoteAddress'])

        # if there are no more connected clients stops the connection monitor thread to release the USB connection
        if len(self._connectedClients) == 0 and self._bvc_conn_thread is not None:
            self._bvc_conn_thread.stop_connection_monitor()
            self._bvc_conn_thread = None

        # Disconnects the printer connection if the connection is active
        if len(self._connectedClients) == 0 and self._comm is not None:
            # calls only the disconnect function on the parent class instead of the complete bee_printer.disconnect
            # which also handles the connection monitor thread. This thread will be handled automatically when
            # the disconnect function is called by the beecom driver disconnect hook
            super(BeePrinter, self).disconnect()

    def on_flash_firmware_started(self, event, payload):
        for callback in self._callbacks:
            try:
                callback.sendFlashingFirmware(payload['version'])
            except:
                self._logger.exception("Exception while notifying client of firmware update operation start")

    def on_flash_firmware_finished(self, event, payload):
        for callback in self._callbacks:
            try:
                callback.sendFinishedFlashingFirmware(payload['result'])
            except:
                self._logger.exception("Exception while notifying client of firmware update operation finished")

    def on_firmware_update_available(self, event, payload):
        for callback in self._callbacks:
            try:
                callback.sendFirmwareUpdateAvailable(payload['version'])
            except:
                self._logger.exception("Exception while notifying client of firmware update available")

    # # # # # # # # # # # # # # # # # # # # # # #
    ########### AUXILIARY FUNCTIONS #############
    # # # # # # # # # # # # # # # # # # # # # # #

    def _setJobData(self, filename, filesize, sd):
        with self._selectedFileMutex:
            if filename is not None:
                if sd:
                    name_in_storage = filename
                    if name_in_storage.startswith("/"):
                        name_in_storage = name_in_storage[1:]
                    path_in_storage = name_in_storage
                    path_on_disk = None
                else:
                    path_in_storage = self._fileManager.path_in_storage(FileDestinations.LOCAL, filename)
                    path_on_disk = self._fileManager.path_on_disk(FileDestinations.LOCAL, filename)
                    _, name_in_storage = self._fileManager.split_path(FileDestinations.LOCAL, path_in_storage)

                self._selectedFile = {
                    "filename": path_in_storage,
                    "filesize": filesize,
                    "sd": sd,
                    "estimatedPrintTime": None
                }
            else:
                self._selectedFile = None
                self._stateMonitor.set_job_data({
                    "file": {
                        "name": None,
                        "path": None,
                        "origin": None,
                        "size": None,
                        "date": None
                    },
                    "estimatedPrintTime": None,
                    "averagePrintTime": None,
                    "lastPrintTime": None,
                    "filament": None,
                })
                return

            estimatedPrintTime = None
            lastPrintTime = None
            averagePrintTime = None
            date = None
            filament = None
            if path_on_disk and os.path.exists(path_on_disk):
                # Use a string for mtime because it could be float and the
                # javascript needs to exact match
                if not sd:
                    date = int(os.stat(path_on_disk).st_mtime)

                try:
                    fileData = self._fileManager.get_metadata(FileDestinations.SDCARD if sd else FileDestinations.LOCAL,
                                                              path_on_disk)
                except:
                    fileData = None
                if fileData is not None:
                    if "analysis" in fileData:
                        if estimatedPrintTime is None and "estimatedPrintTime" in fileData["analysis"]:
                            estimatedPrintTime = fileData["analysis"]["estimatedPrintTime"]
                        if "filament" in fileData["analysis"].keys():
                            filament = fileData["analysis"]["filament"]
                    if "statistics" in fileData:
                        printer_profile = self._printerProfileManager.get_current_or_default()["id"]
                        if "averagePrintTime" in fileData["statistics"] and printer_profile in fileData["statistics"][
                            "averagePrintTime"]:
                            averagePrintTime = fileData["statistics"]["averagePrintTime"][printer_profile]
                        if "lastPrintTime" in fileData["statistics"] and printer_profile in fileData["statistics"][
                            "lastPrintTime"]:
                            lastPrintTime = fileData["statistics"]["lastPrintTime"][printer_profile]

                    if averagePrintTime is not None:
                        self._selectedFile["estimatedPrintTime"] = averagePrintTime
                        self._selectedFile["estimatedPrintTimeType"] = "average"
                    elif estimatedPrintTime is not None:
                        # TODO apply factor which first needs to be tracked!
                        self._selectedFile["estimatedPrintTime"] = estimatedPrintTime
                        self._selectedFile["estimatedPrintTimeType"] = "analysis"

            self._stateMonitor.set_job_data({
                "file": {
                    "name": name_in_storage,
                    "path": path_in_storage,
                    "origin": FileDestinations.SDCARD if sd else FileDestinations.LOCAL,
                    "size": filesize,
                    "date": date
                },
                "estimatedPrintTime": estimatedPrintTime,
                "averagePrintTime": averagePrintTime,
                "lastPrintTime": lastPrintTime,
                "filament": filament,
            })


    def _printJobFilamentLength(self):
        """
        Returns the amount of filament (mm) that will be used for the current print job. If no data is found return None
        """
        # Gets the current print job data
        state_data = self._stateMonitor.get_current_data()

        if state_data['job']['filament'] is not None:
            # gets the filament information for the filament weight to be used in the print job
            filament_extruder = state_data['job']['filament']["tool0"]

            return filament_extruder['length']

        return None

    def _checkSufficientFilamentForPrint(self):
        """
        Checks if the current print job has enough filament to complete. By updating the
        job setting, it will automatically update the interface through the web socket
        :return:
        """
        if not self.is_printing():
            try:
                # Gets the current print job data
                state_data = self._stateMonitor.get_current_data()

                # gets the current amount of filament left in printer
                current_filament_length = self.getFilamentInSpool()
                print_job_filament = self._printJobFilamentLength()

                if print_job_filament is not None:
                    # gets the filament information for the current print job
                    filament_extruder = state_data['job']['filament']["tool0"]

                    if print_job_filament > current_filament_length:
                        filament_extruder['insufficient'] = True
                        self._insufficientFilamentForCurrent = True
                    else:
                        filament_extruder['insufficient'] = False
                        self._insufficientFilamentForCurrent = False
            except Exception as ex:
                self._logger.error('Error checking for sufficient filament for print: %s' % str(ex))


    def _setProgressData(self, completion=None, filepos=None, printTime=None, printTimeLeft=None):
        """
        Auxiliar method to control the print progress status data
        :param completion:
        :param filepos:
        :param printTime:
        :param printTimeLeft: Kept for interface purposes
        :return:
        """
        try:
            if self._selectedFile and "estimatedPrintTime" in self._selectedFile \
                    and self._selectedFile["estimatedPrintTime"]:
                totalPrintTime = self._selectedFile["estimatedPrintTime"]
            else:
                totalPrintTime = self._estimatedTime # This information comes from the progress update from the printer

            self._progress = completion

            # if the printTime information is null, probably the current file object being used by the comm layer
            # does not contain this information either because the printer changed computer, could be a print from a
            # previous file in memory or a recovery from shutdown
            if printTime is None:
                printTime = self._elapsedTime

            self._printTimeLeft = totalPrintTime - printTime if (totalPrintTime is not None and printTime is not None) else None

        except Exception as ex:
            self._logger.error('Error setting print progress data: %s' % str(ex))

        try:
            fileSize=int(self._selectedFile['filesize'])
        except Exception:
            fileSize=None

        try:
            self._stateMonitor.set_progress({
                "completion": self._progress * 100 if self._progress is not None else None,
                "filepos": filepos,
                "printTime": int(self._elapsedTime * 60) if self._elapsedTime is not None else None,
                "printTimeLeft": int(self._printTimeLeft) if self._printTimeLeft is not None else None,
                "fileSizeBytes": fileSize,
                "temperatureTarget": self._targetTemperature
            })

            if completion:
                progress_int = int(completion * 100)
                if self._lastProgressReport != progress_int:
                    self._lastProgressReport = progress_int
                    self._reportPrintProgressToPlugins(progress_int)

        except Exception as ex:
            self._logger.error(ex)


    def _resetPrintProgress(self):
        """
        Resets the progress variables responsible for storing the information that comes
        from the printer during the print progress updates
        :return:
        """
        self._elapsedTime = 0
        self._estimatedTime = 0
        self._executedLines = 0
        self._numberLines = 0


    def _getStateFlags(self):
        return {
            "operational": self.is_operational(),
            "printing": self.is_printing(),
            "closedOrError": self.is_closed_or_error(),
            "error": self.is_error(),
            "paused": self.is_paused(),
            "ready": self.is_ready(),
            "transfering":  self.is_transferring(),
            "sdReady": self.is_sd_ready(),
            "heating": self.is_heating(),
            "shutdown": self.is_shutdown(),
            "resuming": self.is_resuming(),
        }


    def _handleConnectionException(self, ex):

        eventManager().fire(Events.DISCONNECTED)
        self._logger.error("Error connecting to BVC printer: %s" % str(ex))

        self._isConnecting = False
        if self._comm is not None:
            self._comm.close()
            self._comm = None

        # Starts the connection monitor thread only if there are any connected clients and the thread was stopped
        if len(self._connectedClients) > 0 and self._bvc_conn_thread is None:
            self._bvc_conn_thread = ConnectionMonitorThread(self.connect)
            self._bvc_conn_thread.start()
        # stops the status thread if it was started previously
        if self._bvc_status_thread is not None:
            self._bvc_status_thread.stop()
            self._bvc_status_thread = None


    def _register_filament_statistics(self):
        filament = self.getSelectedFilamentProfile()
        if filament is not None:
            filament_amount = self._printJobFilamentLength()  # amount in mm

            display_name = filament.display_name
            material = 'PLA'
            if 'inherits' in filament.data:
                material = filament.data['inherits']['name']

            brand = 'Undefined'
            if filament.brand:
                brand = filament.brand

            self._currentPrintStatistics.set_filament_used(display_name, material, filament.name, brand, filament_amount)

    def _save_usage_statistics(self):
        """
        Logs the print statistics after a print has finished
        :return:
        """
        # saves the base software statistics
        self._stats.save()

        # saves the printer specific statistics
        self._printerStats.save()

        # saves the print statistics details
        if self._currentPrintStatistics is not None:
            self._currentPrintStatistics.save()

    def _get_preheat_temperature_from_filament(self):
        filamentProfile = self.getSelectedFilamentProfile()

        defaultPreheatTemperature = 210  # default target temperature

        if filamentProfile is not None and 'preheat_temperature' in filamentProfile.data:
            return filamentProfile.data['preheat_temperature']
        else:
            return defaultPreheatTemperature

    @deprecated
    def _sendAzureUsageStatistics(self, operation):
        """
        Calls and external executable to send usage statistics to a remote cloud server
        :param operation: Supports 'start' (Start Print), 'cancel' (Cancel Print), 'stop' (Print finished) operations
        :return: true in case the operation was successful or false if not
        """
        import sys
        if not sys.platform == "darwin" and not sys.platform == "win32":
            _logger = logging.getLogger()
            biExePath = settings().getBaseFolder('bi') + '/bi_azure'

            if operation != 'start' and operation != 'cancel' and operation != 'stop':
                return False

            if os.path.exists(biExePath) and os.path.isfile(biExePath):

                printerSN = self.get_printer_serial()

                if printerSN is None:
                    _logger.error("Could not get Printer Serial Number for statistics communication.")
                    return False
                else:
                    cmd = '%s %s %s' % (biExePath,str(printerSN), str(operation))
                    _logger.info(u"Running %s" % cmd)

                    import subprocess
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)

                    (output, err) = p.communicate()

                    p_status = p.wait()

                    if p_status == 0 and 'IOTHUB_CLIENT_CONFIRMATION_OK' in output:
                        _logger.info(u"Statistics sent to remote server. (Operation: %s)" % operation)
                        return True
                    else:
                        _logger.info(u"Failed sending statistics to remote server. (Operation: %s)" % operation)

        return False


class CalibrationGCoder:

    _calibration_gcode = { 'BVC_BEETHEFIRST_V1' :'M29,'
                'M300 ;3.X.X - 2013-12-05,'
                'M206 X500		; SET ACCEL = 500mm/s^2,'
                'M107			; TURN OFF FAN,'
                'M104 S220		; HEAT DONT WAIT,'
                'G1 X-98.0 Y-20.0 Z5.0 F3000,'
                'G1 Y-68.0 Z0.3,'
                'G1 X-98.0 Y0.0 F500 E20,'
                'G92 E			;RESET FILAMENT,'
                'M106			;TURN FAN ON,'
                'M113 S1.0,'
                'M107 ; First Layer Blower OFF,'
                'M108 S12.24,'
                'M104 S205.0,'
                'G1 X-85.86957 Y-58.8909 Z0.15 F3600.0,'
                'G1 F6000.0,'
                'G1 E0.5,'
                'G1 F3600.0,'
                'M101,'
                'G1 X-85.20188 Y-59.34014 Z0.15 F648.0 E0.54773,'
                'G1 X-84.65842 Y-59.56525 E0.58262,'
                'G1 X-84.08642 Y-59.70257 E0.61751,'
                'G1 X84.08642 Y-59.70257 E10.59227,'
                'G1 X84.65842 Y-59.56525 E10.62716,'
                'G1 X85.20188 Y-59.34014 E10.66205,'
                'G1 X85.70344 Y-59.03279 E10.69694,'
                'G1 X86.15074 Y-58.65075 E10.73183,'
                'G1 X86.53279 Y-58.20344 E10.76672,'
                'G1 X86.84014 Y-57.70188 E10.80161,'
                'G1 X87.06525 Y-57.15842 E10.8365,'
                'G1 X87.20257 Y-56.58643 E10.87139,'
                'G1 X87.20257 Y56.58643 E17.58396,'
                'G1 X87.06525 Y57.15842 E17.61885,'
                'G1 X86.84014 Y57.70188 E17.65374,'
                'G1 X86.53279 Y58.20344 E17.68863,'
                'G1 X86.15074 Y58.65075 E17.72352,'
                'G1 X85.70344 Y59.03279 E17.75841,'
                'G1 X85.20188 Y59.34014 E17.7933,'
                'G1 X84.65842 Y59.56525 E17.82819,'
                'G1 X84.08642 Y59.70257 E17.86308,'
                'G1 X-84.08642 Y59.70257 E27.83783,'
                'G1 X-84.65842 Y59.56525 E27.87272,'
                'G1 X-85.20188 Y59.34014 E27.90761,'
                'G1 X-85.70344 Y59.03279 E27.9425,'
                'G1 X-86.15074 Y58.65075 E27.97739,'
                'G1 X-86.53279 Y58.20344 E28.01228,'
                'G1 X-86.84014 Y57.70188 E28.04717,'
                'G1 X-87.06525 Y57.15842 E28.08206,'
                'G1 X-87.20257 Y56.58643 E28.11695,'
                'G1 X-87.20257 Y-56.58643 E34.82952,'
                'G1 X-87.06525 Y-57.15842 E34.86441,'
                'G1 X-86.84014 Y-57.70188 E34.8993,'
                'G1 X-86.53279 Y-58.20344 E34.93419,'
                'G1 X-86.23597 Y-58.55096 E34.9613,'
                'G1 F6000.0,'
                'G1 E34.4613,'
                'G1 F648.0,'
                'M103,'
                'G1 X-86.67555 Y-58.65422 Z0.15 F6000.0,'
                'G1 F648.0,'
                'M103,'
                'M104 S0,'
                'M113 S0.0,'
                'M107,'
                'G1 F6000,'
                'G28'
    }

    def __init__(self):
        pass

    @staticmethod
    def get_calibration_gcode(printer_name):
        if printer_name in CalibrationGCoder._calibration_gcode:
            return CalibrationGCoder._calibration_gcode[printer_name]

        return None
