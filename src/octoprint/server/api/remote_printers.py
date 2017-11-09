# coding=utf-8
from __future__ import absolute_import, division, print_function

__author__ = "Marcos Gomes <mgomes@beeverycreative.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from flask import request, jsonify, make_response, url_for
from werkzeug.exceptions import BadRequest

from octoprint.server import slicingManager, printer
from octoprint.server.util.flask import restricted_access, with_revalidation_checking, get_json_command_from_request

from octoprint.server.api import api, NO_CONTENT

from octoprint.settings import settings as s, valid_boolean_trues

from octoprint.slicing import UnknownSlicer, SlicerNotConfigured, ProfileAlreadyExists, UnknownProfile, CouldNotDeleteProfile

import requests
import json
import base64
import datetime
import datetime, dateutil.parser


class ProdsmartAPIMethods(object):
    colors = {'A101 - Transparent': {'material': 'PLA', 'color': '#ECECE7'},
              'A102 - Blanc Gris': {'material': 'PLA', 'color': '#ECECE7'},
              'A103 - Zinc Yellow': {'material': 'PLA', 'color': '#FBCA44'},
              'A104 - Signal Yellow': {'material': 'PLA', 'color': '#FBCA44'},
              'A105 - Bright Red Orange': {'material': 'PLA', 'color': '#EE6B2A'},
              'A106 - Traffic Red': {'material': 'PLA', 'color': '#BC1B13'},
              'A107 - Tomato Red': {'material': 'PLA', 'color': '#BC1B13'},
              'A108 - Light Pink': {'material': 'PLA', 'color': '#BC84BA'},
              'A109 - Traffic Purple': {'material': 'PLA', 'color': '#913071'},
              'A110 - Violet': {'material': 'PLA', 'color': '#8C0091'},
              'A111 - Sky Blue': {'material': 'PLA', 'color': '#007BAE'},
              'A112 - Traffic Blue': {'material': 'PLA', 'color': '#005A8A'},
              'A114 - Yellow Green': {'material': 'PLA', 'color': '#868A00'},
              'A115 - Pure Green': {'material': 'PLA', 'color': '#008C33'},
              'A116 - Chrome Green': {'material': 'PLA', 'color': '#008C33'},
              'A117 - Chocolate Brown': {'material': 'PLA', 'color': '#8C3A09'},
              'A118 - Telegrey': {'material': 'PLA', 'color': '#858583'},
              'A119 - Signal Black': {'material': 'PLA', 'color': '#000000'},
              'A120 - Pearl Gold': {'material': 'PLA', 'color': '#806442'},
              'A121 - Pearl Light Grey': {'material': 'PLA', 'color': '#8D9295'}}

    modelImgs = {'BEETHEFIRST': 'BEETHEFIRST white background.png',
                 'BEETHEFIRST+': 'BEETHEFIRST+ white background.png',
                 'BEETHEFIRST+A': 'BEETHEFIRST+A white background.png',
                 'BEEINSCHOOL': 'BEEINSCHOOL white background.png',
                 'BEEINSCHOOL A': 'BEEINSCHOOL A white background.png'}

    Info = {}

    url = "http://app.prodsmart.com/"
    apiKey = "8fm7ahh0ukrju";
    apiSecret = "confukbj95htvkf7m85l8pbper";
    key = apiKey + ":" + apiSecret;
    b = bytearray()
    b.extend(key)
    encoding = base64.b64encode(b)
    token = ""

    """############################################################################
                                autentication
        ############################################################################"""

    def autentication(self):

        headers = {'Authorization': "Basic " + self.encoding, "Content-Type": "application/json"}
        authorizationRequest = "{ \"scopes\": [ \"productions_write\" ] }";

        myResponse = requests.post(self.url + "api/authorization", data=authorizationRequest, headers=headers)

        if (myResponse.ok):

            # Loading the response data into a dict variable
            # json.loads takes in only binary or string variables so using content to fetch binary content
            # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
            if (myResponse.content != ""):
                jData = json.loads(myResponse.content)
                for key in jData:
                    if (key == "token"):
                        self.token = str(jData[key])
        else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason
            return True

        print
        "Token: " + self.token

        return False

    """############################################################################
                                autentication
    ############################################################################"""

    def getJobs(self, urlToCall="api/production-orders/?", all=False, notstarted=False):
        headers = {"Content-Type": "application/json"}
        if all:
            link = self.url + urlToCall + "access_token=" + self.token
        else:
            if notstarted:
                link = self.url + urlToCall + "access_token=" + self.token + "&running-status=notstarted"
            else:
                link = self.url + urlToCall + "access_token=" + self.token + "&running-status=started"
        myResponse = requests.get(link, headers=headers)
        if not (myResponse.ok):
            if myResponse.status_code == 401:
                self.autentication()
                myResponse = self.getJobs()
            else:
                # If response code is not ok (200), print the resulting http error code with description
                # myResponse.raise_for_status()
                print
                myResponse.reason

        return myResponse

    """############################################################################
                                updateOrder
    ############################################################################"""

    def updateOrder(self, machine, id, status=0):
        headers = {"Content-Type": "application/json"}
        # api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
        link = self.url + "api/machines/" + machine + "/production-orders/" + id + "?" + "access_token=" + self.token
        data = {"status": status}

        myResponse = requests.post(link, data=json.dumps(data), headers=headers)
        # print myResponse.request.url
        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """############################################################################
                                getProductionOrder
    ############################################################################"""

    def getProductionOrder(self, id, urlToCall="api/production-orders/"):

        headers = {"Content-Type": "application/json"}

        link = self.url + urlToCall + id + "?access_token=" + self.token
        myResponse = requests.get(link, headers=headers)

        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return json.loads(myResponse.content)

    """############################################################################
                                createProductionOrder
    ############################################################################"""

    def createProductionOrder(self, machines, products, start_time, end_time, workers, code, status=0):
        headers = {"Content-Type": "application/json"}
        # api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
        link = self.url + "api/production-orders/?access_token=" + self.token
        data = {"status": status,
                "products": products,
                "code": code,
                "start-date": start_time,
                "due-date": end_time,
                "workers-assigned": workers,
                "machines": machines}

        myResponse = requests.post(link, data=json.dumps(data), headers=headers)
        # print myResponse.request.url
        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return json.loads(myResponse.content)

    """############################################################################
                                    getPrinters
    ############################################################################"""

    def getPrinters(self, urlToCall="api/machines?", all=False, notstarted=False):
        headers = {"Content-Type": "application/json"}
        if all:
            link = self.url + urlToCall + "access_token=" + self.token
        else:
            if notstarted:
                link = self.url + urlToCall + "access_token=" + self.token + "&running-status=notstarted"
            else:
                link = self.url + urlToCall + "access_token=" + self.token + "&running-status=started"
        myResponse = requests.get(link, headers=headers)
        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """############################################################################
                                updatePrinterNotes
    ############################################################################"""

    def updatePrinterNotes(self, machine, notes):

        headers = {"Content-Type": "application/json"}
        # api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
        link = self.url + "api/machines/" + machine + "/notes?access_token=" + self.token

        notes_str = json.dumps(notes, separators=(',', ':'))

        data = {"notes": notes_str}

        myResponse = requests.post(link, data=json.dumps(data), headers=headers)
        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """############################################################################
                                activateProductionOrder
    ############################################################################"""

    def activateProductionOrder(self, id):

        headers = {"Content-Type": "application/json"}
        link = self.url + "api/production-orders/" + str(id) + "/activate?access_token=" + self.token

        myResponse = requests.post(link, headers=headers)

        if (myResponse.ok):
            if (myResponse.content != ""):
                return json.loads(myResponse.content)

        else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

            return None

    """############################################################################
                                updateProductionOrder
    ############################################################################"""

    def updateProductionOrder(self, id, status=0):
        headers = {"Content-Type": "application/json"}
        # api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
        link = self.url + "api/production-orders/" + id + "?" + "access_token=" + self.token
        data = {"status": status}

        myResponse = requests.post(link, data=json.dumps(data), headers=headers)

        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """"############################################################################
                                    deleteProductionOrder
    ############################################################################"""

    def deleteProductionOrder(self, id, urlToCall="api/production-orders/"):

        headers = {"Content-Type": "application/json"}

        link = self.url + urlToCall + id + "?access_token=" + self.token
        myResponse = requests.delete(link, headers=headers)

        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """"############################################################################
                                        notifyOrderProblem
    ############################################################################"""

    def notifyOrderProblem(self, id, shortMsg, Msg, urlToCall="api/production-orders/"):

        headers = {"Content-Type": "application/json"}

        link = self.url + urlToCall + id + "/notify?access_token=" + self.token
        data = {"short-message": shortMsg,
                "message": Msg}

        myResponse = requests.post(link, data=json.dumps(data), headers=headers)

        if not (myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print
            myResponse.reason

        return myResponse

    """"############################################################################
                                            getSystemInfo
    ############################################################################"""


    def getSystemInfo(self):

        """
                GET PRINTER LIST
        """

        printerList = json.loads(self.getPrinters().content)

        self.Info = {}
        self.Info['Printers'] = {}
        self.Info['PrintersList'] = printerList

        for printer in printerList:
            # prod_api.updatePrinterNotes(printer['code'],notes)

            self.Info['Printers'][printer['code']] = {}
            self.Info['Printers'][printer['code']]['on_hold'] = 0

            notes = json.loads(printer['notes'])
            for note in notes:
                printer[note] = notes[note]

        """
                        READ AND LIST PRODUCTION ORDERS
        """
        jobsNotStarted = json.loads(self.getJobs(notstarted=True).content)
        jobsStarted = json.loads(self.getJobs(notstarted=False).content)

        runningJobs = []

        for j in jobsStarted:
            if j['status'] != 'completed':
                runningJobs.append(j)

        """
                        CREATE DICT WITH PRINTER AND JOBS
        """

        self.Info['pendent_jobs'] = jobsNotStarted
        self.Info['running_jobs'] = runningJobs

        for job in jobsNotStarted:
            due_date = dateutil.parser.parse(job['due-date'])
            for machine in job['machines']:
                self.Info['Printers'][machine['code']]['on_hold'] += 1

                if 'queue' not in self.Info['Printers'][machine['code']].keys():
                    self.Info['Printers'][machine['code']]['queue'] = []

                order = {}
                order['name'] = job['products'][0]['product']
                order['start'] = dateutil.parser.parse(job['start-date']).strftime("%Y-%m-%d %H:%M:%S")
                order['end'] = dateutil.parser.parse(job['due-date']).strftime("%Y-%m-%d %H:%M:%S")
                order['id'] = job['id']

                self.Info['Printers'][machine['code']]['queue'].append(order)

                if not 'available_at' in self.Info['Printers'][machine['code']].keys():
                    self.Info['Printers'][machine['code']]['available_at'] = due_date
                else:
                    if due_date > self.Info['Printers'][machine['code']]['available_at']:
                        self.Info['Printers'][machine['code']]['available_at'] = due_date

        for job in runningJobs:
            due_date = dateutil.parser.parse(job['due-date'])
            for machine in job['machines']:
                self.Info['Printers'][machine['code']]['on_hold'] += 1

                if 'queue' not in self.Info['Printers'][machine['code']].keys():
                    self.Info['Printers'][machine['code']]['queue'] = []

                order = {}
                order['name'] = job['products'][0]['product']
                order['start'] = dateutil.parser.parse(job['start-date']).strftime("%Y-%m-%d %H:%M:%S")
                order['end'] = dateutil.parser.parse(job['due-date']).strftime("%Y-%m-%d %H:%M:%S")
                order['id'] = job['id']

                self.Info['Printers'][machine['code']]['queue'].append(order)

                if not 'available_at' in self.Info['Printers'][machine['code']].keys():
                    self.Info['Printers'][machine['code']]['available_at'] = due_date
                else:
                    if due_date > self.Info['Printers'][machine['code']]['available_at']:
                        self.Info['Printers'][machine['code']]['available_at'] = due_date

        for printer in self.Info['PrintersList']:
            self.Info['Printers'][printer['code']]['Ready'] = self.Info['Printers'][printer['code']]['on_hold'] == 0

        return self.Info


Info = {}

@api.route("/remote/getRemotePrinters", methods=["POST"])
@restricted_access
def getRemotePrinters():

    prod_api = ProdsmartAPIMethods()

    try:
        while prod_api.autentication():
            pass
    except Exception:
        return True

    remotePrinters = {}
    Info = prod_api.getSystemInfo()

    for printer in Info['PrintersList']:
        Info['Printers'][printer['code']]['Ready'] = Info['Printers'][printer['code']]['on_hold'] == 0

        remotePrinter = {}
        remotePrinter['id'] = printer['code']
        remotePrinter['Filament'] = printer['material_code']
        remotePrinter['Material'] = prod_api.colors[printer['material_code']]['material']
        remotePrinter['rgb'] = prod_api.colors[printer['material_code']]['color']
        remotePrinter['model'] = printer['model']
        remotePrinter['serial'] = printer['serial']

        remotePrinter['imgPath'] = url_for('static', filename='img/' + prod_api.modelImgs[remotePrinter['model']])

        if Info['Printers'][printer['code']]['Ready']:
            remotePrinter['state'] = 'READY'
            remotePrinter['Progress'] = '100%'
        else:
            remotePrinter['state'] = 'Printing'
            for j in Info['running_jobs']:
                if j['machines'][0]['code'] == printer['code']:
                    remotePrinter['Progress'] = str(j['products'][0]['quantity-produced']*100) + '%'
            remotePrinter['orders'] = Info['Printers'][printer['code']]['queue']
            if 'Progress' not in remotePrinter.keys():
                remotePrinter['Progress'] = '0%'

        remotePrinters[remotePrinter['id']] = remotePrinter

    return jsonify({
        "response": remotePrinters
    })

@api.route("/remote/createPrintingOrders", methods=["POST"])
@restricted_access
def createPrintingOrders():

    prod_api = ProdsmartAPIMethods()

    try:
        while prod_api.autentication():
            pass
    except Exception:
        return True

    Info = prod_api.getSystemInfo()

    valid_commands = {
        "createOrders": []
    }

    command, data, response = get_json_command_from_request(request, valid_commands)
    if response is not None:
        return response

    printers = data['Info'][0]
    file = data['Info'][1]

    new_orders = []


    for printer in printers:

        machines = []
        machines.append({'code':printer})
        products = [{'product': file, 'quantity-ordered': 1}]
        workers = [{'number': 1}, {'number': 2}, {'number': 3}, {'number': 18}]

        start = datetime.datetime.now()

        if Info['Printers'][printer]['on_hold'] > 0:
            start = Info['Printers'][printer]['available_at']
            if start.replace(tzinfo=None) < datetime.datetime.now().replace(tzinfo=None):
                start = datetime.datetime.now()

        end = start + datetime.timedelta(minutes=10)

        new_order = prod_api.createProductionOrder(machines=machines,
                                                   products=products,
                                                   workers=workers,
                                                   start_time=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                   end_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                   code="{} - BEESOFT".format(file))
        new_orders.append(new_order)

    return jsonify({
        "response": new_orders
    })




    return

@api.route("/remote/cancelPrintingOrders", methods=["POST"])
@restricted_access
def cancelPrintingOrders():
    prod_api = ProdsmartAPIMethods()

    try:
        while prod_api.autentication():
            pass
    except Exception:
        return True

    Info = prod_api.getSystemInfo()

    valid_commands = {
        "cancelOrders": []
    }

    command, data, response = get_json_command_from_request(request, valid_commands)
    if response is not None:
        return response

    orderIDs = data['Info'][0]

    for id in orderIDs:
        #Get order
        order = prod_api.getProductionOrder(id)
        if order['running-status'] == 'notstarted':
            prod_api.notifyOrderProblem(id,"Cancel","Cancel")
            prod_api.deleteProductionOrder(id)
        else:
            prod_api.notifyOrderProblem(id, "Cancel", "Cancel")
            #prod_api.updateOrder(order['machines'][0]['code'],id,100)



    return jsonify({
            "response": ''
        })
