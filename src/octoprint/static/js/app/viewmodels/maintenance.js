$(function() {
    function MaintenanceViewModel(parameters) {
        var self = this;
        var cancelTemperatureUpdate = false;
        var fetchTemperatureRetries = 5;
        var TARGET_TEMPERATURE = 210;

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

        self.changeFilament = ko.observable(false);
        self.calibrating = ko.observable(false);
        self.extruderMaintenance = ko.observable(false);
        self.switchNozzle = ko.observable(false);
        self.calibrateExtruder = ko.observable(false);

        self.processStage = ko.observable(0);

        // Helper to store the filament profiles and order them alphabetically
        self.profiles = new ItemListHelper(
            "plugin_cura_profiles",
            {
                "id": function(a, b) {
                    if (a["key"].toLocaleLowerCase() < b["key"].toLocaleLowerCase()) return -1;
                    if (a["key"].toLocaleLowerCase() > b["key"].toLocaleLowerCase()) return 1;
                    return 0;
                },
                "name": function(a, b) {
                    // sorts ascending
                    var aName = a.name();
                    if (aName === undefined) {
                        aName = "";
                    }
                    var bName = b.name();
                    if (bName === undefined) {
                        bName = "";
                    }

                    if (aName.toLocaleLowerCase() < bName.toLocaleLowerCase()) return -1;
                    if (aName.toLocaleLowerCase() > bName.toLocaleLowerCase()) return 1;
                    return 0;
                }
            },
            {},
            "id",
            [],
            [],
            5
        );

        self.selectedFilament = ko.observable();
        self.filamentSelected = ko.observable(false);
        self.filamentResponseError = ko.observable(false);
        self.heatingDone = ko.observable(false);
        self.heatingAchiveTargetTemperature = ko.observable(false);

        self.nozzleSizes = ko.observableArray([]);

        self.selectedNozzle = ko.observable();
        self.nozzleSelected = ko.observable(false);
        self.saveNozzleResponseError = ko.observable(false);

        self.calibrationTestCancelled = false;

        self.filamentInSpool = ko.observable(0.0);
        self.filamentWeightInput = ko.observable();
        self.filamentWeightResponseError = ko.observable(false);
        self.filamentWeightSaveSuccess = ko.observable(false);

        self.onStartup = function() {

            /**
             * Binds the function to automatically show the Change filament dialog to the printer state model
             * for usage in the shutdown panel
             */
            self.printerState.showMaintenanceFilamentChange = function() {
                self.show();

                self.showFilamentChange();
            };
        };

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

            return false;
        };

        self.hide = function() {
            self.maintenanceDialog.modal("hide");
        };

        self._heatingDone = function() {
            self._showMovingMessage();
            $.ajax({
                url: API_BASEURL + "maintenance/heating_done",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    self.heatingDone(true);
                    self._hideMovingMessage();
                },
                error: function() {
                    self.heatingDone(false);
                    self._hideMovingMessage();
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

            $('#maintenanceNextButton').addClass('hidden');
            $('#maintenanceOkButton').addClass('hidden');
            $('#maintenanceCloseButton').removeClass('hidden');


            self.changeFilament(false);
            self.calibrating (false);
            self.extruderMaintenance (false);
            self.switchNozzle (false);
            self.processStage(0);
            self.heatingAchiveTargetTemperature(false);
            // Cancels any heating process
            self.cancelHeating();

            // Returns the operations to the initial step screens
            self.changeFilamentStep0();
            self.calibrationStep0();
            self.replaceNozzleStep0();
            self.calibrateExtruderStep0();
            self.extMaintStep0();

            self._resetProgressBars();

            // Goes to home position
            //self._sendCustomCommand('G28');

            self._hideMovingMessage();
        };

        self.finishOperations = function() {
            $('#maintenanceList').removeClass('hidden');
            $('#cancelMaintenance').addClass('hidden');

            $('#maintenance_changeFilament').addClass('hidden');
            $('#maintenance_calibration').addClass('hidden');
            $('#maintenance_extruderMaintenance').addClass('hidden');
            $('#maintenance_replaceNozzle').addClass('hidden');

            $('#maintenanceCloseButton').removeClass('hidden');

            self.processStage(0);
            self.changeFilament(false);
            self.calibrating (false);
            self.extruderMaintenance (false);
            self.switchNozzle (false);
            self.calibrateExtruder(false)
            self.heatingAchiveTargetTemperature(false);

            // Returns the operations to the initial step screens
            self.changeFilamentStep0();
            self.calibrationStep0();
            self.replaceNozzleStep0();
            self.calibrateExtruderStep0();
            self.extMaintStep0();

            self._resetProgressBars();

            // Goes to home position
            self._sendCustomCommand('G28');

            self._hideMovingMessage();
        };

        self._resetProgressBars = function () {
            // Resets nozzle switch temperature progress
            var tempProgress = $("#temperature-progress-replace-nozzle");
            var tempProgressBar = $(".bar", tempProgress);

            var progressStr = 0 + "%";
            tempProgressBar.css('width', progressStr);
            tempProgressBar.text(progressStr);

            // Resets change filament temperature progress
            tempProgress = $("#temperature_progress");
            tempProgressBar = $(".bar", tempProgress);

            progressStr = 0 + "%";
            tempProgressBar.css('width', progressStr);
            tempProgressBar.text(progressStr);
        };

        self._showMovingMessage = function() {
            $('#maintenance_warning_box').removeClass('hidden');
        };

        self._hideMovingMessage = function() {
            $('#maintenance_warning_box').addClass('hidden');
        };

        self._hasClass = function (element, cls) {
            return (' ' + element.className + ' ').indexOf(' ' + cls + ' ') > -1;
        };

        /***************************************************************************/
        /************             Filament Change functions             ************/
        /***************************************************************************/
        self.showFilamentChange = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_changeFilament').removeClass('hidden');
            $('#maintenanceNextButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
            self.changeFilament(true);

            // Gets the available filament list
            self._getFilamentProfiles();

            // Gets the amount of filament left in spool
            self._getFilamentInSpool();

            // Starts heating automatically
            self.startHeating();
        };

        self.changeFilamentStep0 = function() {
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').removeClass('hidden');

            var tempProgress = $("#temperature_progress");
            var tempProgressBar = $(".bar", tempProgress);

            tempProgressBar.css('width', '0%');
            tempProgressBar.text('0%');

            $('#start-heating-btn').removeClass('hidden');
            $('#progress-bar-div').addClass('hidden');
            $('#change-filament-heating-done').addClass('hidden');

            self.operationLock(false);

            self.filamentSelected(false);
            self.filamentResponseError(false);
            self.filamentWeightSaveSuccess(false);
            self.filamentWeightResponseError(false);

            $('#maintenanceOkButton').addClass('hidden');
        };

        self.nextStep2 = function() {
            $('#step2').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').addClass('hidden');
            if (!self.heatingDone() && !self.heatingAchiveTargetTemperature()){
                $('#maintenanceNextButton').addClass('hidden');
            }
        };

        self.nextStep3 = function() {
            // Heating is finished, let's move on
            self._heatingDone();
            self.saveFilament();

            $('#step3').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
        };

        self.nextStep4 = function() {
            $('#step4').removeClass('hidden');
            $('#step3').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
            $('#maintenanceNextButton').addClass('hidden');
            $('#maintenanceOkButton').removeClass('hidden');
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
                success: function(result) {
                    $('#start-heating-btn').addClass('hidden');
                    $('#progress-bar-div').removeClass('hidden');

                    TARGET_TEMPERATURE = result['target_temperature'];
                    self._updateTempProgress();

                    self.commandLock(false);
                },
                error: function() { self.commandLock(false);  }
            });
        };

        /***************************************************************************/
        /************             Filament Change functions             ************/
        /***************************************************************************/
        self.showFilamentChange = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_changeFilament').removeClass('hidden');
            $('#maintenanceNextButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
            self.changeFilament(true);

            // Gets the available filament list
            self._getFilamentProfiles();

            // Gets the amount of filament left in spool
            self._getFilamentInSpool();

            // Starts heating automatically
            self.startHeating();
        };

        self.changeFilamentStep0 = function() {
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').removeClass('hidden');

            var tempProgress = $("#temperature_progress");
            var tempProgressBar = $(".bar", tempProgress);

            tempProgressBar.css('width', '0%');
            tempProgressBar.text('0%');

            $('#start-heating-btn').removeClass('hidden');
            $('#progress-bar-div').addClass('hidden');
            $('#change-filament-heating-done').addClass('hidden');

            self.operationLock(false);

            self.filamentSelected(false);
            self.filamentResponseError(false);
            self.filamentWeightSaveSuccess(false);
            self.filamentWeightResponseError(false);

            $('#maintenanceOkButton').addClass('hidden');
        };

        self.nextStep2 = function() {
            $('#step2').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').addClass('hidden');
            if (!self.heatingDone() && !self.heatingAchiveTargetTemperature()){
                $('#maintenanceNextButton').addClass('hidden');
            }
        };

        self.nextStep3 = function() {
            // Heating is finished, let's move on
            self._heatingDone();
            self.saveFilament();

            $('#step3').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
        };

        self.nextStep4 = function() {
            $('#step4').removeClass('hidden');
            $('#step3').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
            $('#maintenanceNextButton').addClass('hidden');
            $('#maintenanceOkButton').removeClass('hidden');
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
                success: function(result) {
                    $('#start-heating-btn').addClass('hidden');
                    $('#progress-bar-div').removeClass('hidden');

                    TARGET_TEMPERATURE = result['target_temperature'];
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

                        if ((TARGET_TEMPERATURE - current_temp) <= 5) { // If the temperature is within 5º of target
                            self.heatingAchiveTargetTemperature(true);
                            $('#change-filament-heating-done').removeClass('hidden');
                            $('#maintenanceNextButton').removeClass('hidden');
                            $('#progress-bar-div').addClass('hidden');
                        } else {
                            setTimeout(function() { self._updateTempProgress() }, 2000);
                        }
                    }
                },
                error: function() {
                    while (fetchTemperatureRetries > 0) {
                        setTimeout(function() { self._updateTempProgress() }, 2000);
                        fetchTemperatureRetries -= 1;
                    }
                }
            });
        };

        self.loadFilament = function() {
            self.commandLock(true);
            self._showMovingMessage();
            $('.load-gifs').show();
            $('.unload-gifs').hide();

            $.ajax({
                url: API_BASEURL + "maintenance/load",
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

        self.unloadFilament = function() {
            self.commandLock(true);
            self._showMovingMessage();
            $('.load-gifs').hide();
            $('.unload-gifs').show();

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
                    TARGET_TEMPERATURE = data['target_temperature'];

                    if (response.indexOf('ok') > -1) {
                        self.filamentSelected(true);

                    } else {
                        self.filamentResponseError(true);
                    }

                    self.commandLock(false);
                    self.operationLock(false);
                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                    self.filamentResponseError(true);
                }
            });
        };

        self.saveFilamentWeight = function() {
            self.commandLock(true);

            self.filamentWeightSaveSuccess(false);
            self.filamentWeightResponseError(false);

            var data = {
                command: "filament",
                filamentWeight: self.filamentWeightInput()
            };

            $.ajax({
                url: API_BASEURL + "maintenance/set_filament_weight",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(data) {
                    var response = data['response'];

                    if (response.indexOf('ok') > -1) {
                        self.filamentWeightSaveSuccess(true);


                        self.commandLock(false);
                        self.operationLock(false);

                    } else {
                        self.filamentWeightResponseError(true);
                        self.commandLock(false);
                    }
                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                    self.filamentWeightResponseError(true);
                }
            });
        };

        self._getFilamentProfiles = function(postCallback) {

            $.ajax({
                url: API_BASEURL + "maintenance/filament_profiles",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    // Stores the API call result in a ItemListHelper so the values are sorted alphabetically by key
                    var profiles = [];
                    _.each(_.keys(data), function(key) {
                        profiles.push({
                            key: key,
                            name: ko.observable(data[key].displayName),
                        });
                    });
                    self.profiles.updateItems(profiles);

                    self.filamentProfiles.removeAll();

                    _.each(profiles, function(profile) {

                        // Parses the list and filters for BVC colors
                        // Assumes the '_' nomenclature separation for the profile names
                        var profile_parts = profile.name().split('_');
                        if (profile_parts[0] != null) {
                            var color = profile_parts[0];
                            if (!_.findWhere(self.filamentProfiles(), color)) {
                                self.filamentProfiles.push(color);
                            }
                        }
                    });

                    if (postCallback !== undefined) {
                        postCallback();
                    }
                }
            });
        };

        self._getFilamentInSpool = function() {
            $.ajax({
                url: API_BASEURL + "maintenance/get_filament_spool",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    self.filamentInSpool(Math.round(data.filament));
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
            self.calibrating(true);
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_calibration').removeClass('hidden');
            $('#maintenanceNextButton').removeClass('hidden');

            $('#maintenanceCloseButton').addClass('hidden');

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
            $('#maintenanceNextButton').addClass('hidden');
        };

        self.calibrationTestStep1 = function() {

            self.commandLock(true);
            $('#calibrationStep4').addClass('hidden');
            $('#calibrationStep3').addClass('hidden');
            $('#calibrationStep1').addClass('hidden');
            $('#calibrationStep2').addClass('hidden');

            $('#calibrationTest1').removeClass('hidden');

            $('#maintenanceOkButton').addClass('hidden');
            $('#cancelMaintenance').addClass('hidden');

            self.calibrationTestCancelled = false;

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
                    self.calibrationTestCancelled = true;

                    $('#calibrationStep4').removeClass('hidden');
                    $('#calibrationTest1').addClass('hidden');
                    $('#calibrationTest2').addClass('hidden');

                    $('#maintenanceOkButton').removeClass('hidden');
                    $('#cancelMaintenance').removeClass('hidden');
                    $('#maintenanceNextButton').addClass('hidden');
                },
                error: function() {
                    self.commandLock(false);
                }
            });
        };

        self.repeatCalibration = function() {

            $('#calibrationTest2').addClass('hidden');
            $('#calibrationTest1').removeClass('hidden');

            $('#maintenanceNextButton').removeClass('hidden');
            $('#maintenanceOkButton').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');

            self.commandLock(true);
            self.calibrationTestCancelled = false;

            $.ajax({
                url: API_BASEURL + "maintenance/repeat_calibration",
                type: "POST",
                dataType: "json",
                success: function() {
                    self.calibrationStep0();

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

                    if (printing == false && self.calibrationTestCancelled == false) {
                        //If the test is finished goes to step2
                        self.calibrationTestStep2();
                        return;
                    }

                    if (!self.calibrationTestCancelled) {
                        setTimeout(function() { self._isRunningCalibrationTest(); }, 5000);
                    }
                },
                error: function() {
                    setTimeout(function() { self._isRunningCalibrationTest(); }, 5000);
                }
            });
        };


        self._sendJogCommand = function (axis, direction, distance) {
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
                },
                error: function() {
                    self.commandLock(false);
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
            $('#maintenanceNextButton').removeClass('hidden');
            self.extruderMaintenance(true);
            // Starts the heating operation
            self.startHeatingExtMaint();

            $('#maintenanceCloseButton').addClass('hidden');
            $('#ext-mtn-4').addClass('hidden');
        };


        self.extMaintStep0 = function() {
            $('#extMaintStep2').addClass('hidden');
            $('#extMaintStep3').addClass('hidden');
            $('#extMaintStep4').addClass('hidden');

            $('#extMaintStep1').removeClass('hidden');
        };

        self.nextStepExtMaint1 = function() {
            $('#extMaintStep2').removeClass('hidden');
            $('#extMaintStep3').addClass('hidden');
            $('#extMaintStep1').addClass('hidden');
            $('#extMaintStep4').addClass('hidden');
        };

        self.nextStepExtMaint2 = function() {
            $('#extMaintStep3').removeClass('hidden');
            $('#extMaintStep2').addClass('hidden');
            $('#extMaintStep1').addClass('hidden');
            $('#extMaintStep4').addClass('hidden');
            if (!self.heatingDone() && !self.heatingAchiveTargetTemperature()){
                $('#maintenanceNextButton').addClass('hidden');
            }
        };

        self.nextStepExtMaint3 = function() {
            // Heating is finished, let's move on
            self._heatingDone();

            self.finishExtruderMaintenance();

            $('#extMaintStep4').removeClass('hidden');
            $('#extMaintStep3').addClass('hidden');
            $('#extMaintStep2').addClass('hidden');
            $('#extMaintStep1').addClass('hidden');

            $('#maintenanceNextButton').addClass('hidden');
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
                success: function(result) {
                    $('#progress-bar-ext-mtn').removeClass('hidden');

                    TARGET_TEMPERATURE = result['target_temperature'];
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

                        if ((TARGET_TEMPERATURE - current_temp) <= 5) { // If the temperature is within 5º of target
                            self.heatingAchiveTargetTemperature(true);
                            $('#ext-mtn-4').removeClass('hidden');
                            $('#maintenanceNextButton').removeClass('hidden');
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

        self.finishExtruderMaintenance = function() {

            $.ajax({
                url: API_BASEURL + "maintenance/finish_extruder_maintenance",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function(result) {


                },
                error: function() {  }
            });
        };

        /***************************************************************************/
        /**********         end Extruder maintenance functions          ************/
        /***************************************************************************/

        /***************************************************************************/
        /**************            Replace nozzle functions           **************/
        /***************************************************************************/

        self.showReplaceNozzle = function() {
            self.switchNozzle(true);

            // Gets the available nozzle size list
            self._getNozzleSizes();

            $('#maintenanceNextButton').removeClass('hidden');
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_replaceNozzle').removeClass('hidden');

            $('#maintenanceCloseButton').addClass('hidden');
        };

        self.replaceNozzleStep0 = function() {
            $('#replaceNozzleStep1').removeClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
        };

        self.nextStepReplaceNozzle1 = function() {
            // Starts the heating operation
            self.startHeatingReplaceNozzle();
            if (!self.heatingDone() && !self.heatingAchiveTargetTemperature()){
                $('#maintenanceNextButton').addClass('hidden');
            }
            $('#replaceNozzleStep2').removeClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
        };

        self.nextStepReplaceNozzle2 = function() {
            // Heating is finished, let's move on
            self._heatingDone();

            $('#replaceNozzleStep3').removeClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
        };

        self.nextStepReplaceNozzle3 = function() {
            $('#replaceNozzleStep4').removeClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
        };

        self.nextStepReplaceNozzle4 = function() {
            $('#replaceNozzleStep5').removeClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
        };

        self.nextStepReplaceNozzle5 = function() {
            $('#replaceNozzleStep6').removeClass('hidden');
            $('#replaceNozzleStep7').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
        };

        self.nextStepReplaceNozzle6 = function() {
            $('#replaceNozzleStep7').removeClass('hidden');
            $('#replaceNozzleStep4').addClass('hidden');
            $('#replaceNozzleStep3').addClass('hidden');
            $('#replaceNozzleStep1').addClass('hidden');
            $('#replaceNozzleStep2').addClass('hidden');
            $('#replaceNozzleStep5').addClass('hidden');
            $('#replaceNozzleStep6').addClass('hidden');
        };

        self.proceedToChangeFilament = function() {
            $('#maintenance_replaceNozzle').addClass('hidden');
            $('#maintenanceNextButton').removeClass('hidden');
            self.changeFilament(true);
            self.calibrating (false);
            self.extruderMaintenance (false);
            self.switchNozzle (false);
            self.processStage(0);
            self.heatingAchiveTargetTemperature(false);

            self.showFilamentChange();
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

                        // Moves to the next step
                        self.nextStepReplaceNozzle6();
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
                success: function(result) {
                    $('#progress-bar-replace-nozzle').removeClass('hidden');
                    $('#replace-nozzle-heating-done').addClass('hidden');

                    TARGET_TEMPERATURE = result['target_temperature'];
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

                        if (progress >= 95) {
                            self.heatingAchiveTargetTemperature(true);
                            $('#replace-nozzle-heating-done').removeClass('hidden');
                            $('#progress-bar-replace-nozzle').addClass('hidden');
                            $('#maintenanceNextButton').removeClass('hidden');

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
                url: API_BASEURL + "maintenance/get_nozzle_list",
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

        self.loadFilamentReplaceNozzle = function() {
            self.commandLock(true);
            self._showMovingMessage();

            $.ajax({
                url: API_BASEURL + "maintenance/load",
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

        self.unloadFilamentReplaceNozzle = function() {
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

        self.saveFilamentReplaceNozzle = function() {
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
                    TARGET_TEMPERATURE = data['target_temperature'];

                    if (response.indexOf('ok') > -1) {
                        self.filamentSelected(true);

                        self.finishOperations();
                    } else {
                        self.filamentResponseError(true);
                    }

                    self.commandLock(false);
                    self.operationLock(false);
                },
                error: function() {
                    self.commandLock(false);
                    self.operationLock(false);
                    self.filamentResponseError(true);
                }
            });
        };

        self.nextOperations = function() {
            self.processStage(self.processStage()+1);
            if (self.calibrating()) {
                if(self.processStage() == 1)
                {
                    self.nextStepCalibration1();
                }
                if(self.processStage() == 2)
                {
                    self.nextStepCalibration2();
                }
                if(self.processStage() == 3)
                {
                    self.nextStepCalibration3();
                }
            }
            if (self.switchNozzle()) {
                if(self.processStage() == 1)
                {
                    self.nextStepReplaceNozzle1();
                }
                if(self.processStage() == 2)
                {
                    self.nextStepReplaceNozzle2();
                }
                if(self.processStage() == 3)
                {
                    self.nextStepReplaceNozzle3();
                }
                if(self.processStage() == 4)
                {
                    self.nextStepReplaceNozzle4();
                }
                if(self.processStage() == 5)
                {
                    self.nextStepReplaceNozzle5();
                }
                if(self.processStage() == 6)
                {
                    self.saveNozzle();
                }
            }
            if (self.changeFilament()) {
                if(self.processStage() == 1)
                {
                    self.nextStep2();
                }
                if(self.processStage() == 2)
                {
                    self.nextStep3();
                }
                if(self.processStage() == 3)
                {
                    self.nextStep4();
                }
            }
            if (self.extruderMaintenance()) {
                if(self.processStage() == 1)
                {
                    self.nextStepExtMaint1();
                }
                if(self.processStage() == 2)
                {
                    self.nextStepExtMaint2();
                }
                if(self.processStage() == 3)
                {
                    self.nextStepExtMaint3();
                }
            }
        };

        self.nextButtonEnable = function() {
            if (self.calibrating()) {
                if(self.processStage() == 0 || self.processStage() == 1 || self.processStage() == 2 || self.processStage() == 3 )
                {
                    return  self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser();
                }
            }
            if (self.switchNozzle()) {
                if(self.processStage() == 0 || self.processStage() == 1 || self.processStage() == 2 || self.processStage() == 3 || self.processStage() == 4)
                {
                    return self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser();
                }
                if(self.processStage()==5)
                {
                    return self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser() && self.selectedNozzle;
                }
            }
            if (self.changeFilament()) {
                if(self.processStage() == 0 || self.processStage() == 1)
                {
                    return  self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser() && self.selectedFilament;
                }
                if(self.processStage() == 2)
                {
                    return  self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser();
                }
            }
            if (self.extruderMaintenance()) {
                if(self.processStage() == 0  || self.processStage() == 1  || self.processStage() == 2 || self.processStage() == 3 )
                {
                    return  self.printerState.isOperational() && !self.commandLock()
                        && self.printerState.isReady() && !self.printerState.isPrinting() && self.loginState.isUser();
                }
            }
        };

        /***************************************************************************/
        /*************          end Replace nozzle functions           *************/
        /***************************************************************************/

        /***************************************************************************/
        /************             Extruder Calibration functions             ************/
        /***************************************************************************/
        self.showCalibrateExtruder = function() {
            $('#maintenanceList').addClass('hidden');
            $('#cancelMaintenance').removeClass('hidden');

            $('#maintenance_calibrateExtruder').removeClass('hidden');
            $('#maintenanceNextButton').removeClass('hidden');
            $('#maintenanceCloseButton').addClass('hidden');
            self.calibrateExtruder(true);

            // Gets the available filament list
            self._getFilamentProfiles();

            // Gets the amount of filament left in spool
            self._getFilamentInSpool();

            // Starts heating automatically
            self.startHeating();

            self.switchNozzle(true);

            // Gets the available nozzle size list
            self._getNozzleSizes();

        };

        self.calibrationStep0 = function() {
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').removeClass('hidden');

            var tempProgress = $("#temperature_progress");
            var tempProgressBar = $(".bar", tempProgress);

            tempProgressBar.css('width', '0%');
            tempProgressBar.text('0%');

            $('#start-heating-btn').removeClass('hidden');
            $('#progress-bar-div').addClass('hidden');
            $('#change-filament-heating-done').addClass('hidden');

            self.operationLock(false);

            self.filamentSelected(false);
            self.filamentResponseError(false);
            self.filamentWeightSaveSuccess(false);
            self.filamentWeightResponseError(false);

            $('#maintenanceOkButton').addClass('hidden');
        };

        self.nextStep2 = function() {
            $('#step2').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step3').addClass('hidden');
            $('#step1').addClass('hidden');
            if (!self.heatingDone() && !self.heatingAchiveTargetTemperature()){
                $('#maintenanceNextButton').addClass('hidden');
            }
        };

        self.nextStep3 = function() {
            // Heating is finished, let's move on
            self._heatingDone();
            self.saveFilament();

            $('#step3').removeClass('hidden');
            $('#step4').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
        };

        self.nextStep4 = function() {
            $('#step4').removeClass('hidden');
            $('#step3').addClass('hidden');
            $('#step2').addClass('hidden');
            $('#step1').addClass('hidden');
            $('#maintenanceNextButton').addClass('hidden');
            $('#maintenanceOkButton').removeClass('hidden');
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
                success: function(result) {
                    $('#start-heating-btn').addClass('hidden');
                    $('#progress-bar-div').removeClass('hidden');

                    TARGET_TEMPERATURE = result['target_temperature'];
                    self._updateTempProgress();

                    self.commandLock(false);
                },
                error: function() { self.commandLock(false);  }
            });
        };

        /***************************************************************************/
        /*************          end Calibrate Extruder functions           *************/
        /***************************************************************************/
    }

    OCTOPRINT_VIEWMODELS.push([
        MaintenanceViewModel,
        ["loginStateViewModel", "usersViewModel", "printerProfilesViewModel", "printerStateViewModel"],
        ["#maintenance_dialog", "#navbar_maintenance"]
    ]);
});
