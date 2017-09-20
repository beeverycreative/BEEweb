# coding=utf-8
import logging
import threading
from time import sleep
from beedriver.connection import Conn as BeePrinterConn
from octoprint.settings import settings

class ConnectionMonitorThread(threading.Thread):

	def __init__(self, connection_callback):
		"""
		Thread class to check if a BVC printer was connected to a USB port

		:param connection_callback: Callback function to call when a printer is detected
		:return:
		"""
		super(ConnectionMonitorThread, self).__init__()
		self.USB_POLL_INTERVAL = 1  # seconds
		self._printerConnIntf = BeePrinterConn(dummyPlug=settings().getBoolean(["usb", "dummyPrinter"]))

		self._logger = logging.getLogger()
		self._printer_detected_msg_logged = False
		self._controlFlag = True
		self._connection_callback = connection_callback

	def stop_connection_monitor(self):
		self._controlFlag = False
		self._logger.info("BVC Printer connection monitor stopped.")

	def run(self):

		self._logger.info("Starting BVC Printer connection monitor...")

		while self._controlFlag:
			printers = self._printerConnIntf.getPrinterList()

			if len(printers) > 0: # printer found
				if not self._printer_detected_msg_logged:
					self._logger.info("BVC Printer detected. Waiting for client connection...")
					self._printer_detected_msg_logged = True

				if self._connection_callback():
					return

			sleep (self.USB_POLL_INTERVAL)
