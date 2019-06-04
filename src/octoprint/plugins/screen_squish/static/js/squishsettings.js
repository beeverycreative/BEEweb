$(function() {
    function ScreenSquishViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];

        self.override_version = ko.observable(false);
        self.show_override = ko.observable(true);

        self.onStartupComplete = function() {
            /*new PNotify({
                title: gettext("ScreenSquish Auto Off"),
                text: gettext("ScreenSquish automatically turned itself off due to possible version incompatibility. It may need an update."),
            }); */
        }

        self.onSettingsBeforeSave = function() {
            version = '';
            if (self.override_version()) {
                version = $('span.version').text();
            }
            self.settings.settings.plugins.ScreenSquish.octoprint_max_version(version);
            new PNotify({
                title: gettext("ScreenSquish force enabled"),
                text: gettext("This won't take effect until OctoPrint has been restarted.")
            });
        }
    }

    OCTOPRINT_VIEWMODELS.push([
        ScreenSquishViewModel,
        ["settingsViewModel"],
        ["#screen_squish_settings"]
    ]);
});
