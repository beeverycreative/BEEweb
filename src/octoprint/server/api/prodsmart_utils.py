import requests
import json
import base64


class ProdsmartAPIMethods(object):

    url = "http://app.prodsmart.com/"
    apiKey = "8fm7ahh0ukrju";
    apiSecret = "confukbj95htvkf7m85l8pbper";
    key = apiKey + ":" + apiSecret;
    b = bytearray()
    b.extend(key)
    encoding=base64.b64encode(b)
    token = ""

    def autentication(self):

        headers = {'Authorization':  "Basic " + self.encoding, "Content-Type": "application/json"}
        authorizationRequest = "{ \"scopes\": [ \"productions_write\" ] }";

        myResponse = requests.post(self.url + "api/authorization", data=authorizationRequest, headers=headers)

        if (myResponse.ok):

            # Loading the response data into a dict variable
            # json.loads takes in only binary or string variables so using content to fetch binary content
            # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
            if (myResponse.content != ""):
                jData = json.loads(myResponse.content)
                for key in jData:
                    if(key =="token"):
                        self.token=str(jData[key])
        else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print myResponse.reason
            return True
        print "Token: "+self.token
        return False

    def getJobs(self, urlToCall="api/production-orders/?",all=False,notstarted=False):
        headers = {"Content-Type": "application/json"}
        if all:
            link = self.url + urlToCall + "access_token=" + self.token
        else:
            if notstarted:
                link = self.url + urlToCall + "access_token=" + self.token+"&running-status=notstarted"
            else:
                link = self.url + urlToCall + "access_token=" + self.token+"&running-status=started"
        myResponse = requests.get(link, headers=headers)
        if (myResponse.ok):

            # Loading the response data into a dict variable
            # json.loads takes in only binary or string variables so using content to fetch binary content
            # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
            if (myResponse.content != ""):
                jData = json.loads(myResponse.content)
                for key in jData:
                    x = json.dumps(key)

        else:
            if myResponse.status_code==401:
                self.autentication()
                myResponse=self.getJobs()
            else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
                print myResponse.reason
        return myResponse

    def updateOrder(self,machine,id,status=0):
        headers = {"Content-Type": "application/json"}
       #api/machine/{machine-code}/production-order/{production-order-id}?access_token={access_token}
        link = self.url + "api/machines/"+machine+"/production-orders/"+id+"?" + "access_token=" + self.token
        data={ "status": status }

        myResponse = requests.post(link,data= json.dumps(data) ,headers=headers)
        #print myResponse.request.url
        if (myResponse.ok):

            # Loading the response data into a dict variable
            # json.loads takes in only binary or string variables so using content to fetch binary content
            # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
            if (myResponse.content != ""):
                jData = json.loads(myResponse.content)
                print("The response contains {0} properties".format(len(jData)))
                for key in jData:
                    x = json.dumps(key)
                    print key
                    print key["status"]

        else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print myResponse.reason

    def getProductionOrder(self,id,urlToCall="api/production-orders/"):

        headers = {"Content-Type": "application/json"}

        link=self.url + urlToCall+id+"?access_token="+self.token
        myResponse = requests.get(link, headers=headers)
        print myResponse.status_code
        if (myResponse.ok):

            # Loading the response data into a dict variable
            # json.loads takes in only binary or string variables so using content to fetch binary content
            # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
            if (myResponse.content != ""):
                jData = json.loads(myResponse.content)
                print("The response contains {0} properties".format(len(jData)))
                for key in jData:
                    x= json.dumps(key)
                    print key
                    print key["status"]

        else:
            # If response code is not ok (200), print the resulting http error code with description
            # myResponse.raise_for_status()
            print myResponse.reason

