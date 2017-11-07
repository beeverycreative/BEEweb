$(function() {
    function RemotePrintersViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.printerProfiles = parameters[1];
        //self.printerState = parameters[2];

        self.loadingPrinters = ko.observable(true);
        self.remotePrintersReady = ko.observable(false);

        self.file = ko.observable(undefined);
        self.target = undefined;
        self.path = undefined;
        self.data = undefined;

        self.destinationFilename = ko.observable();

        self.remotePrintButtonControl = ko.observable(true); // Controls the button enabled state

        self.selectedRows = [];

        self.show = function(target, file, force, workbench, path) {

            self.getRemotePrinters();

            $("#remote_printers_dialog").modal("show");

            self.file = file;

        };

        /**
         * Function that is run during the cancel/close of the dialog
         */
        self.closeRemote = function() {

            self.loadingPrinters(false);
            self.remotePrintersReady(false);
        };


        self.remotePrintClick = function () {
            console.log("Remote Print...");

            self.selectedRows = [];
            $("#remote_printers_table tr.remote-table-row-selected").each(function(){
                self.selectedRows.push(this.id);
            });

            if (self.selectedRows.length > 0) {
                var data = {
                "command": "createOrders"
            };
            data['Info'] = [self.selectedRows, self.file];

            $.ajax({
                url: API_BASEURL + "remote/createPrintingOrders",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify(data),
                success: function(data) {


                },
                error: function() {

                }
            });
            }
        };

        self.remorePrintButtonTooltip = ko.pureComputed(function() {
            if (!self.enableRemotePrintButton()) {
                    return gettext("Cannot slice, not all parameters specified");
            } else {
                return gettext("Start the remote print process");
            }
        });

        self.enableRemotePrintButton = ko.pureComputed(function() {
            return true;
                //&& self.profile() != undefined
                //&&( !(self.printerState.isPrinting() || self.printerState.isPaused()) || !self.slicerSameDevice());
        });


        /**
         * Connects to remote server and retrieves connected printer information
         */
        self.getRemotePrinters = function() {

            self.loadingPrinters(true);
            self.remotePrintersReady(false);

            var table = $("#remote_printers_table");
            table.empty();


            $.ajax({
                url: API_BASEURL + "remote/getRemotePrinters",
                type: "POST",
                dataType: "json",
                success: function(data) {

                    $.each(data.response, function (i, item)
                    {

                        var tableRow = $('<tr class="remote-table-row" id="' + item.id + '"/>');

                        tableRow.click(function(){
                           $(this).toggleClass('remote-table-row-selected');
                           //var value=$(this).find('td:first').html();
                           //alert(value);
                        });

                        //Left row space
                        tableRow.append('<td width="5%"></td>');

                        //Printer logo
                        var imageCol = $('<td colspan="2"/>');
                        var img = $('<img src="' + item.imgPath + '">');
                        imageCol.append(img);
                        tableRow.append(imageCol);

                        //Printer progress
                        var progressCol = $('<td colspan="4"/>');
                        var progressDiv = $('<div class="progress remote-print-progress" style="text-align: center"/>');
                        var barDiv =$('<div/>');
                        barDiv.addClass("bar");

                        if(item.state=="READY"){
                            barDiv.addClass("ready-remote-bar");
                            barDiv.append('READY');
                        } else if (item.state=="Printing") {
                            barDiv.addClass("printing-remote-bar");
                            barDiv.append('Printing: ' + item.Progress);
                        } else if (item.state=="Heating") {
                            barDiv.addClass("heating-remote-bar");
                            barDiv.append('Heating: ' + item.Progress);
                        }

                        barDiv.css('width',item.Progress);
                        progressDiv.append(barDiv);
                        progressCol.append(progressDiv);
                        tableRow.append(progressCol);

                        //Material
                        var materialCol = $('<td colspan="1" style="text-align: center"/>');
                        materialCol.append(item.Material);
                        tableRow.append(materialCol);

                        //Color
                        var colorCol = $('<td colspan="1"/>');
                        var colorDiv = $('<div/>');
                        colorDiv.addClass('progress');
                        colorDiv.addClass('remote-color');
                        colorDiv.css("text-align","center");
                        var rgbDiv = $('<div/>');
                        rgbDiv.addClass("bar");
                        //rgbDiv.css("width","100%")
                        rgbDiv.attr('style','width: 100%;background-color: ' + item.rgb + ' !important;')

                        colorDiv.append(rgbDiv);
                        colorCol.append(colorDiv)
                        tableRow.append(colorCol);
                        /*<td colspan="1">
                            <div class="progress remote-color" style="text-align: center">
                                <div class="bar" style="width: 100%;background-color: #0aaaf1 !important;"></div>
                            </div>
                        </td>*/

                        //Right row space
                        tableRow.append('<td width="5%"></td>');

                        table.append(tableRow);

                        self.loadingPrinters(false);
                        self.remotePrintersReady(true);
                    });
                },
                error: function() {
                    console.log("Error GetRemotePrinters\n");

                    self.loadingPrinters(false);
                    self.remotePrintersReady(false);
                }
            });

        };
    }

    OCTOPRINT_VIEWMODELS.push([
        RemotePrintersViewModel,
        ["loginStateViewModel", "printerProfilesViewModel", /*"printerStateViewModel"*/],
        "#remote_printers_dialog"
    ]);
});
