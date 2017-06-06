$(function () {
	function WorkbenchViewModel(parameters) {
		var self = this;

		self.files = parameters[0].listHelper;
		self.loginState = parameters[1];
		self.connection = parameters[2];
        self.slicing = parameters[3];
        self.state = parameters[4];

		//append file list with newly updated stl file.
		self.onEventUpload = function (file) {

			if (file.file.substr(file.file.length - 3).toLowerCase() == "stl") {

				BEEwb.main.loadModel(file.file, false, false);
			}
		};

		self.updateFileList = function () {
			self.files.updateItems(_.filter(self.files.allItems, self.files.supportedFilters["model"]));
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
