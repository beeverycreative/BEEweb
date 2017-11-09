$(function() {
    function curaXViewModel(parameters) {
        var self = this;
         var currentProfileData = null;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];
        self.slicingViewModel = parameters[2];

        self.fileName = ko.observable();

        self.placeholderName = ko.observable();
        self.placeholderDisplayName = ko.observable();
        self.placeholderDescription = ko.observable();

        self.profileName = ko.observable();
        self.profileDisplayName = ko.observable();
        self.profileDescription = ko.observable();
        self.profileAllowOverwrite = ko.observable(true);

        self.uploadElement = $("#settings-curaX-import");
        self.uploadButton = $("#settings-curaX-import-start");
        self.editButton = $("#settings-curaX-edit-start");

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
                },
                "brand": function(a, b) {
                    // sorts ascending
                    var aBrand = a.brand();
                    if (aBrand === undefined) {
                        aBrand = "";
                    }
                    var bBrand = b.brand();
                    if (bBrand === undefined) {
                        bBrand = "";
                    }

                    if (aName.toLocaleLowerCase() < bBrand.toLocaleLowerCase()) return -1;
                    if (aName.toLocaleLowerCase() > bBrand.toLocaleLowerCase()) return 1;
                    return 0;
                },

            },
            {},
            "id",
            [],
            [],
            1000
        );

        self.materials = new ItemListHelper(
            "plugin_cura_profiles",
            {
                "description": function(a, b) {
                    // sorts ascending
                    var aDescription = a.description();
                    if (aDescription === undefined) {
                        aDescription = "";
                    }
                    var bDescription = b.description();
                    if (bDescription === undefined) {
                        bDescription = "";
                    }

                    if (aName.toLocaleLowerCase() < bBrand.toLocaleLowerCase()) return -1;
                    if (aName.toLocaleLowerCase() > bBrand.toLocaleLowerCase()) return 1;
                    return 0;
                },
            },
            {},
            "id",
            [],
            [],
            20
        );

        self._sanitize = function(name) {
            return name.replace(/[^a-zA-Z0-9\-_\.\(\) ]/g, "").replace(/ /g, "_");
        };

        self.uploadElement.fileupload({
            dataType: "json",
            maxNumberOfFiles: 1,
            autoUpload: false,
            add: function(e, data) {
                if (data.files.length == 0) {
                    return false;
                }

                self.fileName(data.files[0].name);

                var name = self.fileName().substr(0, self.fileName().lastIndexOf("."));
                self.placeholderName(self._sanitize(name).toLowerCase());
                self.placeholderDisplayName(name);
                self.placeholderDescription("Imported from " + self.fileName() + " on " + formatDate(new Date().getTime() / 1000));

                self.uploadButton.unbind("click");
                self.uploadButton.on("click", function() {
                    var form = {
                        allowOverwrite: self.profileAllowOverwrite()
                    };

                    if (self.profileName() !== undefined) {
                        form["name"] = self.profileName();
                    }
                    if (self.profileDisplayName() !== undefined) {
                        form["displayName"] = self.profileDisplayName();
                    }
                    if (self.profileDescription() !== undefined) {
                        form["description"] = self.profileDescription();
                    }

                    data.formData = form;
                    data.submit();
                });
            },
            done: function(e, data) {
                self.fileName(undefined);
                self.placeholderName(undefined);
                self.placeholderDisplayName(undefined);
                self.placeholderDescription(undefined);
                self.profileName(undefined);
                self.profileDisplayName(undefined);
                self.profileDescription(undefined);
                self.profileAllowOverwrite(true);

                $("#settings_plugin_curaX_import").modal("hide");
                self.requestData();
                self.slicingViewModel.requestData();
            }
        });

        self.removeProfile = function(data) {
            if (!data.resource) {
                return;
            }

            self.profiles.removeItem(function(item) {
                return (item.key == data.key);
            });

            $.ajax({
                url: data.resource(),
                type: "DELETE",
                success: function() {
                    self.requestData();
                    self.slicingViewModel.requestData();
                }
            });

            self.requestData();
        };

        self.makeProfileDefault = function(data) {
            if (!data.resource) {
                return;
            }

            _.each(self.profiles.items(), function(item) {
                item.isdefault(false);
            });
            var item = self.profiles.getItem(function(item) {
                return item.key == data.key;
            });
            if (item !== undefined) {
                item.isdefault(true);
            }

            $.ajax({
                url: data.resource(),
                type: "PATCH",
                dataType: "json",
                data: JSON.stringify({default: true}),
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    self.requestData();
                }
            });
        };

        self.showImportProfileDialog = function() {
            $("#settings_plugin_curaX_import").modal("show");
        };


        /******************************************* Code where **************************************************/
        self.duplicateProfileDefault = function(data) {
            if (!data.resource) {
                return;
            }
             $.ajax({
                url: data.resource(),
                type: "POST",
                success: function() {
                    self.requestData();
                    self.slicingViewModel.requestData();
                }
            });
            self.requestData();
        };

        self.editProfile = function(data) {
             $.ajax({
                url: API_BASEURL + "slicing/curaX/getProfileQuality/" + data["key"] ,
                type: "GET",
                dataType: "json",
                success:function (current) {
                    console.log(current)
                    $('#comboQuality').empty();
                    for ( var options in current ) {
                      var newOption = $('<option>' + options + '</option>');
                      $('#comboQuality').append(newOption);
                    }
                    self.getProfileToEdit(data)
                }
            });
        };

        self.getProfileToEdit = function(data){
            var quality = $('#comboQuality').find('option:selected').text();

            console.log($('.collapse'));

            currentProfileData = data;

            $('#profileDisplay').text(data["key"]);

            $.ajax({
                url: API_BASEURL + "slicing/curaX/getSingleProfile/" + data["key"] + "/" + quality ,
                type: "GET",
                dataType: "json",
                success:function(data){
                    var $current = $('#accordion_teste div').find('input');
                    console.log(data)
                    console.log($current)
                    for(var i = 0 ; i < $current.length; i++){
                        var fieldID = $current[i].id;
                         if($current[i].type == 'number')
                             $('#'+ fieldID).val(data[fieldID].default_value);
                    }

                    if(!($('#settings_plugin_curaX_edit_profile').is(':visible')))
                        $("#settings_plugin_curaX_edit_profile").modal("show");
                }
            });
        };

        $('#comboQuality').on('change', function (e) {
            self.getProfileToEdit(currentProfileData);
        });


         self.corfirmProfileEdition = function () {  // call de API function in slicing.py

            var form={};
            var quality = $('#comboQuality').find('option:selected').text();

            var $current = $('#accordion_teste div').find('input');

            for(var i = 0 ; i < $current.length; i++){
                var fieldID = $current[i].id;
                if($current[i].type == 'number')
                    // form.push(fieldID+ ":" + $('#'+ fieldID).val() );
                    form[fieldID] = $('#'+ fieldID).val()

            }
            $.ajax({
                url: API_BASEURL + "slicing/curaX/confirmEdition/" + currentProfileData["key"] + "/" + quality ,
                type: "PUT",                //
                dataType: "json",           // data type
                data: JSON.stringify(form), // send the data
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    self.requestData();
                }
            });
             $("#settings_plugin_curaX_edit_profile").modal("hide");
            self.requestData();
        };
        /*********************************************************************************************************/

        self.findMaterialOnArray = function (data,material) {

             if(data.length == 0)
                 return true;

             for (index = 0; index < data.length; ++index) {
                 if(data[index].description == material)
                        return false;
             }
             return true;
        };


        self.requestData = function() {
            $.ajax({
                url: API_BASEURL + "slicing/curaX/profiles",
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            });
        };

        self.fromResponse = function(data) {

            var dataFilter = self.getRadiosData();

            // $("#brands_tab").collapse("hide");
            $("#brandDisplay").text(dataFilter[0]);

            var profiles  = [];
            var material = [];

            _.each(_.keys(data), function(key) {
                  if (data[key].brand == dataFilter[0]) {
                     profiles.push({
                         key: key,
                         name: ko.observable(data[key].displayName),
                         description: ko.observable(data[key].description),
                         isdefault: ko.observable(data[key].default),
                         resource: ko.observable(data[key].resource),
                         brand: ko.observable(data[key].brand)
                     });

                     if (self.findMaterialOnArray(material, data[key].description)) {
                         material.push({
                             key: key,
                             description: data[key].description
                         });
                     }
                 }

            });
            self.profiles.updateItems(profiles);
            self.materials.updateItems(material);

        };

        self.getRadiosData = function () {
            var brandName;
            var radiosBrand =  document.getElementsByName("brand");

            for(var i = 0, length = radiosBrand.length ; i < length ; i++) {
                if (radiosBrand[i].checked) {
                        brandName = radiosBrand[i].value;
                }
            }


            return [brandName];
        };

        self.onInputChange = function (tag) {
            self.requestData();
            // $("#brands_tab").collapse();
        }


        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.requestData();
        };
    }

    $(document).on("click","#settings_plugin_curaX_edit_profile a > span.sign ", function(){

          if($(this).find('i:first').attr('class') == 'icon-chevron-down')
              $(this).find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
          else
              $(this).find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
    });

    $(document).on("click","#settings_plugin_curaX_brands_interface a > span.sign ", function(){
          if($(this).find('i:first').attr('class') == 'icon-chevron-down')
              $(this).find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
          else if($(this).find('i:first').attr('class') == 'icon-chevron-up')
              $(this).find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
    });

    $(document).ready(function(){

            $.ajax({
                url: API_BASEURL + "slicing/curaX/getOptions",
                type: "GET",
                dataType: "json",
                success: function (data) {
                    for (var i = 0; i < data.options.length ; i++) {
                        var counter = data.options[i];
                        var $input = $('<div class="panel_collapse collapsed"><a class="" href="#"><span class="signa"><i class="'+counter.icon+'"></i></span>' +
                             '<span class="lbl">' + counter.id +'</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#'+ counter.id +'" class="sign"><i class="icon-chevron-down"></i></span></a>');
                        $('#accordion_teste').append($input);

                        var $input = $('<div id="'+counter.id+'" class="panel-collapse collapse"></div> </div>');
                        $('#accordion_teste').append($input);

                        for(var j = 0; j < counter.list.length ; j++) {
                            var idcounter = counter.list[j];
                            var $input = $('<div class="form-group"><a class="" href="#"><span  class="sign">'+counter.list[j].DisplayName +'</span>' +
                                 '<input class="inpt" id = "' + idcounter.id + '" type="number"  step="0.01"></a></div>');
                            $('#'+ counter.id ).append($input);
                        }
                    }
                },
            });

        });
    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        curaXViewModel,
        ["loginStateViewModel", "settingsViewModel", "slicingViewModel"],
        "#settings_plugin_curaX"
    ]);
});
