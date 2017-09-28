$(function() {
    function PrinterStateViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.printerProfiles = parameters[1];
        self.slicing = parameters[2];
        self.connection = parameters[3];
        self.settings = parameters[4];

        self.stateString = ko.observable(undefined);
        self.isErrorOrClosed = ko.observable(undefined);
        self.isOperational = ko.observable(undefined);
        self.isPrinting = ko.observable(undefined);
        self.isTransferring = ko.observable(undefined);
        self.isHeating = ko.observable(undefined);
        self.isPaused = ko.observable(undefined);
        self.isError = ko.observable(undefined);
        self.isReady = ko.observable(undefined);
        self.isLoading = ko.observable(undefined);
        self.isSdReady = ko.observable(undefined);

        self.stateClass = ko.observable(undefined);
        self.isShutdown = ko.observable(undefined);
        self.isResuming = ko.observable(undefined);
        self.isConnecting = ko.observable(undefined);

        self.insufficientFilament = ko.observable(false);
        self.ignoredInsufficientFilament = ko.observable(false);

        self.filamentChangedByUser = ko.observable(false); // Flag to detect if the user called the change filament operation,
                                                          // so we can show the print control buttons after enough filament is available
        // Auxiliary variables to control state changes
        var prevPaused = self.isPaused();
        var prevPrinting = self.isPrinting();
        var prevClosed = self.isErrorOrClosed();

        self.enablePrint = ko.pureComputed(function() {
            return self.insufficientFilament() && self.loginState.isUser() && self.filename() != undefined;
        });
        self.enablePause = ko.pureComputed(function() {
            return self.isOperational() && (self.isPrinting() || self.isPaused() || self.isShutdown())
            && self.loginState.isUser() && !self.isHeating();
        });
        self.enableCancel = ko.pureComputed(function() {
            return ((self.isPrinting() || self.isPaused() || self.isHeating() || self.isShutdown() || self.isResuming()))
            && self.loginState.isUser();
        });
        self.enablePreparePrint = ko.pureComputed(function() {
            return self.loginState.isUser() && !self.connection.isConnecting()
                && !self.connection.isErrorOrClosed() && !self.filename()
                && !self.isPrinting() && !self.isPaused() && !self.isShutdown() && !self.isHeating()
                && !self.isResuming() && !self.slicing.slicingInProgress();
        });
        self.enableEstimatePrint = ko.pureComputed(function() {
            return self.loginState.isUser() && !self.connection.isConnecting()
                && self.connection.isErrorOrClosed() && !self.filename()
                && !self.isPrinting() && !self.isPaused() && !self.isShutdown() && !self.isHeating()
                && !self.isResuming() && !self.slicing.slicingInProgress();
        });
        self.showInsufficientFilament = ko.pureComputed(function() {
            return self.loginState.isUser && self.insufficientFilament()
            && self.isReady() && !(self.isHeating() || self.isPrinting() || self.isPaused() || self.isShutdown())
            && !self.ignoredInsufficientFilament() && self.filename() !== undefined;
        });
        self.showPrintControlAfterFilamentChange = ko.pureComputed(function() {
            return self.loginState.isUser && !self.insufficientFilament()
            && self.isReady() && !(self.isHeating() || self.isPrinting() || self.isPaused() || self.isShutdown())
            && self.filamentChangedByUser() && self.filename() != undefined;
        });
        self.showPrintControlButtons = ko.pureComputed(function() {
            return self.isOperational() && (self.isPrinting() || self.isPaused() || self.isShutdown() || self.isHeating() || self.isResuming())
            && self.loginState.isUser();
        });
        self.enablePrintFromMemory = ko.pureComputed(function() {
            return self.loginState.isUser() && self.filename() == undefined && (self.isReady && !self.isPrinting()
            && !self.isPaused() && !self.isHeating() && !self.isShutdown());
        });
        self.noPrinterDetected = ko.pureComputed(function() {
            return self.connection.isErrorOrClosed() && !self.isConnecting()
        });
        self.isSelectedFile = ko.pureComputed(function() {
             return self.loginState.isUser() && self.filename() != undefined;
        });
        self.showShutdownAndChangeFilament = ko.pureComputed(function() {
            return !self.isShutdown() && self.loginState.isUser() && self.isPaused();
        });
        self.showFilename = ko.pureComputed(function() {
            return self.isSelectedFile() && !self.connection.isErrorOrClosed();
        });
        self.isBusy = ko.pureComputed(function() {
            return self.isOperational() && (self.isPrinting() || self.isShutdown() || self.isHeating()
             || self.isTransferring() || self.isPaused() || self.isResuming());
        });

        /**
         * Expands the status/print buttons panel to a larger size
         */
        self.expandStatusPanel = function() {
            if (!$('#state').hasClass('expanded')) {
                $('#state').addClass('expanded');
                $('#state_wrapper').addClass('expanded');

                var h = $('#files').height() -  ($('#state_wrapper').height() - 10);
                $(".gcode_files").height(h);
                $('.slimScrollDiv').height(h);
            }
        };

       /**
        * Retracts the status/print buttons panel to the default size
        */
        self.retractStatusPanel = function() {
            if ($('#state').hasClass('expanded')) {
                $('#state').removeClass('expanded');
                $('#state_wrapper').removeClass('expanded');

                var h = $('#files').height() - ($('#state_wrapper').height() - 10);
                $(".gcode_files").height(h);
                $('.slimScrollDiv').height(h);
            }
        };

        self._showPrintFromMemory = function () {
            $('#printFromMemoryDiv').removeClass('hidden');
            $('#preparePrint').addClass('hidden');
            $('#state_wrapper .accordion-heading').addClass('selected');

            self.expandStatusPanel();
        };

        self._hidePrintFromMemory = function () {
            $('#printFromMemoryDiv').addClass('hidden');
            $('#preparePrint').removeClass('hidden');
            $('#state_wrapper .accordion-heading').removeClass('selected');

            self.retractStatusPanel();
        };

        self.togglePrintFromMemory = function() {
            if (self.enablePrintFromMemory()) {
                if ($('#printFromMemoryDiv').hasClass('hidden')) {
                    self._showPrintFromMemory();
                } else {
                    self._hidePrintFromMemory();
                }
            }
        };

        self.printFromMemory = function() {
            $('#printFromMemoryDiv').addClass('hidden');
            $.ajax({
                url: BEE_API_BASEURL + "print_from_memory",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function(response) {
                    $('#printFromMemoryDiv').addClass('hidden');
                    $('#preparePrint').removeClass('hidden');
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    $('#printFromMemoryDiv').removeClass('hidden');
                }
            });
        };

        self.filename = ko.observable(undefined);
        self.filepath = ko.observable(undefined);
        self.progress = ko.observable(undefined);
        self.filesize = ko.observable(undefined);
        self.filepos = ko.observable(undefined);
        self.printTime = ko.observable(undefined);
        self.printTimeLeft = ko.observable(undefined);
        self.fileSizeBytes = ko.observable(undefined);
        self.temperatureTarget = ko.observable(undefined);
        self.printTimeLeftOrigin = ko.observable(undefined);
        self.sd = ko.observable(undefined);
        self.timelapse = ko.observable(undefined);

        self.busyFiles = ko.observableArray([]);

        self.filament = ko.observableArray([]);
        self.estimatedPrintTime = ko.observable(undefined);
        self.lastPrintTime = ko.observable(undefined);

        self.currentHeight = ko.observable(undefined);

        self.TITLE_PRINT_BUTTON_PAUSED = gettext("Restarts the print job from the beginning");
        self.TITLE_PRINT_BUTTON_UNPAUSED = gettext("Starts the print job");
        self.TITLE_PAUSE_BUTTON_PAUSED = gettext("Resumes the print job");
        self.TITLE_PAUSE_BUTTON_UNPAUSED = gettext("Pauses the print job");

        self.titlePrintButton = ko.observable(self.TITLE_PRINT_BUTTON_UNPAUSED);
        self.titlePauseButton = ko.observable(self.TITLE_PAUSE_BUTTON_UNPAUSED);

        self.printerName = ko.computed(function() {
            var name = "";
            if (self.isErrorOrClosed() !== undefined && !self.isErrorOrClosed() && !self.isError()) {
                name = self.printerProfiles.currentProfileData().name();
            }
            return name;
        });

        self.estimatedPrintTimeString = ko.pureComputed(function() {
            if (self.lastPrintTime())
                return formatFuzzyPrintTime(self.lastPrintTime());
            if (self.estimatedPrintTime())
                return formatFuzzyPrintTime(self.estimatedPrintTime());
            return "-";
        });
        self.byteString = ko.pureComputed(function() {
            if (!self.filesize())
                return "-";
            var filepos = self.filepos() ? formatSize(self.filepos()) : "-";
            return filepos + " / " + formatSize(self.filesize());
        });
        self.heightString = ko.pureComputed(function() {
            if (!self.currentHeight())
                return "-";
            return _.sprintf("%.02fmm", self.currentHeight());
        });
        self.printTimeString = ko.pureComputed(function() {
            if (!self.printTime())
                return "00:00";
            return formatDurationHoursMinutes(self.printTime());
        });
        self.printTimeLeftString = ko.pureComputed(function() {
            if (self.printTimeLeft() == undefined) {
                if ( self.isPaused()) {
                    return "-";
                }else if (!self.printTime() || !(self.isPrinting() )){
                    if (self.lastPrintTime()){
                        return formatFuzzyPrintTime(self.lastPrintTime() * ( 100 - self.progressString()) / 100);
                    }
                    if (self.estimatedPrintTime()){
                        return formatFuzzyPrintTime(self.estimatedPrintTime() * ( 100 - self.progressString()) / 100);
                    }
                    return "-";
                } else {
                    return gettext("Still stabilizing...");
                }
            } else {
                return formatFuzzyPrintTime(self.printTimeLeft());
            }
        });
        self.printTimeLeftOriginString = ko.pureComputed(function() {
            var value = self.printTimeLeftOrigin();
            switch (value) {
                case "linear": {
                    return gettext("Based on a linear approximation (very low accuracy, especially at the beginning of the print)");
                }
                case "analysis": {
                    return gettext("Based on the estimate from analysis of file (medium accuracy)");
                }
                case "mixed-analysis": {
                    return gettext("Based on a mix of estimate from analysis and calculation (medium accuracy)");
                }
                case "average": {
                    return gettext("Based on the average total of past prints of this model with the same printer profile (usually good accuracy)");
                }
                case "mixed-average": {
                    return gettext("Based on a mix of average total from past prints and calculation (usually good accuracy)");
                }
                case "estimate": {
                    return gettext("Based on the calculated estimate (best accuracy)");
                }
                default: {
                    return "";
                }
            }
        });
        self.printTimeLeftOriginClass = ko.pureComputed(function() {
            var value = self.printTimeLeftOrigin();
            switch (value) {
                default:
                case "linear": {
                    return "text-error";
                }
                case "analysis":
                case "mixed-analysis": {
                    return "text-warning";
                }
                case "average":
                case "mixed-average":
                case "estimate": {
                    return "text-success";
                }
            }
        });
        self.progressString = ko.pureComputed(function() {
            if (!self.progress() || self.progress() < 0)
                return 0;
            return self.progress();
        });
        self.progressPercentageString = ko.pureComputed(function() {
            if (!self.progress() || self.progress() < 0)
                return "-";
            return _.sprintf("%d%%", self.progressString());
        });
        self.progressBarString = ko.pureComputed(function() {
            if (!self.progress()) {
                return "";
            }
            if (self.isPrinting()){
                var printTimeLeftString = "";
                if(self.printTimeLeftString() != "-")
                    printTimeLeftString= _.sprintf("( %s remaining)", self.printTimeLeftString());
                return _.sprintf("%d%% %s", self.progressString(), printTimeLeftString);
            }
            if (self.isTransferring()){
                //is transferring file
                var transferTime = 5 + self.fileSizeBytes() / 85000;
                var transferTimeLeft = transferTime - self.progressString() * transferTime / 100;
                if(transferTimeLeft < 1)
                    return _.sprintf("Just a few seconds  ( %d%% )", self.progressString());
                if(transferTimeLeft<60)
                    return _.sprintf("%d seconds  ( %d%% )", transferTimeLeft, self.progressString());
                return _.sprintf("%d minutes %d seconds  ( %d%% )", transferTimeLeft / 60, (transferTimeLeft % 60), self.progressString());
            }
            if (self.isHeating()) {
                return _.sprintf("%dº / %dº  ", self.progressString() * self.temperatureTarget() / 100, self.temperatureTarget());
            }
            //Paused or Shutdown
            return _.sprintf("%d%%", self.progressString());
        });
        self.pauseString = ko.pureComputed(function() {
            if (self.isPaused())
                return gettext("Continue");
            else
                return gettext("Pause");
        });

        self.timelapseString = ko.pureComputed(function() {
            var timelapse = self.timelapse();

            if (!timelapse || !timelapse.hasOwnProperty("type"))
                return "-";

            var type = timelapse["type"];
            if (type == "zchange") {
                return gettext("On Z Change");
            } else if (type == "timed") {
                return gettext("Timed") + " (" + timelapse["options"]["interval"] + " " + gettext("sec") + ")";
            } else {
                return "-";
            }
        });

        self.fromCurrentData = function(data) {
            self._fromData(data);
        };

        self.fromHistoryData = function(data) {
            self._fromData(data);
        };

        self.fromTimelapseData = function(data) {
            self.timelapse(data);
        };

        self._processStateClass = function() {
            self.stateClass("text-black");

            if (self.isOperational()) {
                self.stateClass("ready");
            }
            if (self.isPaused()) {
                self.stateClass("paused");
            }
            if (self.isHeating()) {
                self.stateClass("heating");
            }
            if (self.isResuming()) {
                self.stateClass("heating");
            }
            if (self.isPrinting()) {
                self.stateClass("printing");
            }
            if (self.isShutdown()) {
                self.stateClass("shutdown");
            }
            if (self.isErrorOrClosed()) {
                self.stateClass("error");
            }
        };

        self._fromData = function(data) {
            prevPaused = self.isPaused();
            prevPrinting = self.isPrinting();
            prevClosed = self.isErrorOrClosed();

            self._processStateData(data.state);
            self._processJobData(data.job);
            self._processProgressData(data.progress);
            self._processZData(data.currentZ);
            self._processBusyFiles(data.busyFiles);

            self._processStateClass();
        };

        self._processStateData = function(data) {

            self.stateString(gettext(data.text));
            self.isErrorOrClosed(data.flags.closedOrError);
            self.isOperational(data.flags.operational);
            self.isPaused(data.flags.paused);
            self.isPrinting(data.flags.printing);
            self.isError(data.flags.error);
            self.isReady(data.flags.ready);
            self.isTransferring(data.flags.transfering);
            self.isSdReady(data.flags.sdReady);
            self.isHeating(data.flags.heating);
            self.isShutdown(data.flags.shutdown);
            self.isResuming(data.flags.resuming);

            // Workaround to detect the Connecting printer state, because it is signaled from the backend as being
            // in closedOrError state
            if (data.text.toLowerCase().indexOf('connecting') !== -1) {
                self.isConnecting(true);
            } else {
                self.isConnecting(false);
            }

            if (self.isPaused() !== prevPaused) {
                if (self.isPaused()) {
                    self.titlePrintButton(self.TITLE_PRINT_BUTTON_PAUSED);
                    self.titlePauseButton(self.TITLE_PAUSE_BUTTON_PAUSED);
                } else {
                    self.titlePrintButton(self.TITLE_PRINT_BUTTON_UNPAUSED);
                    self.titlePauseButton(self.TITLE_PAUSE_BUTTON_UNPAUSED);
                }
            }

            // detects if a print has finished to change the ignoredInsufficientFilament flag
            if (prevPrinting === true && self.isPrinting() !== prevPrinting && !self.isPaused() && !self.isShutdown()) {
                self.ignoredInsufficientFilament(false);

                // Shows user feedback dialog
                $("#user_feedback_dialog").modal({
                    backdrop: 'static',
                    keyboard: false
                });
                $("#user_feedback_dialog").modal('show');
            }

            // detects if a print job as started to re-enable the main Print button through the slicing progress flag
            if (prevPrinting === false && (self.isHeating() || self.isTransferring() || self.isPrinting())) {
                self.slicing.slicingInProgress(false);
            }

            // if the printer is shutdown or paused state, expands the status panel
            if (self.isShutdown() || self.isPaused()) {
                self.expandStatusPanel();
            }

            // detects if the state changed from closed to ready (upon printer connection) in order to update
            // the currently selected printer profile, instead of calling the API when the application is loaded
            // in the PrinterProfilesViewModel which would cause the printer label to always show the default printer
            if (prevClosed === true && self.isErrorOrClosed() === false && self.isReady() === true) {
                self.printerProfiles.requestData();
            }

            // detects if the state changed from ready to closed
            if (prevClosed === false && self.isErrorOrClosed() === true && self.isOperational() === false) {
                self._hidePrintFromMemory();
            }

        };

        self._processJobData = function(data) {
            var prevInsufficientFilamentFlag = self.insufficientFilament();
            if (data.file) {
                self.filename(data.file.name);
                self.filepath(data.file.path);
                self.filesize(data.file.size);
                self.sd(data.file.origin == "sdcard");
            } else {
                self.filename(undefined);
                self.filepath(undefined);
                self.filesize(undefined);
                self.sd(undefined);
            }

            self.estimatedPrintTime(data.estimatedPrintTime);
            self.lastPrintTime(data.lastPrintTime);

            var result = [];
            if (data.filament && typeof(data.filament) == "object" && _.keys(data.filament).length > 0) {
                for (var key in data.filament) {
                    if (!_.startsWith(key, "tool") || !data.filament[key] || !data.filament[key].hasOwnProperty("length") || data.filament[key].length <= 0) continue;

                    result.push({
                        name: ko.observable(gettext("Tool") + " " + key.substr("tool".length)),
                        data: ko.observable(data.filament[key])
                    });
                }
            }
            self.filament(result);

            // Signals that there is no filament available in the spool
            if (!self.isErrorOrClosed() && data.filament && data.filament['tool0']) {

                self.insufficientFilament(false);

                // detects if a print has finished to retract the panel in case it was expanded
                if (prevPrinting === true && self.isPrinting() !== prevPrinting && !self.isPaused() && !self.isShutdown()) {
                    self.retractStatusPanel();
                } else if (data.filament['tool0']['insufficient'] == true && !self.isPrinting() && !self.isHeating()) {
                    // Signals for insufficient filament only if a print operation is not ongoing
                    self.insufficientFilament(true);
                    // Expands the panel
                    self.expandStatusPanel();
                }

                // This means that the user changed the filament so we can change the flag to true (only if a print operation is not ongoing)
                if (prevInsufficientFilamentFlag === true && self.insufficientFilament() === false && !self.isPrinting() && !self.isHeating()) {
                    self.filamentChangedByUser(true);
                    self.retractStatusPanel();
                }
            }
        };

        self._processProgressData = function(data) {
            if (data.completion) {
                self.progress(data.completion);

                if (data.completion == 100) {
                    // If print finishes empties the progress bar
                    self.progress(0);
                }
            } else {
                self.progress(undefined);
            }
            self.filepos(data.filepos);
            self.printTime(data.printTime);
            self.printTimeLeft(data.printTimeLeft);
            self.fileSizeBytes(data.fileSizeBytes);
            self.temperatureTarget(data.temperatureTarget);
            self.printTimeLeftOrigin(data.printTimeLeftOrigin);
        };

        self._processZData = function(data) {
            self.currentHeight(data);
        };

        self._processBusyFiles = function(data) {
            var busyFiles = [];
            _.each(data, function(entry) {
                if (entry.hasOwnProperty("path") && entry.hasOwnProperty("origin")) {
                    busyFiles.push(entry.origin + ":" + entry.path);
                }
            });
            self.busyFiles(busyFiles);
        };

        self.print = function() {
            if (self.isPaused()) {
                showConfirmationDialog({
                    message: gettext("This will restart the print job from the beginning."),
                    onproceed: function() {
                        OctoPrint.job.restart();
                    }
                });
            } else {
                OctoPrint.job.start();
            }

            // Forces the insufficient filament message to hide
            if (self.insufficientFilament() && self.ignoredInsufficientFilament() == false) {
                self.ignoredInsufficientFilament(true);
                // forces the print to start, so it can retract the status panel
                self.retractStatusPanel();
            }

        };

        self.onlyPause = function() {
            self.expandStatusPanel();
            OctoPrint.job.pause();
        };

        self.onlyResume = function() {
            self.retractStatusPanel();
            OctoPrint.job.resume();
        };

        self.pause = function(action) {
            $('#job_pause').prop('disabled', true);
            $('#job_cancel').prop('disabled', true);
            OctoPrint.job.togglePause(function () {
                $('#job_pause').prop('disabled', false);
                $('#job_cancel').prop('disabled', false);
            });

            self._restoreShutdown();
        };

        self.shutdown = function() {
            $('#job_shutdown').prop('disabled', true);

            self._jobCommand("shutdown", function () {
                $('#shutdown_confirmation').removeClass('hidden');
                $('#shutdown_panel').addClass('hidden');
            });
        };

        self._restoreShutdown = function() {
            $('#job_shutdown').prop('disabled', false);
            $('#shutdown_confirmation').addClass('hidden');
            $('#shutdown_panel').removeClass('hidden');
        };

        self.cancel = function() {

            self._restoreShutdown();
            self.insufficientFilament(false);
            self.ignoredInsufficientFilament(false);
            self.slicing.slicingInProgress(false);

            if (!self.settings.feature_printCancelConfirmation()) {

                $('#job_cancel').prop('disabled', true);
                $('#job_pause').prop('disabled', true);

                OctoPrint.job.cancel(function() {
                    $('#job_cancel').prop('disabled', false);
                    $('#job_pause').prop('disabled', false);
                    self.retractStatusPanel();
                });
            } else {
                showConfirmationDialog({
                    message: gettext("This will cancel your print."),
                    cancel: gettext("No"),
                    proceed: gettext("Yes"),
                    onproceed: function() {
                        $('#job_cancel').prop('disabled', true);
                        $('#job_pause').prop('disabled', true);

                        OctoPrint.job.cancel(function() {
                            $('#job_cancel').prop('disabled', false);
                            $('#job_pause').prop('disabled', false);
                            self.retractStatusPanel();
                        });
                    }

                });
            }
        };

        self._jobCommand = function(command, payload, callback) {
            if (arguments.length == 1) {
                payload = {};
                callback = undefined;
            } else if (arguments.length == 2 && typeof payload === "function") {
                callback = payload;
                payload = {};
            }

            var data = _.extend(payload, {});
            data.command = command;

            $.ajax({
                url: API_BASEURL + "job",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(response) {
                    if (callback != undefined) {
                        callback();
                    }
                }
            });
        };

        /**
         * Returns true if a the Cancel button should be enabled
         *
         * @returns {boolean}
         */
        self.isCancelEnabled = function() {
            if (!self.loginState.isUser()) {
                return false;
            }

            if (self.filename() == undefined) {
                return false;
            }

            if (!self.isOperational()) {
                return false;
            }

            return true;
        };

        /**
         * This function shows the maintenance panel and
         * automatically displays the change filament dialog
         */
        self.showMaintenanceFilamentChange = function() {
            $('#navbar_show_maintenance').click();
        };

        /**
         * Shows the slicing dialog window for the workbench
         */
        self.preparePrint = function () {
            self.slicing.show('local', BEEwb.helpers.generateSceneName(), false, true);
		};

        /**
         * Shows the slicing/estimation dialog window for the workbench
         */
        self.estimatePrint = function () {
            self.slicing.show('local', BEEwb.helpers.generateSceneName(), true, true);
		};

		self.resizeSidebar = function () {
		    var h = $('#files').height() - $('#state').height() - 55; // 55px for the accordion heading
            $(".gcode_files").height(h);
            $('.slimScrollDiv').height(h);
        };

        /**
         * Callback that is called after model startup
         */
		self.onStartupComplete = function () {

            // Workaround to prevent showing the clutter of information in the status panel during startup
            $('#pause_panel').removeClass('hidden');
            $('#insufficientFilamentMessage').removeClass('hidden');
            $('#printRunningButtons').removeClass('hidden');
            $('#noFilamentAvailableButtons').removeClass('hidden');
            $('#preparePrint').removeClass('hidden');
            $('#noPrinterConnected').removeClass('hidden');
            $('#selecteFileInfo').removeClass('hidden');

            window.addEventListener('resize', self.resizeSidebar, false );
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        PrinterStateViewModel,
        ["loginStateViewModel", "printerProfilesViewModel", "slicingViewModel", "connectionViewModel", "settingsViewModel"],
        ["#state_wrapper", "#drop_overlay"]
    ]);
});
