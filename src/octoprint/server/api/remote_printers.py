# coding=utf-8
from __future__ import absolute_import, division, print_function

__author__ = "Marcos Gomes <mgomes@beeverycreative.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from flask import request, jsonify, make_response, url_for
from werkzeug.exceptions import BadRequest

from octoprint.server import slicingManager, printer
from octoprint.server.util.flask import restricted_access, with_revalidation_checking
from octoprint.server.api import api, NO_CONTENT

from octoprint.settings import settings as s, valid_boolean_trues

from octoprint.slicing import UnknownSlicer, SlicerNotConfigured, ProfileAlreadyExists, UnknownProfile, CouldNotDeleteProfile

@api.route("/remote/getRemotePrinters", methods=["POST"])
@restricted_access
def getRemotePrinters():

	remotePrinters = {}

	remotePrinter = {}
	remotePrinter['id'] = 1
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Printing'
	remotePrinter['Progress'] = '60%'
	remotePrinter['Material'] = 'PLA'
	remotePrinter['Color'] = 'Black'
	remotePrinter['rgb'] = '#000000'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 2
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'READY'
	remotePrinter['Progress'] = '100%'
	remotePrinter['Material'] = 'PETG'
	remotePrinter['Color'] = 'Transparent'
	remotePrinter['rgb'] = 'snow'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 3
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Heating'
	remotePrinter['Progress'] = '80%'
	remotePrinter['Material'] = 'Nylon'
	remotePrinter['Color'] = 'Red'
	remotePrinter['rgb'] = 'red'
	remotePrinters[remotePrinter['id']] = remotePrinter

	remotePrinter = {}
	remotePrinter['id'] = 4
	remotePrinter['model'] = 'BEETHEFIRST+'
	remotePrinter['imgPath'] = url_for('static', filename='img/logo_beethefirstplus.png')
	remotePrinter['state'] = 'Heating'
	remotePrinter['Progress'] = '80%'
	remotePrinter['Material'] = 'Nylon'
	remotePrinter['Color'] = 'Red'
	remotePrinter['rgb'] = 'red'
	remotePrinters[remotePrinter['id']] = remotePrinter

	return jsonify({
		"response": remotePrinters
	})
