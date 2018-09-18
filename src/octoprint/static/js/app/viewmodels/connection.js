$(function() {
    function ConnectionViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settings = parameters[1];
        self.printerProfiles = parameters[2];

        self.printerProfiles.profiles.items.subscribe(function() {
            var allProfiles = self.printerProfiles.profiles.items();

            var printerOptions = [];
            _.each(allProfiles, function(profile) {
                printerOptions.push({id: profile.id, name: profile.name});
            });
            self.printerOptions(printerOptions);
        });

        self.printerProfiles.currentProfile.subscribe(function() {
            self.selectedPrinter(self.printerProfiles.currentProfile());
        });

        self.portOptions = ko.observableArray(undefined);
        self.baudrateOptions = ko.observableArray(undefined);
        self.printerOptions = ko.observableArray(undefined);
        self.selectedPort = ko.observable(undefined);
        self.selectedBaudrate = ko.observable(undefined);
        self.selectedPrinter = ko.observable(undefined);
        self.saveSettings = ko.observable(undefined);
        self.autoconnect = ko.observable(undefined);

        self.isErrorOrClosed = ko.observable(undefined);
        self.isOperational = ko.observable(undefined);
        self.isPrinting = ko.observable(undefined);
        self.isPaused = ko.observable(undefined);
        self.isError = ko.observable(undefined);
        self.isReady = ko.observable(undefined);
        self.isLoading = ko.observable(undefined);

        self.isConnecting = ko.observable(undefined);

        self.serialNumber = ko.observable(undefined);
        self.savingSerialNumber = ko.observable(false);
        self.serialError = ko.observable(undefined);

        self.buttonText = ko.pureComputed(function() {
            if (self.isConnecting())
                return gettext("Connecting...");

            if (self.isErrorOrClosed())
                return gettext("Connect");
            else
                return gettext("Disconnect");
        });

        self.previousIsOperational = undefined;

        self.requestData = function() {
            OctoPrint.connection.getSettings()
                .done(self.fromResponse);
        };

        self.fromResponse = function(response) {
            var ports = response.options.ports;
            var baudrates = response.options.baudrates;
            var portPreference = response.options.portPreference;
            var baudratePreference = response.options.baudratePreference;
            var printerPreference = response.options.printerProfilePreference;
            var printerProfiles = response.options.printerProfiles;

            self.portOptions(ports);
            self.baudrateOptions(baudrates);

            if (!self.selectedPort() && ports && ports.indexOf(portPreference) >= 0)
                self.selectedPort(portPreference);
            if (!self.selectedBaudrate() && baudrates && baudrates.indexOf(baudratePreference) >= 0)
                self.selectedBaudrate(baudratePreference);
            if (!self.selectedPrinter() && printerProfiles && printerProfiles.indexOf(printerPreference) >= 0)
                self.selectedPrinter(printerPreference);

            self.saveSettings(false);
        };

        self.fromHistoryData = function(data) {
            self._processStateData(data.state);
        };

        self.fromCurrentData = function(data) {
            self._processStateData(data.state);
        };

        self.openOrCloseOnStateChange = function() {
            var connectionTab = $("#connection");
            if (self.isOperational() && connectionTab.hasClass("in")) {
                connectionTab.collapse("hide");
            } else if (!self.isOperational() && !connectionTab.hasClass("in")) {
                connectionTab.collapse("show");
            }
        };

        self._processStateData = function(data) {
            self.previousIsOperational = self.isOperational();

            self.isErrorOrClosed(data.flags.closedOrError);
            self.isOperational(data.flags.operational);
            self.isPaused(data.flags.paused);
            self.isPrinting(data.flags.printing);
            self.isError(data.flags.error);
            self.isReady(data.flags.ready);
            self.isLoading(data.flags.loading);

            if (self.loginState.isUser() && self.previousIsOperational != self.isOperational()) {
                // only open or close if the panel is visible (for admins) and
                // the state just changed to avoid thwarting manual open/close
                self.openOrCloseOnStateChange();
            }
        };

        self.connect = function() {
            if (self.isErrorOrClosed()) {
                self.isConnecting(true);

                var data = {
                    "port": self.selectedPort() || "AUTO",
                    "baudrate": self.selectedBaudrate() || 0,
                    "printerProfile": self.selectedPrinter(),
                    "autoconnect": self.settings.serial_autoconnect()
                };

                if (self.saveSettings())
                    data["save"] = true;

                OctoPrint.connection.connect(data)
                    .done(function() {
                        self.settings.requestData();
                        self.settings.printerProfiles.requestData();

                        self.isConnecting(false);
                    });
            } else {
                self.requestData();
                OctoPrint.connection.disconnect();
            }
        };

		/** Printer Serial Number methods **/
		self.showSerialNumberDialog = function() {
			self.snDialog = $("#serial_number_dialog");
			self.snDialog.on("shown", function() {
				$("input", self.snDialog).focus();
			});

			self.snDialog.modal("show");
		};

		self.validSerialNumber = ko.computed(function () {
			if (self.serialNumber() && self.serialNumber().length === 10) {
				return true;
			}
			return false;
    	}, this);

        self.saveSerialNumber = function() {
        	self.savingSerialNumber(true);
        	self.serialError(undefined);

        	if (!self.validSerialNumber()) {
        		self.savingSerialNumber(false);
        		self.serialError(gettext('Please insert a valid 10 digit serial number.'));
        		return;
        	}

            var data = {
                serial_number: self.serialNumber()
            };

            $.ajax({
                url: BEE_API_BASEURL + "save_printer_serial_number",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(response) {
                	self.savingSerialNumber(false);
                	self.snDialog.modal("hide");
                }
            });
        };

        self.cancelSerialNumberInput = function() {
        	self.serialError(undefined);
            var data = {
                serial_number: '000'
            };

			// Sends an invalid serial number just to unlock the connection thread
            $.ajax({
                url: BEE_API_BASEURL + "save_printer_serial_number",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(response) {
                }
            });

            self.snDialog.modal("hide");
        };

        self.onStartup = function() {
            self.requestData();

            // when isAdmin becomes true the first time, set the panel open or
            // closed based on the connection state
            var subscription = self.loginState.isAdmin.subscribe(function(newValue) {
                if (newValue) {
                    // wait until after the isAdmin state has run through all subscriptions
                    setTimeout(self.openOrCloseOnStateChange, 0);
                    subscription.dispose();
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        ConnectionViewModel,
        ["loginStateViewModel", "settingsViewModel", "printerProfilesViewModel"],
        ["#connection_wrapper", "#serial_number_dialog"]
    ]);
});
