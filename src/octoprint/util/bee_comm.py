# coding=utf-8
from __future__ import absolute_import
import os
import threading
import time
import Queue as queue
import logging

from octoprint.settings import settings
from octoprint.events import eventManager, Events
from octoprint.util.comm import MachineCom, regex_sdPrintingByte, regex_sdFileOpened, PrintingFileInformation
from beedriver.connection import Conn as BeePrinterConn
from octoprint.util import comm, get_exception_string, sanitize_ascii, RepeatedTimer, parsePropertiesFile

__author__ = "BEEVC - Electronic Systems"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

class BeeCom(MachineCom):
    STATE_PREPARING_PRINT = 22
    STATE_HEATING = 23
    STATE_SHUTDOWN = 24
    STATE_RESUMING = 25

    _beeConn = None
    _beeCommands = None

    _responseQueue = queue.Queue()
    _statusQueue = queue.Queue()

    _monitor_print_progress = True
    _connection_monitor_active = True
    _prepare_print_thread = None
    _preparing_print = False
    _resume_print_thread = None
    _transferProgress = 0
    _heatingProgress = 0

    def __init__(self, callbackObject=None, printerProfileManager=None):
        super(BeeCom, self).__init__(None, None, callbackObject, printerProfileManager)

        self._openConnection()
        self._heating = False

        # monitoring thread
        self._monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor, name="comm._monitor")
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()


    def _openConnection(self):
        """
        Opens a new connection using the BEEcom driver

        :return: True if the connection was successful
        """
        if self._beeConn is None:
            self._beeConn = BeePrinterConn(self._connDisconnectHook, settings().getBoolean(["usb", "dummyPrinter"]))
            self._changeState(self.STATE_CONNECTING)
            if not self._beeConn.connectToFirstPrinter():
                self._errorValue = 'Invalid USB driver'
                self._changeState(self.STATE_ERROR)
                return False

        if self._beeConn.isConnected():
            self._beeCommands = self._beeConn.getCommandIntf()

            # change to firmware
            if self._beeCommands.getPrinterMode() == 'Bootloader':
                # checks for firmware updates
                firmware_available, firmware_version = self.check_firmware_update()
                if firmware_available:
                    self.update_firmware()

                self._beeCommands.goToFirmware()
            else:
                firmware_available, firmware_version = self.check_firmware_update()
                if firmware_available:
                    eventManager().fire(Events.FIRMWARE_UPDATE_AVAILABLE, {"version": firmware_version})

            # restart connection
            self._beeConn.reconnect()

            # post connection callback
            self._onConnected()

            return True
        else:
            self._changeState(self.STATE_CLOSED)
            return False

    def current_firmware(self):
        """
        Gets the current firmware version
        :return:
        """
        firmware_v = self.getCommandsInterface().getFirmwareVersion()

        if firmware_v is not None:
            return firmware_v
        else:
            return 'Not available'

    def check_firmware_update(self):
        """
        Checks for an available firmware update for the printer by verifying if the value in the firmware.properties file is different
        from the current printer firmware
        :return: if a different version is available than the current, returns a tuple with True and the new version. If no
        printer is detected or no update is available returns False
        """
        _logger = logging.getLogger()
        # get the latest firmware file for the connected printer
        conn_printer = self.getConnectedPrinterName()
        if conn_printer is None:
            return False

        printer_id = conn_printer.replace(' ', '').lower()

        _logger.info("Checking for firmware updates...")
        from os.path import isfile, join
        try:
            firmware_path = settings().getBaseFolder('firmware')
            firmware_properties = parsePropertiesFile(join(firmware_path, 'firmware.properties'))
            firmware_file_name = firmware_properties['firmware.' + printer_id]
        except KeyError as e:
            _logger.error(
                "Problem with printer_id %s. Firmware properties not found for this printer model." % printer_id)
            return

        if firmware_file_name is not None and isfile(join(firmware_path, firmware_file_name)):
            fname_parts = firmware_file_name.split('-')

            # gets the current firmware version, ex: BEEVC-BEETHEFIRST-10.5.23.BIN
            curr_firmware = self.current_firmware()
            curr_firmware_parts = curr_firmware.split('-')

            if len(curr_firmware_parts) == 3 and curr_firmware is not "Not available":
                curr_version_parts = curr_firmware_parts[2].split('.')
                file_version_parts = fname_parts[2].split('.')

                if len(curr_version_parts) >= 3 and len(file_version_parts) >= 3:
                    for i in range(3):
                        if int(file_version_parts[i]) != int(curr_version_parts[i]):
                            return True, curr_firmware
            elif curr_firmware == '0.0.0':
                return True, curr_firmware

        _logger.info("No firmware updates found")
        return False, '0.0.0'

    def update_firmware(self):
        """
        Updates the printer firmware if a printer is connected
        :return: if no printer is connected just returns void
        """
        _logger = logging.getLogger()
        # get the latest firmware file for the connected printer
        conn_printer = self.getConnectedPrinterName()
        if conn_printer is None:
            return

        printer_id = conn_printer.replace(' ', '').lower()

        if printer_id:
            from os.path import isfile, join

            _logger.info("Checking for firmware updates...")

            try:
                firmware_path = settings().getBaseFolder('firmware')
                firmware_properties = parsePropertiesFile(join(firmware_path, 'firmware.properties'))
                firmware_file_name = firmware_properties['firmware.' + printer_id]
            except KeyError as e:
                _logger.error("Problem with printer_id %s. Firmware properties not found for this printer model." % printer_id)
                return

            if firmware_file_name is not None and isfile(join(firmware_path, firmware_file_name)):

                fname_parts = firmware_file_name.split('-')
                return self._flashFirmware(firmware_file_name, firmware_path, fname_parts[2])
            else:
                _logger.error("No firmware file matching the configuration for printer %s found" % conn_printer)


    def sendCommand(self, cmd, cmd_type=None, processed=False, force=False, on_sent=None):
        """
        Sends a custom command through the open connection
        :param on_sent:
        :param cmd:
        :param cmd_type:
        :param processed:
        :param force:
        :return:
        """
        cmd = cmd.encode('ascii', 'replace')
        if not processed:
            cmd = comm.process_gcode_line(cmd)
            if not cmd:
                return

        # The following lines would prevent sending custom commands to the printer during a print job
        #if self.isPrinting() and not self.isSdFileSelected():
        #    self._commandQueue.put((cmd, cmd_type))
        try:
            if self.isOperational():

                wait = None
                if "g" in cmd.lower():
                    wait = "3"

                resp = self._beeCommands.sendCmd(cmd, wait)

                if resp:
                    # puts the response in the monitor queue
                    self._responseQueue.put(resp)

                    # logs the command reply with errors
                    splits = resp.rstrip().split("\n")
                    for r in splits:
                        if "Error" in r:
                            self._logger.warning(r)

                    return True
                else:
                    return False
        except Exception as ex:
            self._logger.error("Error sending command to printer in: %s", str(ex))
            return False


    def close(self, is_error=False, wait=True, timeout=10.0, *args, **kwargs):
        """
        Closes the connection to the printer if it's active
        :param is_error:
        :param wait: unused parameter (kept for interface compatibility)
        :param timeout:
        :param args:
        :param kwargs:
        :return:
        """
        if self._beeCommands is not None:
            self._beeCommands.stopPrintStatusMonitor()

        if self._beeConn is not None:
            try:
                self._beeConn.close()
            except Exception as ex:
                self._logger.error(ex)

        self._changeState(self.STATE_CLOSED)

    def _changeState(self, newState):
        if self._state == newState:
            return

        oldState = self.getStateString()
        self._state = newState
        self._log('Changing monitoring state from \'%s\' to \'%s\'' % (oldState, self.getStateString()))
        self._callback.on_comm_state_change(newState)

    def updatePrinterState(self):
        """
        Confirms the connection changing the internal state of the printer
        :return:
        """
        if self._beeConn.isConnected():
            if self._state != self.STATE_OPERATIONAL and self._beeCommands.isReady():
                self._changeState(self.STATE_OPERATIONAL)
                return
            elif self._state != self.STATE_PAUSED and self._beeCommands.isPaused():
                self._changeState(self.STATE_PAUSED)
                return
            elif self._state != self.STATE_PRINTING and self._beeCommands.isPrinting():
                self._changeState(self.STATE_PRINTING)
                return
            elif self._state != self.STATE_SHUTDOWN and self._beeCommands.isShutdown():
                self._changeState(self.STATE_SHUTDOWN)
                return
        else:
            self._changeState(self.STATE_CLOSED)

    def getConnectedPrinterName(self):
        """
        Returns the current connected printer name
        :return:
        """
        if self._beeConn is not None:
            return self._beeConn.getConnectedPrinterName()
        else:
            return ""

    def getConnectedPrinterSN(self):
        """
        Returns the current connected printer serial number
        :return:
        """
        if self._beeConn is not None:
            return self._beeConn.getConnectedPrinterSN()
        else:
            return None

    def isOperational(self):
        return self._state == self.STATE_OPERATIONAL \
               or self._state == self.STATE_PRINTING \
               or self._state == self.STATE_PAUSED \
               or self._state == self.STATE_SHUTDOWN \
               or self._state == self.STATE_TRANSFERING_FILE \
               or self._state == self.STATE_PREPARING_PRINT \
               or self._state == self.STATE_HEATING \
               or self._state == self.STATE_RESUMING

    def isClosedOrError(self):
        return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR \
               or self._state == self.STATE_CLOSED

    def isBusy(self):
        return self.isPrinting() or self.isPaused() or self.isPreparingPrint() or self.isResuming()

    def isPreparingPrint(self):
        return self._state == self.STATE_PREPARING_PRINT or self._state == self.STATE_HEATING

    def isPrinting(self):
        return self._state == self.STATE_PRINTING

    def isHeating(self):
        return self._state == self.STATE_HEATING

    def isShutdown(self):
        return self._state == self.STATE_SHUTDOWN

    def isResuming(self):
        return self._state == self.STATE_RESUMING

    def isTransferring(self):
        return self._state == self.STATE_PREPARING_PRINT

    def getStateString(self):
        """
        Returns the current printer state
        :return:
        """
        if self._state == self.STATE_CLOSED:
            return "Disconnected"
        elif self._state == self.STATE_PREPARING_PRINT:
            return "Transferring"
        elif self._state == self.STATE_HEATING:
            return "Heating"
        elif self._state == self.STATE_SHUTDOWN:
            return "Shutdown"
        elif self._state == self.STATE_OPERATIONAL:
            return "Ready"
        elif self._state == self.STATE_RESUMING:
            return "Resuming"
        else:
            return super(BeeCom, self).getStateString()

    def startPrint(self, pos=None, printTemperature=210):
        """
        Starts the printing operation
        :param pos: if the string 'memory' is passed the printer will print the last file in the printer's memory
        :param printTemperature: The temperature target for the print job
        """
        if not self.isOperational() or self.isPrinting():
            return

        if self._currentFile is None and pos is None:
            raise ValueError("No file selected for printing")

        try:
            self._changeState(self.STATE_PREPARING_PRINT)

            if pos == 'from_memory':
                # special case that signals the print from memory operation
                print_resp = self._beeCommands.repeatLastPrint(printTemperature=printTemperature)
            else:
                # standard case where the analysis object is passed in the pos variable
                estimatedPrintTime = None
                gcodeLines = None
                if pos is not None and "estimatedPrintTime" in pos:
                    estimatedPrintTime = pos['estimatedPrintTime']
                if pos is not None and "gcodeLines" in pos:
                    gcodeLines = pos['gcodeLines']

                print_resp = self._beeCommands.printFile(
                    self._currentFile.getFilename(),
                    printTemperature=printTemperature,
                    estimatedPrintTime=estimatedPrintTime,
                    gcodeLines=gcodeLines
                )

            if print_resp is True:
                self._heatupWaitStartTime = time.time()
                self._heatupWaitTimeLost = 0.0
                self._pauseWaitStartTime = 0
                self._pauseWaitTimeLost = 0.0

                self._heating = True

                self._preparing_print = True
                self._prepare_print_thread = threading.Thread(target=self._preparePrintThread, name="comm._preparePrint")
                self._prepare_print_thread.daemon = True
                self._prepare_print_thread.start()
            else:
                self._errorValue = "Error while preparing the printing operation."
                self._logger.exception(self._errorValue)
                self._changeState(self.STATE_ERROR)
                eventManager().fire(Events.ERROR, {"error": self.getErrorString()})
                return

        except:
            self._errorValue = get_exception_string()
            self._logger.exception("Error while trying to start printing: " + self.getErrorString())
            self._changeState(self.STATE_ERROR)
            eventManager().fire(Events.ERROR, {"error": self.getErrorString()})


    def cancelPrint(self, firmware_error=None):
        """
        Cancels the print operation
        :type firmware_error: unused parameter, just to keep the interface compatible with octoprint
        """
        if not self.isOperational() or self.isStreaming():
            return

        self._preparing_print = False
        if self._beeCommands.cancelPrint():

            self._changeState(self.STATE_OPERATIONAL)

            if self.isSdFileSelected():
                if self._sd_status_timer is not None:
                    try:
                        self._sd_status_timer.cancel()
                    except:
                        pass
        else:
            self._logger.exception("Error while canceling the print operation.")
            eventManager().fire(Events.ERROR, {"error": "Error canceling print"})
            return


    def setPause(self, pause):
        """
        Toggle Pause method
        :param pause: True to pause or False to unpause
        :return:
        """
        if self.isStreaming():
            return

        if not self._currentFile:
            return

        payload = {
            "file": self._currentFile.getFilename(),
            "filename": os.path.basename(self._currentFile.getFilename()),
            "origin": self._currentFile.getFileLocation()
        }

        try:
            if (not pause and self.isPaused()) or (not pause and self.isShutdown()):
                if self._pauseWaitStartTime:
                    self._pauseWaitTimeLost = self._pauseWaitTimeLost + (time.time() - self._pauseWaitStartTime)
                    self._pauseWaitStartTime = None

                # resumes printing
                self._preparing_print = True
                self._beeCommands.resumePrint()

                self._heating = True
                self._resume_print_thread = threading.Thread(target=self._resumePrintThread, name="comm._resumePrint")
                self._resume_print_thread.daemon = True
                self._resume_print_thread.start()

            elif pause and self.isPrinting():
                if not self._pauseWaitStartTime:
                    self._pauseWaitStartTime = time.time()

                # pause print
                self._beeCommands.pausePrint()

                self._changeState(self.STATE_PAUSED)

                eventManager().fire(Events.PRINT_PAUSED, payload)
        except Exception as ex:
            self._logger.error("Error setting printer in pause mode: %s", str(ex))

    def setShutdownState(self):
        """
        Setter method to change the current state to SHUTDOWN
        :return:
        """
        self._changeState(self.STATE_SHUTDOWN)


    def enterShutdownMode(self):
        """
        Enters the printer shutdown mode
        :return:
        """
        if self.isStreaming():
            return

        if not self._currentFile:
            return

        payload = {
            "file": self._currentFile.getFilename(),
            "filename": os.path.basename(self._currentFile.getFilename()),
            "origin": self._currentFile.getFileLocation()
        }

        # enter shutdown mode
        try:
            self._beeCommands.enterShutdown()
            self.setShutdownState()
            eventManager().fire(Events.POWER_OFF, payload)
        except Exception as ex:
            self._logger.error("Error setting printer in shutdown mode: %s", str(ex))


    def startHeating(self, targetTemperature=210):
        """
        Starts the heating procedure
        :param targetTemperature:
        :return:
        """
        try:
            self._changeState(self.STATE_HEATING)
            return self._beeCommands.startHeating(targetTemperature)
        except Exception as ex:
            self._logger.error(ex)


    def cancelHeating(self):
        """
        Cancels the heating procedure
        :return:
        """
        try:
            self._changeState(self.STATE_OPERATIONAL)
            return self._beeCommands.cancelHeating()
        except Exception as ex:
            self._logger.error(ex)


    def heatingDone(self):
        """
        Runs the necessary commands after the heating operation is finished
        :return:
        """
        try:
            res = self._beeCommands.goToLoadUnloadPos()
            self.updatePrinterState()
            return res
        except Exception as ex:
            self._logger.error(ex)


    def unload(self):
        """
        Unloads the filament from the printer
        :return:
        """
        try:
            return self._beeCommands.unload()
        except Exception as ex:
            self._logger.error(ex)


    def load(self):
        """
        Loads the filament to the printer
        :return:
        """
        try:
            return self._beeCommands.load()
        except Exception as ex:
            self._logger.error(ex)

    def initSdCard(self):
        """
        Initializes the SD Card in the printer
        :return:
        """
        if not self.isOperational():
            return

        try:
            self._beeCommands.initSD()

            if settings().getBoolean(["feature", "sdAlwaysAvailable"]):
                self._sdAvailable = True
                self.refreshSdFiles()
                self._callback.on_comm_sd_state_change(self._sdAvailable)
        except Exception as ex:
            self._logger.error("Error initializing printer SD Card: %s", str(ex))

    def refreshSdFiles(self):
        """
        Refreshes the list of available SD card files
        :return:
        """
        if not self.isOperational() or self.isBusy():
            return

        try:
            fList = self._beeCommands.getFileList()

            ##~~ SD file list
            if len(fList) > 0 and 'FileNames' in fList:

                for sdFile in fList['FileNames']:

                    if comm.valid_file_type(sdFile, "machinecode"):
                        if comm.filter_non_ascii(sdFile):
                            self._logger.warn("Got a file from printer's SD that has a non-ascii filename (%s), that shouldn't happen according to the protocol" % filename)
                        else:
                            if not filename.startswith("/"):
                                # file from the root of the sd -- we'll prepend a /
                                filename = "/" + filename
                            self._sdFiles.append((sdFile, 0))
                        continue
        except Exception as ex:
            self._logger.error("Error file list from SD: %s", str(ex))

    def startFileTransfer(self, filename, localFilename, remoteFilename):
        """
        Transfers a file to the printer's SD Card
        """
        if not self.isOperational() or self.isBusy():
            self._log("Printer is not operation or busy")
            return

        try:
            self._currentFile = comm.StreamingGcodeFileInformation(filename, localFilename, remoteFilename)
            self._currentFile.start()

            # starts the transfer
            self._beeCommands.transferSDFile(filename, localFilename)

            eventManager().fire(Events.TRANSFER_STARTED, {"local": localFilename, "remote": remoteFilename})
            self._callback.on_comm_file_transfer_started(remoteFilename, self._currentFile.getFilesize())

            # waits for transfer to end
            while self._beeCommands.getTransferCompletionState() > 0:
                time.sleep(2)

            remote = self._currentFile.getRemoteFilename()
            payload = {
                "local": self._currentFile.getLocalFilename(),
                "remote": remote,
                "time": self.getPrintTime()
            }

            self._currentFile = None
            self._changeState(self.STATE_OPERATIONAL)
            self._callback.on_comm_file_transfer_done(remote)
            eventManager().fire(Events.TRANSFER_DONE, payload)
            self.refreshSdFiles()

        except Exception as ex:
            self._logger.error("Error setting printer in shutdown mode: %s", str(ex))

    def startPrintStatusProgressMonitor(self):
        """
        Starts the monitor thread that keeps track of the print progress
        :return:
        """
        if self._beeCommands is not None:
            # starts the progress status thread
            self._beeCommands.startPrintStatusMonitor(self._statusProgressQueueCallback)

    def selectFile(self, filename, sd):
        """
        Overrides the original selectFile method to allow to select files when printer is busy. For example
        when reconnecting after connection was lost and the printer is still printing
        :param filename:
        :param sd:
        :return:
        """
        if sd:
            if not self.isOperational():
                # printer is not connected, can't use SD
                return
            self._sdFileToSelect = filename
            self.sendCommand("M23 %s" % filename)
        else:
            # special case for non existent file in system after shutdown recovery
            if filename is None:
                filenameInPrinter = self.getCurrentFileNameFromPrinter()
                if filenameInPrinter is not None:
                    self._currentFile = InMemoryFileInformation(filenameInPrinter, offsets_callback=self.getOffsets,
                                                                 current_tool_callback=self.getCurrentTool)
                else:
                    self._currentFile = comm.PrintingFileInformation('shutdown_recover_file')

            # Special case treatment for in memory file printing
            if filename == 'Memory File':
                filenameInPrinter = self.getCurrentFileNameFromPrinter()
                if filenameInPrinter is not None:
                    filename = filenameInPrinter
                    self._currentFile = InMemoryFileInformation(filename, offsets_callback=self.getOffsets,
                                                                current_tool_callback=self.getCurrentTool)
                else:
                    self._currentFile = InMemoryFileInformation(filename, offsets_callback=self.getOffsets,
                                                                 current_tool_callback=self.getCurrentTool)

                self._callback.on_comm_file_selected(filename, 0, False)
            else:
                self._currentFile = comm.PrintingGcodeFileInformation(filename, offsets_callback=self.getOffsets,
                                                                 current_tool_callback=self.getCurrentTool)
                eventManager().fire(Events.FILE_SELECTED, {
                    "file": self._currentFile.getFilename(),
                    "filename": os.path.basename(self._currentFile.getFilename()),
                    "origin": self._currentFile.getFileLocation()
                })
                self._callback.on_comm_file_selected(filename, self._currentFile.getFilesize(), False)

    def getPrintProgress(self):
        """
        Gets the current print progress
        :return:
        """
        if self._currentFile is None:
            return None
        return self._currentFile.getProgress()

    def getCurrentFile(self):
        """
        Gets the current PrintFileInformation object
        :return:
        """
        return self._currentFile

    def getCurrentFileNameFromPrinter(self):
        """
        Gets the filename of the file being currently printed or None if no informations is available
        :return: string with the filename or None
        """
        if not self.isOperational():
            return None
        try:
            if self._beeCommands is not None:
                return self._beeCommands.getCurrentPrintFilename()
        except Exception as ex:
            self._logger.error(ex)

        return None

    def getExtruderStepsMM(self):
        """
        Gets Extruder Steps/mm
        :return: steps/mm
        """
        if not self.isOperational():
            return None
        try:
            if self._beeCommands is not None:
                return self._beeCommands.getExtruderStepsMM()
        except Exception as ex:
            self._logger.error(ex)

        return None

    def setExtruderStepsMM(self,steps):
        """
        Sets Extruder Steps/mm
        :param steps:
        :return:
        """
        if not self.isOperational():
            return None
        try:
            if self._beeCommands is not None:
                return self._beeCommands.setExtruderStepsMM(steps)
        except Exception as ex:
            self._logger.error(ex)
        return None

    def isExtruderCalibrationRequired(self):
        if not self.isOperational():
            return False

        if self._beeCommands.isExtruderCalibrated():
            return False

        return True

    def _getResponse(self):
        """
        Auxiliar method to read the command response queue
        :return:
        """
        self.none = self._beeConn is None
        if self.none:
            return None
        try:
            ret = self._responseQueue.get()
        except:
            self._log("Exception raised while reading from command response queue: %s" % (get_exception_string()))
            self._errorValue = get_exception_string()
            return None

        if ret == '':
            #self._log("Recv: TIMEOUT")
            return ''

        try:
            self._log("Recv: %s" % sanitize_ascii(ret))
        except ValueError as e:
            self._log("WARN: While reading last line: %s" % e)
            self._log("Recv: %r" % ret)

        return ret

    def triggerPrintFinished(self):
        """
        This method runs the post-print job code
        :return:
        """
        # Resets SD printing related variables
        self._sdFilePos = 0
        if self._sd_status_timer is not None:
            try:
                self._sd_status_timer.cancel()
            except:
                pass

        self._changeState(self.STATE_OPERATIONAL)
        self._callback.on_comm_print_job_done()


    def _monitor(self):
        """
        Monitor thread of responses from the commands sent to the printer
        :return:
        """
        feedback_controls, feedback_matcher = comm.convert_feedback_controls(settings().get(["controls"]))
        feedback_errors = []
        pause_triggers = comm.convert_pause_triggers(settings().get(["printerParameters", "pauseTriggers"]))

        #exits if no connection is active
        if not self._beeConn.isConnected():
            return

        startSeen = False
        supportWait = settings().getBoolean(["feature", "supportWait"])

        while self._monitoring_active:
            try:
                line = self._getResponse()
                if line is None:
                    continue

                ##~~ debugging output handling
                if line.startswith("//"):
                    debugging_output = line[2:].strip()
                    if debugging_output.startswith("action:"):
                        action_command = debugging_output[len("action:"):].strip()

                        if action_command == "pause":
                            self._log("Pausing on request of the printer...")
                            self.setPause(True)
                        elif action_command == "resume":
                            self._log("Resuming on request of the printer...")
                            self.setPause(False)
                        elif action_command == "disconnect":
                            self._log("Disconnecting on request of the printer...")
                            self._callback.on_comm_force_disconnect()
                        else:
                            for hook in self._printer_action_hooks:
                                try:
                                    self._printer_action_hooks[hook](self, line, action_command)
                                except:
                                    self._logger.exception("Error while calling hook {} with action command {}".format(self._printer_action_hooks[hook], action_command))
                                    continue
                    else:
                        continue

                ##~~ Error handling
                line = self._handleErrors(line)

                ##~~ process oks
                if line.strip().startswith("ok") or (self.isPrinting() and supportWait and line.strip().startswith("wait")):
                    self._clear_to_send.set()
                    self._long_running_command = False

                ##~~ Temperature processing
                if ' T:' in line or line.startswith('T:') or ' T0:' in line or line.startswith('T0:') \
                        or ' B:' in line or line.startswith('B:'):

                    self._processTemperatures(line)
                    self._callback.on_comm_temperature_update(self._temp, self._bedTemp)

                ##~~ SD Card handling
                elif 'SD init fail' in line or 'volume.init failed' in line or 'openRoot failed' in line:
                    self._sdAvailable = False
                    self._sdFiles = []
                    self._callback.on_comm_sd_state_change(self._sdAvailable)
                elif 'Not SD printing' in line:
                    if self.isSdFileSelected() and self.isPrinting():
                        # something went wrong, printer is reporting that we actually are not printing right now...
                        self._sdFilePos = 0
                        self._changeState(self.STATE_OPERATIONAL)
                elif 'SD card ok' in line and not self._sdAvailable:
                    self._sdAvailable = True
                    self.refreshSdFiles()
                    self._callback.on_comm_sd_state_change(self._sdAvailable)
                elif 'Begin file list' in line:
                    self._sdFiles = []
                    self._sdFileList = True
                elif 'End file list' in line:
                    self._sdFileList = False
                    self._callback.on_comm_sd_files(self._sdFiles)
                elif 'SD printing byte' in line and self.isSdPrinting():
                    # answer to M27, at least on Marlin, Repetier and Sprinter: "SD printing byte %d/%d"
                    match = regex_sdPrintingByte.search(line)
                    self._currentFile.setFilepos(int(match.group(1)))
                    self._callback.on_comm_progress()
                elif 'File opened' in line and not self._ignore_select:
                    # answer to M23, at least on Marlin, Repetier and Sprinter: "File opened:%s Size:%d"
                    match = regex_sdFileOpened.search(line)
                    if self._sdFileToSelect:
                        name = self._sdFileToSelect
                        self._sdFileToSelect = None
                    else:
                        name = match.group(1)
                    self._currentFile = comm.PrintingSdFileInformation(name, int(match.group(2)))
                elif 'File selected' in line:
                    if self._ignore_select:
                        self._ignore_select = False
                    elif self._currentFile is not None:
                        # final answer to M23, at least on Marlin, Repetier and Sprinter: "File selected"
                        self._callback.on_comm_file_selected(self._currentFile.getFilename(), self._currentFile.getFilesize(), True)
                        eventManager().fire(Events.FILE_SELECTED, {
                            "file": self._currentFile.getFilename(),
                            "origin": self._currentFile.getFileLocation()
                        })
                elif 'Writing to file' in line:
                    # answer to M28, at least on Marlin, Repetier and Sprinter: "Writing to file: %s"
                    self._changeState(self.STATE_PRINTING)
                    self._clear_to_send.set()
                    line = "ok"

                elif 'Done saving file' in line:
                    self.refreshSdFiles()
                elif 'File deleted' in line and line.strip().endswith("ok"):
                    # buggy Marlin version that doesn't send a proper \r after the "File deleted" statement, fixed in
                    # current versions
                    self._clear_to_send.set()

                ##~~ Message handling
                elif line.strip() != '' \
                        and line.strip() != 'ok' and not line.startswith("wait") \
                        and not line.startswith('Resend:') \
                        and line != 'echo:Unknown command:""\n' \
                        and self.isOperational():
                    self._callback.on_comm_message(line)

                ##~~ Parsing for feedback commands
                if feedback_controls and feedback_matcher and not "_all" in feedback_errors:
                    try:
                        self._process_registered_message(line, feedback_matcher, feedback_controls, feedback_errors)
                    except:
                        # something went wrong while feedback matching
                        self._logger.exception("Error while trying to apply feedback control matching, disabling it")
                        feedback_errors.append("_all")

                ##~~ Parsing for pause triggers
                if pause_triggers and not self.isStreaming():
                    if "enable" in pause_triggers.keys() and pause_triggers["enable"].search(line) is not None:
                        self.setPause(True)
                    elif "disable" in pause_triggers.keys() and pause_triggers["disable"].search(line) is not None:
                        self.setPause(False)
                    elif "toggle" in pause_triggers.keys() and pause_triggers["toggle"].search(line) is not None:
                        self.setPause(not self.isPaused())
                        self.setPause(not self.isPaused())

                ### Connection attempt
                elif self._state == self.STATE_CONNECTING:
                    if "start" in line and not startSeen:
                        startSeen = True
                        self._sendCommand("M110")
                        self._clear_to_send.set()
                    elif "ok" in line:
                        self._onConnected()
                    elif time.time() > self._timeout:
                        self.close()

                ### Operational
                elif self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PAUSED:
                    if "ok" in line:
                        # if we still have commands to process, process them
                        if self._resendDelta is not None:
                            self._resendNextCommand()
                        elif self._sendFromQueue():
                            pass

                    # resend -> start resend procedure from requested line
                    elif line.lower().startswith("resend") or line.lower().startswith("rs"):
                        self._handleResendRequest(line)

            except Exception as ex:
                self._logger.exception("Something crashed inside the USB connection.")

                errorMsg = "See octoprint.log for details"
                self._log(ex.message)
                self._errorValue = errorMsg
                self._changeState(self.STATE_ERROR)
                eventManager().fire(Events.ERROR, {"error": self.getErrorString()})
        self._log("Connection closed, closing down monitor")


    def _statusProgressQueueCallback(self, status_obj):
        """
        Auxiliar callback method to push the status object that comes from the printer into the queue

        :param status_obj:
        :return:
        """
        # calls the Printer object to update the progress values
        self._callback.updateProgress(status_obj)
        self._callback.on_comm_progress()

    def _onConnected(self):
        """
        Post connection callback
        """

        # starts the connection monitor thread
        self._beeConn.startConnectionMonitor()

        self._temperature_timer = RepeatedTimer(self._timeout_intervals.get("temperature", 4.0), self._poll_temperature, run_first=True)
        self._temperature_timer.start()

        if self._sdAvailable:
            self.refreshSdFiles()
        else:
            self.initSdCard()

        payload = dict(port=self._port, baudrate=self._baudrate)
        eventManager().fire(Events.CONNECTED, payload)

    def _poll_temperature(self):
        """
        Polls the temperature after the temperature timeout, re-enqueues itself.

        If the printer is not operational, not printing from sd, busy with a long running command or heating, no poll
        will be done.
        """
        try:
            if self.isOperational() and not self.isStreaming() and not self._long_running_command and not self._heating:
                self.sendCommand("M105", cmd_type="temperature_poll")
        except Exception as e:
            self._log("Error polling temperature %s" % str(e))


    def getCommandsInterface(self):
        """
        Returns the commands interface for BVC printers
        :return:
        """
        return self._beeCommands


    def _connDisconnectHook(self):
        """
        Function to be called by the BVC driver to shutdown the connection
        :return:
        """
        self._callback.disconnect()


    def _preparePrintThread(self):
        """
        Thread code that runs while the print job is being prepared
        :return:
        """
        try:
            # waits for heating/file transfer
            while self._beeCommands.isTransferring():
                time.sleep(1)
                self._transferProgress = self._beeCommands.getTransferState()
                # makes use of the same method that is used for the print job progress, to update
                # the transfer progress since we are going to use the same progress bar
                self._callback._setProgressData(self._transferProgress, 0, 0, 0)
                if not self._preparing_print:  # the print (transfer) was cancelled
                    return
            self._callback._resetPrintProgress()
            self._changeState(self.STATE_HEATING)
        except Exception as ex:
            self._logger.error("Error while preparing print. Transfer error: %s", str(ex))
            self._changeState(self.STATE_OPERATIONAL)
            return

        try:
            while self._beeCommands.isHeating():
                time.sleep(1)
                currentHeatingProgress = self._beeCommands.getHeatingProgress()
                if currentHeatingProgress is None:
                    self._heatingProgress = 0.0
                elif currentHeatingProgress > self._heatingProgress:
                    # small verification to prevent temperature update errors coming from the printer due to sensor noise
                    # the temperature is only updated to a new value if it's greater than the previous when the printer is
                    # heating
                    self._heatingProgress = round(currentHeatingProgress, 2)

                # makes use of the same method that is used for the print job progress, to update
                # the heating progress since we are going to use the same progress bar
                self._callback._setProgressData(self._heatingProgress, 0, 0, 0)
                if not self._preparing_print:  # the print (heating) was cancelled
                    self._heatingProgress = 0.0
                    return

            # Forces the heating progress to 100% to display the progress bar full, because the actual progress will
            # stop just before 100%, to avoid heat sensor errors near final target temperature
            self._heatingProgress = 1.0
            self._callback._setProgressData(self._heatingProgress, 0, 0, 0)
        except Exception as ex:
            self._logger.error("Error while preparing print. Heating error: %s", str(ex))
            self._changeState(self.STATE_OPERATIONAL)
            self._heatingProgress = 0.0
            return

        try:
            if self._currentFile is not None:
                self._heatingProgress = 0.0
                # Starts the real printing operation
                self._changeState(self.STATE_PRINTING)

                payload = {
                    "file": self._currentFile.getFilename(),
                    "filename": os.path.basename(self._currentFile.getFilename()),
                    "origin": self._currentFile.getFileLocation()
                }
                eventManager().fire(Events.PRINT_STARTED, payload)

                # starts the progress status thread
                self.startPrintStatusProgressMonitor()

                if self._heatupWaitStartTime is not None:
                    self._heatupWaitTimeLost = self._heatupWaitTimeLost + (time.time() - self._heatupWaitStartTime)
                    self._heatupWaitStartTime = None
                    self._heating = False
                self._preparing_print = False

                # leaves the start operation to the last, in case the file was deleted in the meantime and could throw and exception
                self._currentFile.start()
            else:
                self._heatingProgress = 0.0
                self._changeState(self.STATE_OPERATIONAL)
                self._logger.error('Error starting Print operation. No selected file found.')

        except Exception as ex:
            self._logger.error("Error while starting print. %s", str(ex))
            return

    def _resumePrintThread(self):
        """
        Thread code that runs while the print job is being resumed after pause/shutdown
        :return:
        """
        self._changeState(self.STATE_RESUMING)

        while self._beeCommands.isResuming():
            time.sleep(1)
            if not self._preparing_print:  # the print (heating) was cancelled
                return

        if self._currentFile is not None:
            # Starts the real printing operation
            self._changeState(self.STATE_PRINTING)

            payload = {
                "file": self._currentFile.getFilename(),
                "filename": os.path.basename(self._currentFile.getFilename()),
                "origin": self._currentFile.getFileLocation()
            }

            eventManager().fire(Events.PRINT_RESUMED, payload)

            # starts the progress status thread
            self.startPrintStatusProgressMonitor()

            if self._heatupWaitStartTime is not None:
                self._heatupWaitTimeLost = self._heatupWaitTimeLost + (time.time() - self._heatupWaitStartTime)
                self._heatupWaitStartTime = None
                self._heating = False
            self._preparing_print = False
        else:
            self._changeState(self.STATE_READY)
            self._logger.error('Error starting Print operation. No selected file found.')


    def _flashFirmware(self, firmware_file_name, firmware_path, version):
        """
        Auxiliary method that performs that calls the low level driver flash firmware operation
        :param firmware_file_name:
        :param firmware_path:
        :param version:
        :return:
        """
        from os.path import join
        _logger = logging.getLogger()

        try:
            _logger.info("Updating printer firmware...")
            eventManager().fire(Events.FIRMWARE_UPDATE_STARTED, {"version": firmware_file_name})

            if self.getCommandsInterface().flashFirmware(join(firmware_path, firmware_file_name), firmware_file_name):

                _logger.info("Firmware updated to %s" % version)
                eventManager().fire(Events.FIRMWARE_UPDATE_FINISHED, {"result": True})
                return True

        except Exception as ex:
            _logger.exception(ex)

        _logger.info("Error updating firmware to version %s" % version)
        eventManager().fire(Events.FIRMWARE_UPDATE_FINISHED, {"result": False})
        return False



class InMemoryFileInformation(PrintingFileInformation):
    """
    Dummy file information handler for printer in memory files
    Encapsulates information regarding an ongoing direct print. Takes care of the needed file handle and ensures
    that the file is closed in case of an error.
    """

    def __init__(self, filename, offsets_callback=None, current_tool_callback=None):
        PrintingFileInformation.__init__(self, filename)

        self._handle = None

        self._offsets_callback = offsets_callback
        self._current_tool_callback = current_tool_callback

        self._size = 0
        self._pos = 0
        self._read_lines = 0
