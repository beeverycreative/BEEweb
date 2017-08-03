$(function () {
	function WorkbenchViewModel(parameters) {
		var self = this;

		self.files = parameters[0].listHelper;
		self.loginState = parameters[1];
		self.connection = parameters[2];
        self.slicing = parameters[3];
        self.state = parameters[4];

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

	}

	// This is how our plugin registers itself with the application, by adding some configuration information to
	// the global variable ADDITIONAL_VIEWMODELS
	ADDITIONAL_VIEWMODELS.push([
			// This is the constructor to call for instantiating the plugin
			WorkbenchViewModel,

			// This is a list of dependencies to inject into the plugin, the order which you request here is the order
			// in which the dependencies will be injected into your view model upon instantiation via the parameters
			// argument
			["filesViewModel", "loginStateViewModel", "connectionViewModel", "slicingViewModel", "printerStateViewModel"],

			// Finally, this is the list of all elements we want this view model to be bound to.
			[("#workbench")]
		]);
});
