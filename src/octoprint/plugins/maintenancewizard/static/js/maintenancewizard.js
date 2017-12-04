$(function() {
    function MaintenanceWizardExtruderCalibrationViewModel(parameters) {
        var self = this;

        self.maintenanceViewModel = parameters[0];
		self.wizard = parameters[1];

		// EVENT LISTENERS
        self.onStartup = function() {
        };

        self.onWizardShow = function() {
        	// Makes sure the wizard finish button is hidden
			self.wizard.wizardDialog.find(".button-finish").hide();
        };

        self.onWizardFinish = function() {
        };

		// VIEW MODEL FUNCTIONS
        self.showCalibrateExtruder = function () {
			self.maintenanceViewModel.showMaintenanceCalibrateExtruder();

			self.closeDialog();
		};

        self.closeDialog = function() {
            self.wizard.wizardDialog.modal("hide");
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        MaintenanceWizardExtruderCalibrationViewModel,
        ["maintenanceViewModel", "wizardViewModel"],
        "#wizard_plugin_maintenancewizard_extrudercalibration"
    ]);
});
