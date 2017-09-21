$(function() {
    function AppearanceViewModel(parameters) {
        var self = this;

        self.name = parameters[0].appearance_name;
        self.color = parameters[0].appearance_color;
        self.colorTransparent = parameters[0].appearance_colorTransparent;
        self.printerProfiles = parameters[1];
        self.connection = parameters[2];

        self.brand = ko.pureComputed(function() {
            if (self.name())
                return self.name();
            else
                return gettext("BEESOFT");
        });

        self.fullbrand = ko.pureComputed(function() {
            if (self.name())
                return gettext("BEESOFT") + ": " + self.name();
            else
                return gettext("BEESOFT");
        });

        self.title = ko.pureComputed(function() {
            if (self.name())
                return "[" + gettext("BEESOFT") + "]" + self.name();
            else
                return gettext("BEESOFT");
        });
    }

    OCTOPRINT_VIEWMODELS.push([
        AppearanceViewModel,
        ["settingsViewModel", "printerProfilesViewModel", "connectionViewModel"],
        "head"
    ]);
});
