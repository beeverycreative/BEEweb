$(function() {
    function NavigationViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.appearance = parameters[1];
        self.settings = parameters[2];
        self.usersettings = parameters[3];
        self.system = parameters[4];

        self.appearanceClasses = ko.pureComputed(function() {
            var classes = self.appearance.color();
            if (self.appearance.colorTransparent()) {
                classes += " transparent";
            }
            return classes;
        });

        self.triggerAction = function(action) {
            var callback = function() {
                $.ajax({
                    url: API_BASEURL + "system",
                    type: "POST",
                    dataType: "json",
                    data: "action=" + action.action,
                    success: function() {
                        new PNotify({title: "Success", text: _.sprintf(gettext("The command \"%(command)s\" executed successfully"), {command: action.name}), type: "success"});
                    },
                    error: function(jqXHR, textStatus, errorThrown) {
                        if (!action.hasOwnProperty("ignore") || !action.ignore) {
                            var error = "<p>" + _.sprintf(gettext("The command \"%(command)s\" could not be executed."), {command: action.name}) + "</p>";
                            error += pnotifyAdditionalInfo("<pre>" + jqXHR.responseText + "</pre>");
                            new PNotify({title: gettext("Error"), text: error, type: "error", hide: false});
                        }
                    }
                })
            };
            if (action.confirm) {
                showConfirmationDialog(action.confirm, function (e) {
                    callback();
                });
            } else {
                callback();
            }
        }

        self.aboutDialog = $('#aboutbee_dialog');
        self.currentFirmware = ko.observable('Undefined');

        self.showAboutBee = function() {

            // show settings, ensure centered position
            self.aboutDialog.modal({
                minHeight: function() { return Math.max($.fn.modal.defaults.maxHeight() - 500, 250); }
            }).css({
                width: 'auto',
                'margin-left': function() { return -($(this).width() /2); }
            });

            $.ajax({
                url: BEE_API_BASEURL + "firmware/current/version",
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function(data) {
                    self.currentFirmware(data.version);
                }
            });

            return false;
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        NavigationViewModel,
        ["loginStateViewModel", "appearanceViewModel", "settingsViewModel", "userSettingsViewModel", "systemViewModel"],
        ["#navbar", "#aboutbee_dialog"]
    ]);
});
