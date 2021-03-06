$(function() {
    function SlicingViewModel(parameters) {
        var self = this;

        $.ajaxSetup({ cache: false });		//command for do not caching the results of AJAX calls - this fixs some problems when connecting to BTFs and BTFs+ alternately.


        self.loginState = parameters[0];
        self.printerProfiles = parameters[1];

        self.file = ko.observable(undefined);
        self.target = undefined;
        self.path = undefined;
        self.data = undefined;

        self.defaultSlicer = undefined;
        self.defaultProfile = undefined;

        self.destinationFilename = ko.observable();
        self.gcodeFilename = self.destinationFilename; // TODO: for backwards compatibility, mark deprecated ASAP

        self.title = ko.observable();
        self.slicer = ko.observable();
        self.slicers = ko.observableArray();
        self.profile = ko.observable();
        self.profiles = ko.observableArray();
        self.printerProfile = ko.observable();

        self.colors = ko.observableArray();
        self.selColor = ko.observable();
        self.selDensity = ko.observable("Low");
        self.customDensity = ko.observable();
        self.selResolution = ko.observable("Medium");
        self.platformAdhesion = ko.observable("None");
        self.support = ko.observable("None");
        self.nozzleTypes = ko.observableArray();
        self.selNozzle = ko.observable();
        self.filamentInSpool = ko.observable();
        self.workbenchFile = false; // Signals if the slice dialog was called upon a workbench scene

        self.sliceButtonControl = ko.observable(true); // Controls the button enabled state

        self.estimateButtonControl = ko.observable(true); // Controls the button enabled state
        self.estimationDialog = ko.observable(false); // Signals if the dialog was called with the force option for estimation
        self.estimationReady = ko.observable(false);
        self.estimating = ko.observable(false);
        self.slicingDoneEstimationCallback = undefined; // Callback function to be called after the slicing event has finished
        self.estimatedPrintTime = ko.observable();
        self.estimatedFilament = ko.observable();
        self.showAdhesionOptions = ko.observable(true);

        self.gcodeDownloadLink = ko.observable();

        self.slicerSameDevice = ko.observable();

        self.allViewModels = undefined;

        self.slicingInProgress = ko.observable(false); // this flag is used to control the visibility of the main Print... button

        self.slicingDialog = $("#slicing_configuration_dialog");

        self.slicersForFile = function(file) {
            if (file === undefined) {
                return [];
            }

            return _.filter(self.configuredSlicers(), function(slicer) {
                return _.any(slicer.sourceExtensions, function(extension) {
                    return _.endsWith(file.toLowerCase(), "." + extension.toLowerCase());
                });
            });
        };

        self.resetProfiles = function() {
            self.profiles.removeAll();
            self.profile(undefined);
        };

        self.metadataForSlicer = function(key) {
            if (key == undefined || !self.data.hasOwnProperty(key)) {
                return;
            }

            var slicer = self.data[key];
            self.slicerSameDevice(slicer.sameDevice);
        };

        self.resetMetadata = function() {
            self.slicerSameDevice(true);
        };

        self.configuredSlicers = ko.pureComputed(function() {
            return _.filter(self.slicers(), function(slicer) {
                return slicer.configured;
            });
        });

        self.matchingSlicers = ko.computed(function() {
            var slicers = self.slicersForFile(self.file());

            var containsSlicer = function(key) {
                return _.any(slicers, function(slicer) {
                    return slicer.key == key;
                });
            };

            var current = self.slicer();
            if (!containsSlicer(current)) {
                if (self.defaultSlicer !== undefined && containsSlicer(self.defaultSlicer)) {
                    self.slicer(self.defaultSlicer);
                } else {
                    self.slicer(undefined);
                    self.resetProfiles();
                }
            } else {
                self.profilesForSlicer(self.slicer());
            }

            return slicers;
        });

        self.afterSlicingOptions = [
            {"value": "none", "text": gettext("Do nothing")},
            {"value": "select", "text": gettext("Select for printing")},
            {"value": "print", "text": gettext("Start printing")}
        ];
        self.afterSlicing = ko.observable("none");

        self.show = function(target, file, force, workbench, path) {
            self.estimationDialog(false);
            self.slicingDoneEstimationCallback = undefined;
            self.estimatedPrintTime(null);
            self.estimatedFilament(null);

            if (!BEEwb.main.isModelInPlatform()) {
                html = _.sprintf(gettext("There is no model on the platform. First import a model to print or estimate the print time."));
                new PNotify({title: gettext("No model on the platform"), text: html, type: "warning", hide: false});
                return;
            }

            if (BEEwb.helpers.isSceneOverAdhesionThreshold()) {
            	self.showAdhesionOptions(false);
            	self.platformAdhesion('disabled');
            } else {
            	self.showAdhesionOptions(true);
            	self.platformAdhesion('None');
            }

            if (force === true) {
                self.estimationDialog(true);
            }

            var filename = file.substr(0, file.lastIndexOf("."));
            if (filename.lastIndexOf("/") != 0) {
                path = path || filename.substr(0, filename.lastIndexOf("/"));
                filename = filename.substr(filename.lastIndexOf("/") + 1);
            }

            self.requestData(function() {
                if (!self.enableSlicingDialog() && !self.estimationDialog()) {
                    html = _.sprintf(gettext("Could not estimate the print operation. Please make sure the slicer is configured, or contact the support for help."));
                    new PNotify({title: gettext("No slicer configured"), text: html, type: "error", hide: true});
                    return;
                }
                self._nozzleFilamentUpdate();
                self.target = target;
                self.file(file);
                self.path = path;self.title(_.sprintf(gettext("Slicing %(filename)s"), {filename: filename}));
                self.destinationFilename(filename);
                self.printerProfile(self.printerProfiles.currentProfile());
                self.afterSlicing("print");

                self.slicingDialog.modal({
                    backdrop: 'static',
                    keyboard: false
                });
                self.slicingDialog.modal("show");

                // Flag to signal if the slicing window was called by the workbench
                self.workbenchFile = workbench;
            });
        };

        self.slicer.subscribe(function(newValue) {
            if (newValue === undefined) {
                self.resetProfiles();
                self.resetMetadata();
            } else {
                self.profilesForSlicer(newValue);
                self.metadataForSlicer(newValue);
            }
        });

        self.enableSlicingDialog = ko.pureComputed(function() {
            return self.configuredSlicers().length > 0;
        });

        self.enableSlicingDialogForFile = function(file) {
            return self.slicersForFile(file).length > 0;
        };

        self.enableSliceButton = ko.pureComputed(function() {
            return self.destinationFilename() !== undefined
                && self.destinationFilename().trim() !== ""
                && self.slicer() != undefined
                && self.sliceButtonControl()
                && !self.estimationDialog();
        });

        self.sliceButtonTooltip = ko.pureComputed(function() {
            if (!self.enableSliceButton()) {
                if (self.slicerSameDevice()) {
                    return gettext("Cannot slice on the same device while printing");
                } else {
                    return gettext("Cannot slice, not all parameters specified");
                }
            } else {
                return gettext("Start the slicing process");
            }
        });

        self.enableEstimateButton = ko.pureComputed(function() {
            return self.estimateButtonControl();
        });

        self.requestData = function(callback) {
            return OctoPrint.slicing.listAllSlicersAndProfiles()
                .done(function(data) {
                    self.fromResponse(data);
                    if (callback !== undefined) {
                        callback();
                    }
                });
        };

        self.destinationExtension = ko.pureComputed(function() {
            var fallback = "???";
            if (self.slicer() === undefined) {
                return fallback;
            }
            var slicer = self.data[self.slicer()];
            if (slicer === undefined) {
                return fallback;
            }
            var extensions = slicer.extensions;
            if (extensions === undefined) {
                return fallback;
            }
            var destinationExtensions = extensions.destination;
            if (destinationExtensions === undefined || !destinationExtensions.length) {
                return fallback;
            }

            return destinationExtensions[0] || fallback;
        });

        self._nozzleFilamentUpdate = function() {
            $.ajax({
                url: API_BASEURL + "maintenance/get_nozzles_and_filament",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    self.nozzleTypes.removeAll();
                    var nozzleList = data.nozzleList;

                    for (var key in nozzleList) {
                        self.nozzleTypes.push(nozzleList[key].value);
                    }

                    self.selNozzle(data.nozzle);

                    if (data.filament !== null) {
						//console.log(self.colors());
						//alert("self.colors() was written to the console...");

                        self.colors().forEach(function(elem) {
                            var elem_reduced = elem.replace("#  ", "")
                                                   .replace("# ", "");
//                                                   .replace("BTF+", "")			<- not necessary.
//                                                   .replace("BTF", "")
//                                                   .replace("TPU 04", "TPU")
//                                                   .replace("TPU 06", "TPU");
//							console.log(elem);
//							console.log(elem_reduced);
//							console.log(data.filament);
                            var flag = (elem_reduced === data.filament);

                            if (flag) {
                                self.selColor(elem);
                            }
/*							if (elem === data.filament){
								self.selColor(elem);
							} */
                        });
                    } else {
                        // Selects the first color from the list by default
                        if (self.colors().length > 0) {
                            self.selColor(self.colors()[0]);
                        }
                    }

					if (data.filamentInSpool === null) {
						self.filamentInSpool(null);
					} else {
						self.filamentInSpool(Math.round(data.filamentInSpool));
					}
                }
            });
        };
        self.enableHighPlusResolution = ko.pureComputed(function() {
            return self.selNozzle() != "0.6";
        });

        self.forPrint = function() {
            if (self.afterSlicing() != "none")
                return true;

            return false;
        };

        self.fromResponse = function(data) {
            self.data = data;

            var selectedSlicer = undefined;
            self.slicers.removeAll();
            _.each(_.values(data), function(slicer) {
                var name = slicer.displayName;
                if (name == undefined) {
                    name = slicer.key;
                }

                if (slicer.default && slicer.configured) {
                    selectedSlicer = slicer.key;
                }

                var props = {
                    key: slicer.key,
                    name: name,
                    configured: slicer.configured,
                    sourceExtensions: slicer.extensions.source,
                    destinationExtensions: slicer.extensions.destination,
                    sameDevice: slicer.sameDevice
                };
                self.slicers.push(props);
            });

            self.defaultSlicer = selectedSlicer;

            if (self.allViewModels) {
                callViewModels(self.allViewModels, "onSlicingData", [data]);
            }
        };

        self.profilesForSlicer = function(key) {
            if (key == undefined) {
                key = self.slicer();
            }
            if (key == undefined || !self.data.hasOwnProperty(key)) {
                return;
            }
            var slicer = self.data[key];

            var selectedProfile = undefined;
            self.profiles.removeAll();
            self.colors.removeAll();

            _.each(_.values(slicer.profiles), function(profile) {
                var name = profile.displayName;
                if (name == undefined) {
                    name = profile.key;
                }

                if (profile.default) {
                    selectedProfile = profile.key;
                }

                self.profiles.push({
                    key: profile.key,
                    name: name
                });

                // Fills the colors = filaments list
                self.colors.push(name);

            });

            if (selectedProfile != undefined) {
                self.profile(selectedProfile);
            }

            self.defaultProfile = selectedProfile;
        };

        self._removeTempGcode = function(callback) {
            // Removes any previous file with the same name
            $.ajax({
                url: API_BASEURL + "files/" + self.target + "/" + self.destinationFilename() + ".gco",
                type: "DELETE",
                success: function() {
                    if (callback !== undefined) {
                        callback();
                    }
                },
                error: function () {
                    if (callback !== undefined) {
                        callback();
                    }
                }
            });
        };

        /**
         * Calls the slicing API and presents the time/cost estimations to the user
         */
        self.sliceAndEstimate = function() {
            $(".slice-option:not(.closed)").click();

            self.estimating(true);
            self.estimateButtonControl(false);
            self.sliceButtonControl(false);

            self.estimationReady(false);
            self.gcodeDownloadLink(null);
            self.afterSlicing("none");

            if (self.destinationFilename()) {
                self._removeTempGcode(self.prepareAndSlice)
            } else {
                self.prepareAndSlice();
            }

            self.slicingDoneEstimationCallback = function () {
                $.ajax({
                    url: API_BASEURL + "files/" + self.target + "/" + self.destinationFilename() + ".gco",
                    type: "GET",
                    dataType: "json",
                    contentType: "application/json; charset=UTF-8",
                    success: function ( data ) {
                        if (data["gcodeAnalysis"]) {
                            self.estimatedPrintTime(gettext("Estimated print time")
                            + ": " + formatDurationHoursMinutes(data["gcodeAnalysis"]["estimatedPrintTime"]));

                            if (data["gcodeAnalysis"]["filament"] && typeof(data["gcodeAnalysis"]["filament"]) == "object") {
                                var filament = data["gcodeAnalysis"]["filament"];
                                if (_.keys(filament).length == 1) {
                                    self.estimatedFilament(gettext("Filament") + ": " + formatFilament(data["gcodeAnalysis"]["filament"]["tool" + 0]));

                                } else if (_.keys(filament).length > 1) {
                                    for (var toolKey in filament) {
                                        if (!_.startsWith(toolKey, "tool") || !filament[toolKey] || !filament[toolKey].hasOwnProperty("length") || filament[toolKey]["length"] <= 0) continue;

                                        self.estimatedFilament(gettext("Filament") +  ": " + formatFilament(filament[toolKey]));
                                    }
                                }
                            }
                        }

                        if (data["refs"] && data["refs"]["download"]) {
                            self.gcodeDownloadLink(data["refs"]["download"]);
                        }

                        self.estimating(false);
                        self.estimationReady(true);
                        self.estimateButtonControl(true);
                        self.sliceButtonControl(true);
                    },
                    error: function ( response ) {
                        html = _.sprintf(gettext("Unable to get time estimation for file."));
                        new PNotify({title: gettext("Estimation failed"), text: html, type: "error", hide: false});
                        self.estimateButtonControl(true);
                        self.sliceButtonControl(true);
                        self.estimating(false);
                    }
                })
            };
        };

        /**
         * Saves the current workbench scene and calls the slicing operation on the resulting STL file
         */
        self.prepareAndSlice = function() {

            self.sliceButtonControl(false);
            self.slicingInProgress(true);

            // Checks if the slicing was called on a workbench scene and finally saves it
            if (self.workbenchFile) {

                // NOTE: setTimeout is a workaround to allow the saveScene function to run
                // separately and release this "thread" so the button is disabled
                setTimeout(function() {
                    var saveCall = BEEwb.main.saveScene(self.file());
                    // waits for the save operation
                    saveCall.done( function () {
                        self.slice(self.file());
                    });
                }, 10);

            } else {
                self.slice(undefined);
            }
        };


        /**
         * Function that is run during the cancel/close of the dialog
         */
        self.closeSlicing = function() {
            //Makes sure the options panels are all expanded after the dialog is closed
            $(".slice-option.closed").click();

            if (self.estimationReady() && self.destinationFilename()) {
                self._removeTempGcode()
            }

            self.estimationReady(false);
            self.slicingInProgress(false);
        };

        self.slice = function(modelToRemoveAfterSlice) {
            // Selects the slicing profile based on the color and resolution
            if (self.selColor() !== null && self.selResolution() !== null) {

				var selected_colour;
				if (self.estimationDialog()){
					selected_colour = BEEwb.helpers.get_selected_filament();	//-> uses the filament profile selected by the user at the estimation panel;
				}
				else{
					selected_colour = self.selColor();							//-> uses the filament profile at machine.
				}
                _.each(self.profiles(), function(profile) {
                    // checks if the profile contains the selected color and nozzle size
                    if (_.contains(profile.name, selected_colour)) {
                        self.profile(profile.key);
                    }
                });
            }

            var destinationFilename = self._sanitize(self.destinationFilename());

            var destinationExtensions = self.data[self.slicer()] && self.data[self.slicer()].extensions && self.data[self.slicer()].extensions.destination
                                        ? self.data[self.slicer()].extensions.destination
                                        : ["???"];
            if (!_.any(destinationExtensions, function(extension) {
                    return _.endsWith(destinationFilename.toLowerCase(), "." + extension.toLowerCase());
                })) {
                destinationFilename = destinationFilename + "." + destinationExtensions[0];
            }

            var data = {
                slicer: self.slicer(),
                profile: self.profile(),
                resolution: self.selResolution(),
                nozzle: self.selNozzle(),
                printerProfile: self.printerProfile(),
                destination: destinationFilename
            };

            if (self.path != undefined) {
                data["path"] = self.path;
            }

            if (self.afterSlicing() === "print") {
                data["print"] = true;
            } else if (self.afterSlicing() === "select") {
                data["select"] = true;
            }

            if (modelToRemoveAfterSlice !== undefined) {
                data["delete_model"] = modelToRemoveAfterSlice;
            }

            // Density support
            if (self.selDensity() == "Low") {
                data['profile.fill_density'] = 5;
            } else if (self.selDensity() == "Medium") {
                data['profile.fill_density'] = 10;
            } else if (self.selDensity() == "High") {
                data['profile.fill_density'] = 20;
            } else if (self.selDensity() == "High+") {
                data['profile.fill_density'] = 40;
            } else if (self.selDensity() == "Custom") {
                if (self.customDensity() > 100)
                    self.customDensity(100);
                if (self.customDensity() < 0)
                    self.customDensity(0);

                data['profile.fill_density'] = self.customDensity();
            }

            // BVC Raft Support
            if (self.platformAdhesion() == 'Raft') {
                data['profile.platform_adhesion'] = 'raft';
            } else if (self.platformAdhesion() == 'Brim') {
                data['profile.platform_adhesion'] = 'brim';
            } else {
                data['profile.platform_adhesion'] = 'none';
            }

            // BVC Support
            if (self.support() == 'Everywhere') {
                data['profile.support'] = 'everywhere';
            } else if (self.support() == 'Touching Platform') {
                data['profile.support'] = 'buildplate';
            } else {
                data['profile.support'] = 'none';
            }

            OctoPrint.files.slice( self.target , self.file(),
                data)
                .done( function ( ) {
                    self.sliceButtonControl(true);

                    // Only enables the estimation button if it's not an estimate operation
                    if (self.afterSlicing() !== "none") {
                        self.estimateButtonControl(true);
                    }
                }).error( function (  ) {
                    html = _.sprintf(gettext("Could not slice the selected file."));
                    new PNotify({title: gettext("Slicing failed"), text: html, type: "error", hide: false});

                    self.sliceButtonControl(true);
                    self.estimating(false);
                    // Only enables the estimation button if it's not an estimate operation
                    if (self.afterSlicing() !== "none") {
                        self.estimateButtonControl(true);
                    }
                });

            // Only hides the slicing dialog if it's not an estimate operation
            if (self.afterSlicing() !== "none") {
                self.slicingDialog.modal("hide");
                self.destinationFilename(undefined);
            }

            self.slicer(self.defaultSlicer);
            self.profile(self.defaultProfile);

            // Statistics logging
            self._send3DModelsInformations();
        };

        /**
         * Prints the gcode file if the estimation was already run
         */
        self.print = function() {
            if (self.destinationFilename() === undefined) return;
            self.sliceButtonControl(false);
            $.ajax({
                url: API_BASEURL + "files/" + self.target + "/" + self.destinationFilename() + ".gco",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({command: "select", print: true}),
                success: function ( response ) {

                    self.sliceButtonControl(true);
                },
                error: function ( response ) {
                    html = _.sprintf(gettext("Could not find the prepared file for print. Please consult the logs for details."));
                    new PNotify({title: gettext("Print start failed"), text: html, type: "error", hide: false});

                    self.sliceButtonControl(true);
                }
            });

            self.estimationReady(false);

            //Makes sure the options panels are all expanded after the dialog is closed
            $(".slice-option.closed").click();
            self.slicingDialog.modal("hide");

            // Statistics logging
            self._send3DModelsInformations();
        };

        /**
         * Decision function on whether to slice and print the file or just print if the estimation and respective
         * slice was already made
         */
        self.printOrSlice = function () {
            if (self.enableSliceButton()) {
                if (self.estimationReady()) {
                    self.print();
                } else {
                    self.prepareAndSlice();
                }
            }
        };

        self._sanitize = function(name) {
            return name.replace(/[^a-zA-Z0-9\-_\.\(\) ]/g, "").replace(/ /g, "_");
        };

        self.onEventSettingsUpdated = function(payload) {
            self.requestData();
        };

        self.onAllBound = function(allViewModels) {
            self.allViewModels = allViewModels;
        };

		// This function is used to force the custom density radio button to be checked when the input box is clicked
		self.setCustomDensityChecked = function () {
			self.selDensity('Custom');
		};

        /**
         * Collects and sends for statistics logging the current 3D models in the scene ready to be printed
         * @private
         */
        self._send3DModelsInformations = function () {

            // Sends the current 3D model information to the server for statistics
            var models_info = BEEwb.main.getSceneModelsInformation();
            var data = {
                models_info: models_info
            };
            $.ajax({
                url: BEE_API_BASEURL + "save_model_information",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(response) {
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        SlicingViewModel,
        ["loginStateViewModel", "printerProfilesViewModel"],
        "#slicing_configuration_dialog"
    ]);
});
