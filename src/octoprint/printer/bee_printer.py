# coding=utf-8

from __future__ import absolute_import
from octoprint.util.bee_comm import BeeCom
import os
from octoprint.printer.standard import Printer
from octoprint.printer import PrinterInterface
from octoprint.settings import settings

__author__ = "BEEVC - Electronic Systems "
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"


class BeePrinter(Printer):
    """
    BVC implementation of the :class:`PrinterInterface`. Manages the communication layer object and registers
    itself with it as a callback to react to changes on the communication layer.
    """

    def __init__(self, fileManager, analysisQueue, printerProfileManager):
        super(BeePrinter, self).__init__(fileManager, analysisQueue, printerProfileManager)
        self._estimatedTime = None
        self._elapsedTime = None
        self._numberLines = None
        self._executedLines = None
        self._currentFeedRate = None
        self._runningCalibrationTest = False

    def connect(self, port=None, baudrate=None, profile=None):
        """
         Connects to the printer. If port and/or baudrate is provided, uses these settings, otherwise autodetection
         will be attempted.
        """

        if self._comm is not None:
            self._comm.close()
        #self._printerProfileManager.select(profile)

        self._comm = BeeCom(callbackObject=self, printerProfileManager=self._printerProfileManager)
        self._comm.confirmConnection()

        bee_commands = self._comm.getCommandsInterface()

        # homes all axis
        if bee_commands is not None and bee_commands.isPrinting() is False:
            bee_commands.home()

        # selects the printer profile based on the connected printer name
        printer_name = self.get_printer_name()
        self._printerProfileManager.select(printer_name)

    def updateProgress(self, progressData):
        """
        Receives a progress data object from the BVC communication layer
        and updates the progress attributes

        :param progressData:
        :return:
        """
        if progressData is not None and self._selectedFile is not None:
            self._elapsedTime = progressData['Elapsed Time'] if 'Elapsed Time' in progressData else None
            self._estimatedTime = progressData['Estimated Time'] if 'Estimated Time' in progressData else None
            self._executedLines = progressData['Executed Lines'] if 'Executed Lines' in progressData else None
            self._numberLines = progressData['Lines'] if 'Lines' in progressData else None

    def refresh_sd_files(self, blocking=False):
        """
        Refreshes the list of file stored on the SD card attached to printer (if available and printer communication
        available).
        """
        if not self._comm or not self._comm.isSdReady():
            return

        self._comm.refreshSdFiles()

    def on_comm_progress(self):
        """
         Callback method for the comm object, called upon any change in progress of the print job.
         Triggers storage of new values for printTime, printTimeLeft and the current progress.
        """

        self._setProgressData(self.getPrintProgress(), self.getPrintFilepos(),
                              self._comm.getPrintTime(), self._comm.getCleanedPrintTime())

        # If the status from the printer is no longer printing runs the post-print trigger
        if self.getPrintProgress() >= 1 \
                and self._comm.getCommandsInterface().isPreparingOrPrinting() is False:

            self._comm.triggerPrintFinished()

            self._comm.getCommandsInterface().stopStatusMonitor()
            self._runningCalibrationTest = False

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

    def getPrinterName(self):
        """
        Returns the name of the connected printer
        :return:
        """
        if self._comm is not None:
            return self._comm.getConnectedPrinterName()
        else:
            return None

    def jog(self, axis, amount):
        """
        Jogs the tool a selected amount in the axis chosen

        :param axis:
        :param amount:
        :return:
        """
        if not isinstance(axis, (str, unicode)):
            raise ValueError("axis must be a string: {axis}".format(axis=axis))

        axis = axis.lower()
        if not axis in PrinterInterface.valid_axes:
            raise ValueError("axis must be any of {axes}: {axis}".format(axes=", ".join(PrinterInterface.valid_axes), axis=axis))
        if not isinstance(amount, (int, long, float)):
            raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

        printer_profile = self._printerProfileManager.get_current_or_default()

        # if the feed rate was manually set uses it
        if self._currentFeedRate is not None:
            movement_speed = self._currentFeedRate * 60
        else:
            movement_speed = printer_profile["axes"][axis]["speed"]

        bee_commands = self._comm.getCommandsInterface()

        if axis == 'x':
            bee_commands.move(amount, 0, 0, None, movement_speed)
        elif axis == 'y':
            bee_commands.move(0, amount, 0, None, movement_speed)
        elif axis == 'z':
            bee_commands.move(0, 0, amount, None, movement_speed)

    def feed_rate(self, factor):
        """
        Updates the feed rate factor
        :param factor:
        :return:
        """
        factor = self._convert_rate_value(factor, min=50, max=200)
        self._currentFeedRate = factor

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

        if 'z' in axes:
            bee_commands.homeZ()
        elif 'x' in axes and 'y' in axes:
            bee_commands.homeXY()

    def extrude(self, amount):
        """
        Extrudes the defined amount
        :param amount:
        :return:
        """
        if not isinstance(amount, (int, long, float)):
            raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

        printer_profile = self._printerProfileManager.get_current_or_default()
        extrusion_speed = printer_profile["axes"]["e"]["speed"]

        bee_commands = self._comm.getCommandsInterface()
        bee_commands.move(0, 0, 0, amount, extrusion_speed)

    def get_current_temperature(self):
        """
        Returns the current extruder temperature
        :return:
        """
        return self._comm.getCommandsInterface().getNozzleTemperature()


    def startHeating(self, targetTemperature=200):
        """
        Starts the heating procedure
        :param targetTemperature:
        :return:
        """
        return self._comm.getCommandsInterface().startHeating(targetTemperature)

    def cancelHeating(self):
        """
        Cancels the heating procedure
        :return:
        """
        return self._comm.getCommandsInterface().cancelHeating()

    def heatingDone(self):
        """
        Runs the necessary commands after the heating operation is finished
        :return:
        """
        return self._comm.getCommandsInterface().goToLoadUnloadPos()

    def unload(self):
        """
        Unloads the filament from the printer
        :return:
        """
        return self._comm.getCommandsInterface().unload()

    def load(self):
        """
        Loads the filament to the printer
        :return:
        """
        return self._comm.getCommandsInterface().load()

    def setFilamentString(self, filamentStr):
        """
        Saves the filament reference string in the printer memory
        :return:
        """
        return self._comm.getCommandsInterface().setFilamentString(filamentStr)

    def startCalibration(self, repeat=False):
        """
        Starts the calibration procedure
        :param repeat:
        :return:
        """
        return self._comm.getCommandsInterface().startCalibration(repeat=repeat)

    def nextCalibrationStep(self):
        """
        Goes to the next calibration step
        :return:
        """
        return self._comm.getCommandsInterface().goToNextCalibrationPoint()

    def startCalibrationTest(self):
        """
        Starts the printer calibration test
        :return:
        """
        test_gcode = CalibrationGCoder.get_calibration_gcode(self._printerProfileManager.get_current_or_default()['name'])
        lines = test_gcode.split(',')

        file_path = os.path.join(settings().getBaseFolder("uploads"), 'BEETHEFIRST_calib_test.gcode')
        calibtest_file = open(file_path, 'w')

        for line in lines:
            calibtest_file.write(line + '\n')

        calibtest_file.close()

        self.select_file(file_path, False)
        self.start_print()

        self._runningCalibrationTest = True

        return None

    def cancelCalibrationTest(self):
        """
        Cancels the running calibration test
        :return:
        """
        self.cancel_print()

        return None

    def isRunningCalibrationTest(self):
        """
        Updates the running calibration test flag
        :return:
        """
        return self._runningCalibrationTest

    def _setProgressData(self, progress, filepos, printTime, cleanedPrintTime):
        """
        Auxiliar method to control the print progress status data
        :param progress:
        :param filepos:
        :param printTime:
        :param cleanedPrintTime:
        :return:
        """
        estimatedTotalPrintTime = self._estimateTotalPrintTime(progress, cleanedPrintTime)
        totalPrintTime = estimatedTotalPrintTime

        if self._selectedFile and "estimatedPrintTime" in self._selectedFile \
                and self._selectedFile["estimatedPrintTime"]:

            statisticalTotalPrintTime = self._selectedFile["estimatedPrintTime"]
            if progress and cleanedPrintTime:
                if estimatedTotalPrintTime is None:
                    totalPrintTime = statisticalTotalPrintTime
                else:
                    if progress < 0.5:
                        sub_progress = progress * 2
                    else:
                        sub_progress = 1.0
                    totalPrintTime = (1 - sub_progress) * statisticalTotalPrintTime + sub_progress * estimatedTotalPrintTime

        self._progress = progress
        self._printTime = printTime
        self._printTimeLeft = totalPrintTime - cleanedPrintTime if (totalPrintTime is not None and cleanedPrintTime is not None) else None

        self._stateMonitor.set_progress({
            "completion": self._progress * 100 if self._progress is not None else None,
            "filepos": filepos,
            "printTime": int(self._elapsedTime * 60) if self._elapsedTime is not None else None,
            "printTimeLeft": int(self._printTimeLeft) if self._printTimeLeft is not None else None
        })

        if progress:
            progress_int = int(progress * 100)
            if self._lastProgressReport != progress_int:
                self._lastProgressReport = progress_int
                self._reportPrintProgressToPlugins(progress_int)


class CalibrationGCoder:

    _calibration_gcode = { 'BEETHEFIRST' :'M29,'
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