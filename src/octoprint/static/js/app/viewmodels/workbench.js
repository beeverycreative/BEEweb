$(function () {
	function WorkbenchViewModel(parameters) {
		var self = this;

        ko.bindingHandlers.numeric = {
            init: function (element, valueAccessor) {
                $(element).on("keydown", function (event) {
                    // Allow: backspace, delete, tab, escape, and enter
                    if (event.keyCode == 46 || event.keyCode == 8 || event.keyCode == 9 || event.keyCode == 27 || event.keyCode == 13 ||
                        // Allow: Ctrl+A
                        (event.keyCode == 65 && event.ctrlKey === true) ||
                        // Allow: . ,
                        (event.keyCode == 188 || event.keyCode == 190 || event.keyCode == 110) ||
                        // Allow: home, end, left, right
                        (event.keyCode >= 35 && event.keyCode <= 39)) {
                        // let it happen, don't do anything
                        return;
                    }
                    else {
                        // Ensure that it is a number and stop the keypress
                        if (event.shiftKey || (event.keyCode < 48 || event.keyCode > 57) && (event.keyCode < 96 || event.keyCode > 105)) {
                            event.preventDefault();
                        }
                    }
                });
            }
        };

		self.files = parameters[0].listHelper;
		self.loginState = parameters[1];
		self.connection = parameters[2];
        self.slicing = parameters[3];
        self.state = parameters[4];

        // Save scene dialog attributes
        self.sceneName = ko.observable();
        self.savingScene = ko.observable(false);

        self.saveSceneDialog = $("#save_scene_dialog");
        self.saveSceneDialog.on("shown", function() {
            $("input", self.saveSceneDialog).focus();
        });
        $("form", self.saveSceneDialog).on("submit", function(e) {
            e.preventDefault();
            if (self.enableSaveScene()) {
                self.saveScene();
            }
        });

        // User feedback dialog attributes
        self.printSuccess = ko.observable(true);
        self.sendingFeedback = ko.observable(false);
        self.printObservations = ko.observable("");
        self.printClassification = ko.observable(5).extend({min: 1, max: 10});

        self.userFeedback = $("#user_feedback_dialog");
        self.userFeedback.on("shown", function() {
            $("input", self.userFeedback).focus();
        });
        $("form", self.userFeedback).on("submit", function(e) {
            e.preventDefault();
            self.sendUserFeedback();
        });

		//append file list with newly updated stl file.
		self.onEventUpload = function (file) {

			if (file.file.substr(file.file.length - 3).toLowerCase() === "stl") {

				BEEwb.main.loadModel(file.file, false, false);
			}
		};

		self.updateFileList = function () {
			self.files.updateItems(_.filter(self.files.allItems, self.files.supportedFilters["model"]));
		};

		self.enableSaveScene = function () {
            if (self.sceneName()) {
                return true;
            }

            return false;
        };

		self.saveScene = function() {
		    self.savingScene(true);

		    // Adds the extension .stl to the filename if it does not contain
		    if (!self.sceneName().endsWith('.stl')) {
		        self.sceneName(self.sceneName() + '.stl');
		    }

            // NOTE: setTimeout is a workaround to allow the saveScene function to run
            // separately and release this "thread" so the button is disabled
            setTimeout(function() {
                var saveCall = BEEwb.main.saveScene(self.sceneName());
                // waits for the save operation
                saveCall.done( function () {
                    self.saveSceneDialog.modal("hide");

                    self.savingScene(false);
                });
            }, 10);

		};

		self.showSaveScene = function () {
		    self.sceneName(BEEwb.helpers.generateSceneName());
		    self.saveSceneDialog.modal("show");
        };

        // User feedback dialog methods
		self.showUserFeedbackDialog = function () {
		    self.userFeedback.modal("show");
        };

        self.sendUserFeedback = function () {
            self.sendingFeedback(true);

            // validates print classification input
            if (self.printClassification() > 10) {
                self.printClassification(10);
            }
            if (self.printClassification() < 1) {
                self.printClassification(1);
            }

            var feedback = {
                print_success: self.printSuccess(),
                print_rating: self.printClassification(),
                observations: self.printObservations()
            };

            $.ajax({
                url: BEE_API_BASEURL + "save_user_feedback",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(feedback),
                success: function(response) {
                    if (!response.success) {
                        var html = _.sprintf(gettext("An error occurred while saving your feedback. Please consult the logs."));
                        new PNotify({title: gettext("Save feedback failed"), text: html, type: "error", hide: false});
                    }
                    self.sendingFeedback(false);
                    self.userFeedback.modal("hide");
                }, error: function (response) {
                    var html = _.sprintf(gettext("An error occurred while saving your feedback. Please consult the logs."));
                    new PNotify({title: gettext("Save feedback failed"), text: html, type: "error", hide: false});

                    self.sendingFeedback(false);
                    self.userFeedback.modal("hide");
                }
            });
        };

        self.closeUserFeedbackDialog = function () {

            // Sends an empty user feedback just to signal the end of statistics collection for the finished print
            $.ajax({
                url: BEE_API_BASEURL + "no_user_feedback",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function(response) {
                }
            });

            self.userFeedback.modal("hide");
        };

	}

	// This is how our plugin registers itself with the application, by adding some configuration information to
	// the global variable ADDITIONAL_VIEWMODELS
	ADDITIONAL_VIEWMODELS.push([
			// This is the constructor to call for instantiating the plugin
			WorkbenchViewModel,

			// This is a list of dependencies to inject into the plugin, the order which you request here is the order
			// in which the dependencies will be injected into your view model upon instantiation via the parameters
			// argument
			["filesViewModel", "loginStateViewModel", "connectionViewModel", "slicingViewModel", "printerStateViewModel","remotePrintersViewModel"],

			// Finally, this is the list of all elements we want this view model to be bound to.
			[("#workbench")]
		]);
});
