# coding=utf-8
import logging
import threading
from time import sleep


class StatusDetectionMonitorThread(threading.Thread):

	def __init__(self, bee_comm):
		super(StatusDetectionMonitorThread, self).__init__()
		self.USB_POLL_INTERVAL = 3  # seconds
		self._logger = logging.getLogger()
		self._controlFlag = True
		self.bee_comm=bee_comm

	def run(self):
		"""
		Thread  to check the current status of a connected BVC printer
	
		:param bee_comm: BVC printer connection object
		:return:
		"""

		self._logger.info("Starting BVC Printer status monitor...")
		while  self._controlFlag:
			sleep(self.USB_POLL_INTERVAL)

			if self.bee_comm is None:
				return

			if self.bee_comm.getCommandsInterface() is None:
				continue

			if self.bee_comm.isShutdown():
				continue

			# At the moment we only want to detect possible abrupt changes to shutdown
			# We must also verify if the print is not resuming, because during the resume from shutdown
			# the state is still in Shutdown (in the printer)
			if self.bee_comm.getCommandsInterface().isShutdown() and not self.bee_comm.getCommandsInterface().isResuming():
				self._logger.info("BVC Printer Shutdown detected.")
				self.bee_comm.setShutdownState()

	def stop_status_monitor(self):
		self._controlFlag = False
		self._logger.info("BVC Printer status monitor stopped.")
