$(function() {
    function MaintenanceViewModel(parameters) {
        var self = this;
        var cancelTemperatureUpdate = false;
        var fetchTemperatureRetries = 5;
        var TARGET_TEMPERATURE = 200;

        self.loginState = parameters[0];
        self.users = parameters[1];
        self.printerProfiles = parameters[2];
        self.printerState = parameters[3];

        self.receiving = ko.observable(false);
        self.sending = ko.observable(false);
        self.callbacks = [];

        self.commandLock = ko.observable(false);
        self.operationLock = ko.observable(false);

        self.maintenanceDialog = $('#maintenance_dialog');
        self.filamentProfiles = ko.observableArray();

        self.selectedFilament = ko.observable();
        self.filamentSelected = ko.observable(false);
        self.filamentResponseError = ko.observable(false);
        self.heatingDone = ko.observable(false);

        self.nozzleSizes = ko.observableArray([]);

        self.selectedNozzle = ko.observable();
        self.nozzleSelected = ko.observable(false);
        self.saveNozzleResponseError = ko.observable(false);

        self.onStartup = function() {

            /**
             * Binds the function to automatically show the Change filament dialog to the printer state model
             * for usage in the shutdown panel
             */
            self.printerState.showMaintenanceFilamentChange = function() {
                self.show();

                self.showFilamentChange();
            };
        }

        self.show = function() {
            // show maintenance panel, ensure centered position
            self.maintenanceDialog.modal({
                backdrop: 'static',
                keyboard: false,
                minHeight: function() {
                    return Math.max($.fn.modal.defaults.maxHeight() - 80, 250);
                }
            }).css({
                width: 'auto',
                'margin-left': function() { return -($(this).width() /2); }
            });

            // Gets the available filament list
            self._getFilamentProfiles();

            // Gets the available nozzle size list
            self._getNozzleSizes();

            return false;
        };

        self.hide = function() {
            self.maintenanceDialog.modal("hide");
        };

        self._heatingDone = function() {
            $.ajax({
                url: API_BASEURL + "maintenance/heating_done",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    self.heatingDone(true);
                },
                error: function() {
                    self.heatingDone(false);
                }
            });
        };

        self.cancelOperations = function() {

            $('#maintenanceList').removeClass('hidden');
            $('#cancelMaintenance').addClass('hidden');

            $('#maintenance_changeFilament').addClass('hidden');
            $('#maintenance_calibration').addClass('hidden');
            $('#maintenance_extruderMaintenance').addClass('hidden');
            $('#maintenance_replaceNozzle').addClass('hidden');

            $('#maintenanceOkButton').addClass('hidden');
            $('#maintenanceCloseButton').removeClass('hidden');

            // Cancels any heating process
            self.cancelHeating();

            // Returns the operations to the initial step screens
            self.changeFilamentStep0();
            self.calibrationStep0();
            self.replaceNozzleStep0();
            self.extMaintStep0();

            // Goes to home position
            self._sendCustomCommand('G28');

            self._hideMovingMessage();
        };

        self.finishOperations = function() {
            $('#maintenanceList').removeClass('hidden');
            $('#cancelMaintenance').addClass('hidden');

            $('#maintenance_changeFilament').addClass('hidden');
            $('#maintenance_calibration').addClass('hidden');
            $('#maintenance_extruderMaintenance').addClass('hidden');
            $('#maintenance_replaceNozzle').addClass('hidden');

            // Returns the operations to the initial step screens
            self.changeFilamentStep0();
            self.calibrationStep0();
            self.replaceNozzleStep0();
            self.extMaintStep0();

            // Goes to home position
            self._sendCustomCommand('G28');

            self._hideMovingMessage();
        };

        self._showMovingMessage = function() {
            $('#maintenance_warning_box').removeClass('hidden');
        };

        self._hideMovingMessage = function() {
            $('#maintenance_warning_box').addClass('hidden');
        };

        /***************************************************************************/
        /*******                   Filament Change functions            ************/
        /***************************************************************************/
        self.showFilamentChange = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_changeFilament').removeClass('hidden');

            // Starts heating automatically
            self.startHeating();
        };

        self.changeFilamentStep0 = function() {
            $('#step2').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').removeClass('hidden');

            var tempProgress = $("#temperature_progress");
            var tempProgressBar = $(".bar", tempProgress);

            tempProgressBar.css('width', '0%');
            tempProgressBar.text('0%');

            $('#start-heating-btn').removeClass('hidden');
            $('#progress-bar-div').addClass('hidden');

            self.operationLock(false);

            self.filamentSelected(false);
            self.filamentResponseError(false);

            $('#maintenanceCloseButton').removeClass('hidden');
            $('#maintenanceOkButton').addClass('hidden');
        };

        self.nextStep2 = function() {
            $('#step2').removeClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').addClass('hidden');
        };

        self.nextStep3 = function() {
            $('#step3').removeClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
        };

        self.changeFilamentStepFinalStep = function() {
            $('#maintenanceOkButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
        };

        self.startHeating = function() {
            cancelTemperatureUpdate = false;
            self.heatingDone(false);

            self.commandLock(true);
            self.operationLock(true);

            $.ajax({
                url: API_BASEURL + "maintenance/start_heating",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    $('#start-heating-btn').addClass('hidden');
                    $('#progress-bar-div').removeClass('hidden');

                    self._updateTempProgress();

                    self.commandLock(false);
                },
                error: function() { self.commandLock(false);  }
            });
        };

        self.cancelHeating = function() {

            $.ajax({
                url: API_BASEURL + "maintenance/cancel_heating",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    $('#start-heating-btn').removeClass('hidden');
                    $('#progress-bar-div').addClass('hidden');

                    var tempProgress = $("#temperature_progress");
                    var tempProgressBar = $(".bar", tempProgress);
                    tempProgressBar.css('width', '0%');
                    tempProgressBar.text('0%');

                    self.commandLock(false);
                    self.operationLock(false);

                    self.heatingDone(false);

                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                }
            });

            cancelTemperatureUpdate = true;
        };

        self._updateTempProgress = function() {

            fetchTemperatureRetries = 5;

            $.ajax({
                url: API_BASEURL + "maintenance/temperature",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    if (!cancelTemperatureUpdate) {
                        var current_temp = data['temperature'];
                        var progress = ((current_temp / TARGET_TEMPERATURE) * 100).toFixed(0);

                        var tempProgress = $("#temperature_progress");
                        var tempProgressBar = $(".bar", tempProgress);

                        var progressStr = progress + "%";
                        tempProgressBar.css('width', progressStr);
                        tempProgressBar.text(progressStr);

                        if (progress >= 100) {
                            // Heating is finished, let's move on
                            self._heatingDone();

                            if (self.filamentSelected()) {
                                $('#step3').removeClass('hidden');
                                $('#step2').addClass('hidden');
                                $('#step1').addClass('hidden');
                            }
                        } else {
                            setTimeout(function() { self._updateTempProgress() }, 2000);
                        }
                    }
                },
                error: function() {
                    while (fetchTemperatureRetries > 0)
                        setTimeout(function() { self._updateTempProgress() }, 2000);
                        fetchTemperatureRetries -= 1;
                    }
            });
        };

        self.loadFilament = function() {
            self.commandLock(true);
            self._showMovingMessage();

            $.ajax({
                url: API_BASEURL + "maintenance/load",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.changeFilamentStepFinalStep();
                    self.commandLock(false);
                    self._hideMovingMessage();
                },
                error: function() {
                    self.commandLock(false);
                    self._hideMovingMessage();
                }
            });
        };

        self.unloadFilament = function() {
            self.commandLock(true);
            self._showMovingMessage();

            $.ajax({
                url: API_BASEURL + "maintenance/unload",
                type: "POST",
                dataType: "json",
                success: function() {

                    self.commandLock(false);
                    self._hideMovingMessage();
                },
                error: function() {
                    self.commandLock(false);
                    self._hideMovingMessage();
                }
            });
        };

        self.saveFilament = function() {
            self.commandLock(true);

            self.filamentSelected(false);
            self.filamentResponseError(false);

            var data = {
                command: "filament",
                filamentStr: self.selectedFilament()
            };

            $.ajax({
                url: API_BASEURL + "maintenance/save_filament",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(data) {
                    var response = data['response'];

                    if (response.indexOf('ok') > -1) {
                        self.filamentSelected(true);

                        self.commandLock(false);
                        self.operationLock(false);

                        if (self.heatingDone()) {
                            self.nextStep3();
                        } else {
                            self.nextStep2();
                        }
                    } else {
                        self.filamentResponseError(true);
                        self.commandLock(false);
                    }
                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                    self.filamentResponseError(true);
                }
            });
        };

        self._getFilamentProfiles = function() {

            $.ajax({
                url: API_BASEURL + "maintenance/filament_profiles",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    var profiles = data;
                    self.filamentProfiles.removeAll();

                    _.each(profiles, function(profile) {

                        // Parses the list and filters for BVC colors
                        // Assumes the '_' nomenclature separation for the profile names
                        var profile_parts = profile.displayName.split('_');
                        if (profile_parts[0] != null) {
                            var color = profile_parts[0];
                            if (!_.findWhere(self.filamentProfiles(), color)) {
                                self.filamentProfiles.push(color);
                            }
                        }
                    });
                }
            });
        };

        /***************************************************************************/
        /**********             end Filament Change functions           ************/
        /***************************************************************************/

        /***************************************************************************/
        /**********                 Calibration functions               ************/
        /***************************************************************************/


        self.showCalibration = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_calibration').removeClass('hidden');

            // Starts the calibration operation
            self.startCalibration();
        };

        self.startCalibration = function() {
            self.commandLock(true);
            self.operationLock(true);

            $.ajax({
                url: API_BASEURL + "maintenance/start_calibration",
                type: "POST",
                dataType: "json",
                success: function() {

                    self.commandLock(false);
                },
                error: function() { self.commandLock(false); }
            });
        };

        self.upBigStep = function() {
            self._sendJogCommand('z', -1, 0.5);
        };

        self.upSmallStep = function() {
            self._sendJogCommand('z', -1, 0.05);
        };

        self.downBigStep = function() {
            self._sendJogCommand('z', 1, 0.5);
        };

        self.downSmallStep = function() {
            self._sendJogCommand('z', 1, 0.05);
        };

        self.calibrationStep0 = function() {

            $('#calibrationStep1').removeClass('hidden');
            $('#calibrationStep2').addClass('hidden');
            $('#calibrationStep3').addClass('hidden');
            $('#calibrationStep4').addClass('hidden');

            $('#calibrationTest1').addClass('hidden');
            $('#calibrationTest2').addClass('hidden');

            self.operationLock(false);
        };

        self.nextStepCalibration1 = function() {
            // Sends the command to go to the next calibration point
            self._nextCalibrationStep();

            $('#calibrationStep2').removeClass('hidden');
            $('#calibrationStep1').addClass('hidden');
        };

        self.nextStepCalibration2 = function() {

            // Sends the command to go to the next calibration point
            self._nextCalibrationStep();

            $('#calibrationStep3').removeClass('hidden');
            $('#calibrationStep1').addClass('hidden');
            $('#calibrationStep2').addClass('hidden');
        };

        self.nextStepCalibration3 = function() {
            // Sends the command to go to the next calibration point
            self._nextCalibrationStep();

            $('#calibrationStep4').removeClass('hidden');
            $('#calibrationStep3').addClass('hidden');
            $('#calibrationStep2').addClass('hidden');
            $('#calibrationStep1').addClass('hidden');

            $('#maintenanceOkButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
        };

        self.calibrationTestStep1 = function() {

            self.commandLock(true);
            $('#calibrationStep4').addClass('hidden');
            $('#calibrationStep3').addClass('hidden');
            $('#calibrationStep1').addClass('hidden');
            $('#calibrationStep2').addClass('hidden');

            $('#calibrationTest1').removeClass('hidden');

            $.ajax({
                url: API_BASEURL + "maintenance/start_calibration_test",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.commandLock(false);
                    self._isRunningCalibrationTest();
                },
                error: function() {
                    self.commandLock(false);
                }
            });
        };

        self.cancelCalibrationTest = function() {

            self.commandLock(true);

            $.ajax({
                url: API_BASEURL + "maintenance/cancel_calibration_test",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.commandLock(false);

                    $('#calibrationStep4').removeClass('hidden');
                    $('#calibrationTest1').addClass('hidden');
                },
                error: function() {
                    self.commandLock(false);
                }
            });
        };

        self.repeatCalibration = function() {

            $('#calibrationTest2').addClass('hidden');
            $('#calibrationTest1').removeClass('hidden');

            self.commandLock(true);

            $.ajax({
                url: API_BASEURL + "maintenance/repeat_calibration",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.calibrationStep0();
                    self.nextStepCalibration1();

                    self.commandLock(false);
                },
                error: function() { self.commandLock(false); }
            });
        };

        self.calibrationTestStep2 = function() {

            $('#calibrationTest1').addClass('hidden');
            $('#calibrationTest2').removeClass('hidden');
        };

        self._isRunningCalibrationTest = function () {

            $.ajax({
                url: API_BASEURL + "maintenance/running_calibration_test",
                type: "GET",
                dataType: "json",
                success: function(data) {

                    var printing = data['response'];

                    if (printing == false) {
                        //If the test is finished goes to step2
                        self.calibrationTestStep2();
                        return;
                    }
                    setTimeout(function() { self._isRunningCalibrationTest(); }, 10000);

                },
                error: function() {
                    setTimeout(function() { self._isRunningCalibrationTest(); }, 10000);
                }
            });
        };


        self._sendJogCommand = function (axis, direction, distance) {
            self._showMovingMessage();
            self.commandLock(true);
            var data = {
                "command": "jog"
            };
            data[axis] = distance * direction;

            $.ajax({
                url: API_BASEURL + "printer/printhead",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function() {
                    self.commandLock(false);
                    self._hideMovingMessage();
                },
                error: function() {
                    self.commandLock(false);
                    self._hideMovingMessage();
                }
            });
        };

        self._sendCustomCommand = function (command) {
            $.ajax({
                url: API_BASEURL + "printer/command",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({"command": command})
            });
        };

        self._nextCalibrationStep = function() {

            self.commandLock(true);

            $.ajax({
                url: API_BASEURL + "maintenance/calibration_next",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.commandLock(false);
                },
                error: function() { self.commandLock(false); }
            });
        };

        /***************************************************************************/
        /**********             end Calibrations functions              ************/
        /***************************************************************************/

        /***************************************************************************/
        /**********            Extruder maintenance functions           ************/
        /***************************************************************************/

        self.showExtruderMaintenance = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_extruderMaintenance').removeClass('hidden');

            // Starts the heating operation
            self.startHeatingExtMaint();
        };


        self.extMaintStep0 = function() {
            $('#extMaintStep2').addClass('hidden');
            $('#extMaintStep3').addClass('hidden');

            $('#extMaintStep1').removeClass('hidden');
        };

        self.nextStepExtMaint1 = function() {
            $('#extMaintStep2').removeClass('hidden');
            $('#extMaintStep3').addClass('hidden');
            $('#extMaintStep1').addClass('hidden');
        };

        self.nextStepExtMaint2 = function() {
            $('#extMaintStep3').removeClass('hidden');
            $('#extMaintStep2').addClass('hidden');
            $('#extMaintStep1').addClass('hidden');

            $('#maintenanceOkButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
        };

        self.startHeatingExtMaint = function() {
            cancelTemperatureUpdate = false;
            self.commandLock(true);
            self.operationLock(true);
            self.heatingDone(false);

            $.ajax({
                url: API_BASEURL + "maintenance/start_heating",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    $('#progress-bar-ext-mtn').removeClass('hidden');

                    self._updateTempProgressExtMaint();

                    self.commandLock(false);

                },
                error: function() { self.commandLock(false);  }
            });
        };

        self._updateTempProgressExtMaint = function() {
            fetchTemperatureRetries = 5;

            $.ajax({
                url: API_BASEURL + "maintenance/temperature",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    if (!cancelTemperatureUpdate) {
                        var current_temp = data['temperature'];
                        var progress = ((current_temp / TARGET_TEMPERATURE) * 100).toFixed(0);

                        var tempProgress = $("#temperature-progress-ext-mtn");
                        var tempProgressBar = $(".bar", tempProgress);

                        var progressStr = progress + "%";
                        tempProgressBar.css('width', progressStr);
                        tempProgressBar.text(progressStr);

                        if (progress >= 100) {
                            // Heating is finished, let's move on
                            self._heatingDone();

                            $('#ext-mtn-3').removeClass('hidden');
                            $('#progress-bar-ext-mtn').addClass('hidden');
                        } else {

                            setTimeout(function() { self._updateTempProgressExtMaint() }, 2000);
                        }
                    }
                },
                error: function() {
                    while (fetchTemperatureRetries > 0)
                        setTimeout(function() { self._updateTempProgressExtMaint() }, 2000);
                        fetchTemperatureRetries -= 1;
                    }
            });
        };

        /***************************************************************************/
        /**********         end Extruder maintenance functions          ************/
        /***************************************************************************/

        /***************************************************************************/
        /**************            Replace nozzle functions           **************/
        /***************************************************************************/


        self.showReplaceNozzle = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_replaceNozzle').removeClass('hidden');

            // Starts the heating operation
            self.startHeatingReplaceNozzle();
        };

        self.replaceNozzleStep0 = function() {
            $('#replaceNozzleStep2').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep1').removeClass('hidden');

        };

        self.nextStepReplaceNozzle1 = function() {
            $('#replaceNozzleStep2').removeClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
        };

        self.nextStepReplaceNozzle2 = function() {
            $('#replaceNozzleStep3').removeClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');

            $('#maintenanceOkButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
        };

        self.saveNozzle = function() {
            self.commandLock(true);

            self.nozzleSelected(false);
            self.saveNozzleResponseError(false);

            var data = {
                command: "nozzle",
                nozzleType: self.selectedNozzle()
            };

            $.ajax({
                url: API_BASEURL + "maintenance/save_nozzle",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(data) {
                    var response = data['response'];

                    if (response.indexOf('ok') > -1) {
                        self.nozzleSelected(true);

                        self.commandLock(false);
                        self.operationLock(false);

                        if (self.heatingDone()) {
                            self.nextStepReplaceNozzle2();
                        } else {
                            self.nextStepReplaceNozzle1();
                        }
                    } else {
                        self.saveNozzleResponseError(true);
                        self.commandLock(false);
                    }
                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                    self.saveNozzleResponseError(true);
                }
            });
        };

        self.startHeatingReplaceNozzle = function() {
            cancelTemperatureUpdate = false;
            self.commandLock(true);
            self.operationLock(true);
            self.heatingDone(false);

            $.ajax({
                url: API_BASEURL + "maintenance/start_heating",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    $('#progress-bar-replace-nozzle').removeClass('hidden');

                    self._updateTempProgressReplaceNozzle();

                    self.commandLock(false);

                },
                error: function() { self.commandLock(false);  }
            });
        };

        self._updateTempProgressReplaceNozzle = function() {
            fetchTemperatureRetries = 5;

            $.ajax({
                url: API_BASEURL + "maintenance/temperature",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    if (!cancelTemperatureUpdate) {
                        var current_temp = data['temperature'];
                        var progress = ((current_temp / TARGET_TEMPERATURE) * 100).toFixed(0);

                        var tempProgress = $("#temperature-progress-replace-nozzle");
                        var tempProgressBar = $(".bar", tempProgress);

                        var progressStr = progress + "%";
                        tempProgressBar.css('width', progressStr);
                        tempProgressBar.text(progressStr);

                        if (progress >= 100) {
                            // Heating is finished, let's move on
                            self._heatingDone();

                            if (self.nozzleSelected()) {
                                self.nextStepReplaceNozzle2();
                            }
                        } else {
                            setTimeout(function() { self._updateTempProgressReplaceNozzle() }, 2000);
                        }
                    }
                },
                error: function() {
                    while (fetchTemperatureRetries > 0)
                        setTimeout(function() { self._updateTempProgressReplaceNozzle() }, 2000);
                        fetchTemperatureRetries -= 1;
                    }
            });
        };

        self._getNozzleSizes = function() {

            $.ajax({
                url: API_BASEURL + "maintenance/nozzle_sizes",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    var ntypes = data;
                    self.nozzleSizes.removeAll();

                    _.each(ntypes, function(ntype) {

                        self.nozzleSizes.push({
                            key: ntype.value,
                            name: ntype.value
                        });
                    });
                }
            });
        };

        /***************************************************************************/
        /*************          end Replace nozzle functions           *************/
        /***************************************************************************/
    }

    OCTOPRINT_VIEWMODELS.push([
        MaintenanceViewModel,
        ["loginStateViewModel", "usersViewModel", "printerProfilesViewModel", "printerStateViewModel"],
        ["#maintenance_dialog", "#navbar_maintenance"]
    ]);
});
