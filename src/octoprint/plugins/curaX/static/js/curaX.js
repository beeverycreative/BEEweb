$(function() {
    function curaXViewModel(parameters) {
        var self = this;

        var currentProfileData = null;
        var currentMaterialSelected = null;
        var currentBrandSelected = null;

        self.selNozzle = undefined;

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

        self.brands = new ItemListHelper(
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




         self.removeMaterial = function(data) {

             console.log(data);

            if (!data.resource) {
                return;
            }

            self.profiles.removeItem(function(item) {
                return (item.key == data.key);
            });

            $.ajax({
                url: API_BASEURL + "slicing/curaX/deleteMaterial/" + data["key"] ,
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


        self.getNozzle = function(){
             $.ajax({
                 url: API_BASEURL + "maintenance/get_nozzles_and_filament",
                 type: "GET",
                 dataType: "json",
                 success: function (data) {
                      selNozzle = data.nozzle;
                 }
             });
        };


        self.editProfile = function (data) {
            // $('#edit_content').empty();
            // $('#edit_content').append('<div class="panel_collapse panel-default"><a class="" href="#"><span class="lbl">Profile:</span>'+
            //              '<select  id="quality_droplist"></select>'+
            //              '<span class="sign" data-bind="click: function() {$root.removeQualityInProfile();}"><i class="icon-trash"></i></span>'+
            //              '<span class="sign" data-bind="click: function() {$root.NewQuality();}"><i class="icon-plus-sign-alt"></i></span>'+
            //              '<span class="sign" data-bind="click: function() {$root.NewQualityCopy();}"><i class="icon-copy"></i></span>'+
            //              '<span class="sign" data-bind="click: function() {$root.NewQualityName();}"><i class="icon-edit"></i></span></a></div>');

            $.ajax({
                url: API_BASEURL + "slicing/curaX/getProfileQuality/" + data["key"] ,
                type: "GET",
                dataType: "json",
                success:function (current) {
                    $('#quality_droplist').empty();
                    $.each(current,function (_value) {
                        $('#quality_droplist').append('<option>' + _value + '</option>');
                    });

                    self.appendToEditMenu();
                    self.getProfileToEdit(data)
                }
            });
            // console.log($('#quality_droplist :selected').text());
            //
            // self.appendToEditMenu();
            // self.getProfileToEdit(data)

        };


        // self.editProfile = function(data) {
        //    console.log(selNozzle);
        //      $.ajax({
        //         url: API_BASEURL + "slicing/curaX/getProfileQuality/" + data["key"] ,
        //         type: "GET",
        //         dataType: "json",
        //         success:function (current) {
        //             console.log(current);
        //             $('#comboQuality').empty();
        //             for ( var options in current ) {
        //               var newOption = $('<option>' + options + '</option>');
        //               $('#comboQuality').append(newOption);
        //             }
        //             self.getProfileToEdit(data)
        //         }
        //     });
        // };

         self._lookInData = function (name,data) {
            var _state = false;
             _.each(data, function(value,item) {
                 if (name == item)
                     _state = true;
            });
            return _state;
        };

        self.getProfileToEdit = function(data){
            // self.appendToEditMenu();

            // $("#settings_plugin_curaX_teste_profile").modal("show");
            // var quality = $('#quality_droplist').text();
            //
            // console.log(quality)
            //   $("#settings_plugin_curaX_teste_profile").modal("show");
            // console.log($('#quality_droplist').find('option:selected').text());
             // $("#settings_plugin_curaX_teste_profile").modal("show");

              var quality = $('#quality_droplist :selected').text();

            console.log(quality)

            currentProfileData = data;

            $('#profileDisplay').text(data["key"]);
            // + self.selColor() + "/" + self.selQuality() + "/" + self.selNozzle(),
            $.ajax({
                url: API_BASEURL + "slicing/curaX/getSingleProfile/" + data["key"] + "/" + quality + "/" + selNozzle,
                type: "GET",
                dataType: "json",
                success:function(data){

                    // console.log(data);
                    // var _input = $('#edit_content div').find('input,select');
                    // console.log(_input);

                    // if(!($('#settings_plugin_curaX_edit_profile').is(':visible')))
                    //     $("#settings_plugin_curaX_edit_profile").modal("show");

                    // console.log(_input);
                    // _.each(_input,function (info) {
                    //     console.log('#' + info.id);
                    //     if(self._lookInData(info.id,data)) {
                    //         console.log('#' + info.id);
                    //         if (info.type == 'checkbox') {
                    //             $('#' + info.id).prop('checked', data[info.id].default_value);
                    //         } else{
                    //             console.log('#' + info.id,data[info.id].default_value)
                    //             $('#layer_height0').val("60");
                    //         }
                    //     }
                    // });
                    var $current = $('#edit_content div').find('input');
                    console.log(data)
                    for(var i = 0 ; i < $current.length; i++){
                        var fieldID = $current[i].id;
                         if(self._lookInData(fieldID.replace('ed',''),data))
                             $('#'+ fieldID).val(data[fieldID.replace('ed','')].default_value);
                    }
                    //
                    if(!($('#settings_plugin_curaX_edit_profile').is(':visible')))
                        $("#settings_plugin_curaX_edit_profile").modal("show");
                }
            });

             // $("#settings_plugin_curaX_edit_profile").modal("show");

        };

        $('#comboQuality').on('change', function (e) {
            self.getProfileToEdit(currentProfileData);
        });


         self.corfirmProfileEdition = function () {  // call de API function in slicing.py

            var form={};
            var quality = $('#comboQuality').find('option:selected').text();

            // var $current = $('#edit_panel div').find('input');
            //
            // for(var i = 0 ; i < $current.length; i++){
            //     var fieldID = $current[i].id;
            //     if($current[i].type == 'number')
            //         form[fieldID.replace('edit','')] = $('#'+ fieldID).val()
            // }
            console.log(form);

             var _input = $('#edit_content').find('input , select');
                _.each(_input,function (info) {
                      if(info.type == 'checkbox')
                          form['profile.' + info.id] = $('#' + info.id).is(':checked');
                      else
                         form['profile.'+ info.id] = $('#'+ info.id).val();
                });

             console.log(form);
            // $.ajax({
            //     url: API_BASEURL + "slicing/curaX/confirmEdition/" + currentProfileData["key"] + "/" + quality ,
            //     type: "PUT",                //
            //     dataType: "json",           // data type
            //     data: JSON.stringify(form), // send the data
            //     contentType: "application/json; charset=UTF-8",
            //     success: function() {
            //         self.requestData();
            //     }
            // });
            //  $("#settings_plugin_curaX_edit_profile").modal("hide");
            // self.requestData();
        };
        /*********************************************************************************************************/

        self.findMaterialOnArray = function (data,material) {

             if(!material)
                return false;

             if(data.length == 0)
                 return true;

             for (index = 0; index < data.length; ++index) {
                 if(data[index].key == material)
                        return false;
             }
             return true;
        };


        self.requestData = function() {
            $.ajax({
                url: API_BASEURL + "slicing/curaX/materials",
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            });
        };

        self.fromResponse = function(data) {

            if(self.profiles.allItems.length == 0){
                $('#profile_message').text("No material selected");
                $('#_profiles_tab_indicator_').text("No material selected");
                $('#_profiles_tab_infomation_indicator_').text("No material selected");
            }

            var brand  = [];
            var material = [];

            _.each(_.keys(data), function(key) {

                     material.push({
                         key: key,
                         name: ko.observable(data[key].displayName),
                         description: ko.observable(data[key].description),
                         isdefault: ko.observable(data[key].default),
                         resource: ko.observable(data[key].resource),
                         brand: ko.observable(data[key].brand)
                     });

                     if (self.findMaterialOnArray(brand, data[key].brand)) {
                         brand.push({
                             key: data[key].brand
                         });
                     }
            });
            // console.log(brand);
            // console.log(material);

            self.materials.updateItems(material);
            self.brands.updateItems(brand);


        };

        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.requestData();
        };

/******************************************************************************************
 * Get Profiles from material
 * @param none
 * @return none
 ******************************************************************************************/
        self.getProfilesInheritsMaterials = function(data, parent){
            $('#profiles_acordion').empty();


            currentMaterialSelected = data;
            currentBrandSelected = parent;

            $.ajax({
                url: API_BASEURL + "slicing/curaX/InheritsMaterials/" + data["key"] ,
                type: "GET",
                dataType: "json",
                success:function (current) {
                    var profile = [];
                    _.each(_.keys(current), function(key) {
                         profile.push({
                             key: key,
                             resource: ko.observable(current[key].resource),
                             isdefault: ko.observable(current[key].default)

                         });
                    });
                    self.profiles.updateItems(profile);

                    if(self.profiles.allItems.length == 0)
                        $('#profile_message').text("No profiles for this material!!");
                    else
                        $('#profile_message').text("");
                }
            });

            $.ajax({
                url: API_BASEURL + "slicing/curaX/getMaterial/" + data["key"],
                type: "GET",
                dataType: "json",
                success:function(data){
                    $('#_information_display_name').text(data['display_name'].default_value);
                    $('#_information_default_material_print_temperature').text(data['default_material_print_temperature'].default_value + " ºC");
                    $('#_information_brand').text(data['brand'].default_value);
                    $('#_information_speed_infill').text(data['speed_infill'].default_value + " mm/s");
                    $('#_information_material').text(data['material_type'].default_value);
                    $('#_information_speed_wall_0').text(data['speed_wall_0'].default_value + " mm/s");
                    $('#_information_filament_cost').text(data['filament_cost'].default_value);
                    $('#_information_speed_wall_x').text(data['speed_wall_x'].default_value + " mm/s");
                    $('#_information_filament_weight').text(data['filament_weight'].default_value + " g");
                }
            });


            $('#_profiles_tab_indicator_').text(data['key']);
            $('#_profiles_tab_infomation_indicator_').text(data['key']);

            $("#material_tab").collapse("hide");
            $("#profiles_tab").collapse("show");

            var $col = $("#material_tab").find('.collapse');
            for( var i = 0; i < $col.length ; i++){
                if ($('#' + $col[i].id).hasClass('in')) {
                    $('#' + $col[i].id).collapse("hide");
                }
            }

            var $sub = $('.sub_panel_accordion .sign');
            for( var i = 0; i < $sub.length;i++){
                self.SwitchSecondPanelIcons($($sub[i]).attr('data-target'));
            }


        };
/******************************************************************************************
 * Save new Material in the files
 * @param none
 * @return none
 ******************************************************************************************/
        self.saveMaterial =function() {

            var form = {};
            var $current = $('#settings_plugin_curaX_new_material div').find('input');
            for (var i = 0; i < $current.length; i++) {
                var fieldID = $current[i].id;
                if ($current[i].type == 'number' || $current[i].type == 'text')
                    form[fieldID] = $('#' + fieldID).val()
            }


            if ($('#material_modal_label').text() == "NEW MATERIAL") {
                $.ajax({
                    url: API_BASEURL + "slicing/curaX/saveMaterial",
                    type: "PUT",
                    dataType: "json",
                    data: JSON.stringify(form),
                    contentType: "application/json; charset=UTF-8",
                });
            }else{
                $.ajax({
                    url: API_BASEURL + "slicing/curaX/saveMaterial/" + $('#material_modal_edition').text(),
                    type: "PUT",
                    dataType: "json",
                    data: JSON.stringify(form),
                    contentType: "application/json; charset=UTF-8",
                });
            }

            $("#settings_plugin_curaX_new_material").modal("hide");

            $("#information_panel").collapse("show");

            $("#print_settings_panel").collapse("hide");

            self.requestData();
        };
/******************************************************************************************
 * Get material data["key"] data from files
 * @param data [material do edit]
 * @return none
 ******************************************************************************************/
        self.editMaterial = function (data) {

             $('#material_modal_label').text("EDIT MATERIAL:");
             $('#material_modal_edition').text(data["key"]);
             $.ajax({
                url: API_BASEURL + "slicing/curaX/getMaterial/" + data["key"],
                type: "GET",
                dataType: "json",
                success:function(data){
                    var $current = $('#settings_plugin_curaX_new_material div').find('input');
                    for(var i = 0 ; i < $current.length; i++){
                        var fieldID = $current[i].id;
                         if($current[i].type == 'number' || $current[i].type == 'text')
                             $('#'+ fieldID).val(data[fieldID].default_value);
                    }
                }
            });
            $("#settings_plugin_curaX_new_material").modal("show");
        };
/******************************************************************************************
 * Get data from rawprofile and added to new profile form
 * @param none
 * @return none
 ******************************************************************************************/
        self.createNewProfile = function(){
            if(currentMaterialSelected == null){
                $("#settings_plugin_curaX_new_profile_message").modal('show');
            }else{
                $("#_profile_name_new_profile_").val('Custom');
                $("#_profile_Quality_new_profile_").val('Normal');
                $.ajax({
                    url: API_BASEURL + "slicing/curaX/getRawProfile/" + currentMaterialSelected["key"],
                    type: "GET",
                    dataType: "json",
                    success:function(data){
                        var $current = $('#newProfile_panel div').find('input');
                        for(var i = 0 ; i < $current.length; i++){
                            var fieldID = $current[i].id;
                             if($current[i].type == 'number' || $current[i].type == 'text')
                                $('#'+ fieldID).val(data[fieldID.replace('new','')].default_value);
                        }
                    }
                });
                $("#settings_plugin_curaX_new_profile").modal("show");
            }
        };
/******************************************************************************************
 * Get data from rawmterial and added to new profile form
 * @param none
 * @return none
 ******************************************************************************************/
        self.createNewMaterial = function(){
                $("#material_modal_label").text('NEW MATERIAL');
                // $("#_profile_Quality_new_profile_").val('Normal');
                $.ajax({
                    url: API_BASEURL + "slicing/curaX/getRawMaterial" ,
                    type: "GET",
                    dataType: "json",
                    success:function(data){
                        var $current = $('#newMaterial_panel div').find('input');
                        for(var i = 0 ; i < $current.length; i++){
                            var fieldID = $current[i].id;
                             if($current[i].type == 'number' || $current[i].type == 'text')
                                $('#'+ fieldID).val(data[fieldID].default_value);
                        }
                    }
                });
                $("#settings_plugin_curaX_new_material").modal("show");
        };
/******************************************************************************************
 * Save data from created profile
 * @param none
 * @return none
 ******************************************************************************************/
         self.saveRawProfile = function () {  // call de API function in slicing.py

            var form={};
            var quality = $('#comboQuality').find('option:selected').text();

            var $current = $('#newProfile_panel div').find('input');

            for(var i = 0 ; i < $current.length; i++){
                var fieldID = $current[i].id;
                if($current[i].type == 'number')
                    form[fieldID.replace('new','')] = $('#'+ fieldID).val();
            }
            form['inherits'] = currentMaterialSelected["key"];
            form['quality'] = $('#_profile_Quality_new_profile_').val();
            form['name'] = $('#_profile_name_new_profile_').val();

            $.ajax({
                url: API_BASEURL + "slicing/curaX/saveRawProfile" ,
                type: "PUT",                //
                dataType: "json",           // data type
                data: JSON.stringify(form), // send the data
                contentType: "application/json; charset=UTF-8",
                success: function() {
                    // self.requestData();
                }
            });
             $("#settings_plugin_curaX_new_profile").modal("hide");
             self.getProfilesInheritsMaterials(currentMaterialSelected , currentBrandSelected);
            // self.requestData();
        };
/******************************************************************************************
 * remove profile
 * @param none
 * @return none
 ******************************************************************************************/
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
                self.getProfilesInheritsMaterials(currentMaterialSelected,currentProfileData)
        };

/******************************************************************************************
 * remove profile
 * @param none
 * @return none
 ******************************************************************************************/
        self.removeQualityInProfile = function() {
            $profile_to_edit = $("#profileDisplay").text();
            $quality_to_edit = $("#comboQuality").val();
                $.ajax({
                    url:  API_BASEURL + "slicing/curaX/delete_quality/" + $quality_to_edit + "/" + $profile_to_edit,
                    type: "DELETE",
                    success: function() {
                        self.requestData();
                        self.slicingViewModel.requestData();
                    }
                });
                $("#settings_plugin_curaX_edit_profile").modal("hide");
                self.getProfilesInheritsMaterials(currentMaterialSelected,currentProfileData)
        };

/******************************************************************************************
 * change profile quality name
 * @param none
 * @return none
 ******************************************************************************************/
        self.changeQualityProfileName = function() {
            $profile_to_edit  = $("#profileDisplay").text();
            $quality_to_edit  = $("#comboQuality").val();
            $new_quality_name = $("#_new_quality_name").val();

            console.log($profile_to_edit);
            console.log($quality_to_edit);
            console.log("Ok");
                // if (!data.resource) {
                //     return;
                // }
                // self.profiles.removeItem(function(item) {
                //     return (item.key == data.key);
                // });
             if ($('#profileQualityHeader').text() == "CHANGE PROFILE NAME") {
                 $.ajax({
                     url: API_BASEURL + "slicing/curaX/change_quality_profile/" + $profile_to_edit + "/" + $quality_to_edit + "/" + $new_quality_name,
                     type: "POST",
                     success: function () {
                         self.requestData();
                         self.slicingViewModel.requestData();
                     }
                 });
             }

             if ($('#profileQualityHeader').text() == "PROFILE COPY") {
                 $.ajax({
                     url: API_BASEURL + "slicing/curaX/copy_quality_profile/" + $profile_to_edit + "/" + $quality_to_edit + "/" + $new_quality_name,
                     type: "POST",
                     success: function () {
                         self.requestData();
                         self.slicingViewModel.requestData();
                     }
                 });
             }

             if ($('#profileQualityHeader').text() == "NEW PROFILE") {
                 $.ajax({
                     url: API_BASEURL + "slicing/curaX/new_quality/" + $profile_to_edit + "/" + $new_quality_name,
                     type: "POST",
                     success: function () {
                         self.requestData();
                         self.slicingViewModel.requestData();
                     }
                 });
             }

                $("#settings_plugin_curaX_change_name").modal("hide");
                $("#settings_plugin_curaX_edit_profile").modal("hide");
                self.getProfilesInheritsMaterials(currentMaterialSelected,currentBrandSelected);


                // self.getProfilesInheritsMaterials(currentMaterialSelected,currentProfileData)
        };


/******************************************************************************************
 * call name change form
 * @param none
 * @return none
 ******************************************************************************************/
         self.NewQualityName = function() {
            $("#profileQualityHeader").text("CHANGE PROFILE NAME");
            $("#settings_plugin_curaX_change_name").modal("show");
         };

/******************************************************************************************
 * call name change form
 * @param none
 * @return none
 ******************************************************************************************/
         self.NewQualityCopy = function() {
            $("#profileQualityHeader").text("PROFILE COPY");
            $("#settings_plugin_curaX_change_name").modal("show");
         };

 /******************************************************************************************
 * call name change form
 * @param none
 * @return none
 ******************************************************************************************/
         self.NewQuality = function() {
             $("#profileQualityHeader").text("NEW PROFILE");
             $("#settings_plugin_curaX_change_name").modal("show");

         };

/******************************************************************************************
 * switch panel icons
 * @param none
 * @return none
 ******************************************************************************************/
         self.SwitchIcons = function(child){

               var $this = $(child).attr('href');
               console.log($this);
               if($($this).hasClass('collapse in')){
                   $(child).parent().find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
               }else{
                   $(child).parent().find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
               }
         };
/******************************************************************************************
 * switch panel icons
 * @param none
 * @return none
 ******************************************************************************************/
         self.SwitchSecondPanelIcons = function(child){

               var $this = $(child).attr('data-target');
               console.log($this);
               if($($this).hasClass('collapse in')){
                   $(child).parent().find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
               }else{
                   $(child).parent().find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
               }
         };

/******************************************************************************************
 * switch panel icons
 * @param none
 * @return none
 ******************************************************************************************/
           $(document).on("click",".panel_input", function() {
               var $this = $(this).children('.sign').attr('href');
               if($($this).hasClass('collapse in')){
                   $(this).find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
               }else{
                   $(this).find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
               }
           });

           $(document).on("click",".panel_accordion .lbl", function(){
              self.SwitchIcons(this);
           });

           $(document).on("click",".panel_accordion .sign", function(){
              self.SwitchIcons(this);
           });

           $(document).on("click",".sub_panel_accordion .lbl_two", function(){
               console.log(this)
              self.SwitchSecondPanelIcons(this);
           });

           $(document).on("click",".sub_panel_accordion .sign", function(){
              self.SwitchSecondPanelIcons(this);
           });


           self.appendToEditMenu = function () {
               $('#edit_content').empty();

               $.ajax({
                   url: API_BASEURL + "slicing/curaX/getOptions",
                   type: "GET",
                   dataType: "json",
                   success: function (data) {
                       $.each(data.options, function (_value, _options) {
                           $('#edit_content').append('<div class="panel_collapse collapsed"><a class="" href="#">' +
                               '<span data-toggle="collapse"  data-parent="#accordion" href="#' + _options.id + '" class="lbl">' + _options.id + '</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#edit' + _options.id + '" class="sign"><i class="icon-chevron-down"></i></span></a>' +
                               '<div id="' + _options.id + '" class="panel-collapse collapse"></div> </div>');

                           $.each(_options.list, function (_value, _list) {

                               if (_list.type == 'integer') {
                                   $('#' + _options.id).append('<div class="form-group"><a><span  class="sign">' + _list.label + '</span>' +
                                       '<input class="inpt" id = "ed' + _list.id+'" type="number"  step="0.01"></a></div>');

                                   $('#ed' + _list.id).val(_list.default_value);
                               } else if (_list.type == 'boolean') {
                                   $('#' + _options.id).append('<div class="form-group"><a><span  class="sign">' + _list.label + '</span>' +
                                       '<input class="inpt" id = "ed' + _list.id + '" type="checkbox" ></a></div>');

                                   $('#ed' + _list.id).attr('checked', _list.default_value);

                               }else if (_list.type == 'droplist') {
                                   $('#' + _options.id).append('<div class="form-group"><a><span  class="sign">' + _list.label + '</span>' +
                                       '<select id = "ed' + _list.id + '" ></select></a></div>');

                                   if(_list.options.length > 0) {
                                       _.each(_list.options, function (din_options) {
                                           $('#ed' + _list.id).append($('<option>', {
                                               value: din_options,
                                               text: din_options
                                           }));
                                       });
                                       $('#ed' +_list.id).val(_list.default_value);
                                   }
                               }
                           });
                       });
                   }
               });
           };




    }

    $(document).ready(function(){
              $.ajax({
                 url: API_BASEURL + "maintenance/get_nozzles_and_filament",
                 type: "GET",
                 dataType: "json",
                 success: function (data) {
                      self.selNozzle = data.nozzle;
                 }
             });
            // $.ajax({
            //     url: API_BASEURL + "slicing/curaX/getOptions",
            //     type: "GET",
            //     dataType: "json",
            //     success: function (data) {
            //         console.log(data);
            //         $.each(data.options,function (_value,_options) {
            //             console.log(_options.id)
            //             $('#newProfile_panel').append('<div class="panel_collapse collapsed"><a class="" href="#">' +
            //                    '<span data-toggle="collapse"  data-parent="#accordion" href="#edit'+ _options.id +'" class="lbl">' + _options.id +'</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#edit'+ _options.id +'" class="sign"><i class="icon-chevron-down"></i></span></a>'+
            //                    '<div id="edit'+_options.id+'" class="panel-collapse collapse"></div> </div>');
            //             $('#edit_panel').append('<div class="panel_collapse collapsed"><a class="" href="#">' +
            //                    '<span data-toggle="collapse"  data-parent="#accordion" href="#new'+ _options.id +'" class="lbl">' + _options.id +'</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#new'+ _options.id +'" class="sign"><i class="icon-chevron-down"></i></span></a>' +
            //                    '<div id="new'+_options.id+'" class="panel-collapse collapse"></div> </div>');
            //
            //
            //             $.each(_options.list, function (_value,_list) {
            //
            //                 if(_list.type == 'integer'){
            //                     $('#edit'+ _options.id ).append('<div class="form-group"><a class="" href="#"><span  class="sign">'+_list.label +'</span>' +
            //                         '<input class="inpt" id = "edit' + _list.id + '" type="number"  step="0.01"></a></div>');
            //
            //                 }else if(_list.type == 'boolean'){
            //                    $('#edit'+ _options.id ).append('<div class="form-group"><a class="" href="#"><span  class="sign">'+_list.label +'</span>' +
            //                          '<input class="inpt" id = "edit' + _list.id + '" type="checkbox" ></a></div>');
            //
            //                    $('#edit' + _list.id).attr('checked',_list.default_value);
            //                 }else if(_list.type == 'droplist'){
            //
            //                 }
            //
            //             })
            //         });
            //         for (var i = 0; i < data.options.length ; i++) {
            //
            //             var counter = data.options[i];
            //
            //             var $input_edit = $('<div class="panel_collapse collapsed"><a class="" href="#"><span class="signa"><i class="'+counter.icon+'"></i></span>' +
            //                  '<span data-toggle="collapse"  data-parent="#accordion" href="#edit'+ counter.id +'" class="lbl">' + counter.id +'</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#edit'+ counter.id +'" class="sign"><i class="icon-chevron-down"></i></span></a>');
            //             var $input_new  = $('<div class="panel_collapse collapsed"><a class="" href="#"><span class="signa"><i class="'+counter.icon+'"></i></span>' +
            //                  '<span data-toggle="collapse"  data-parent="#accordion" href="#new'+ counter.id +'" class="lbl">' + counter.id +'</span>' + '<span data-toggle="collapse"  data-parent="#accordion" href="#new'+ counter.id +'" class="sign"><i class="icon-chevron-down"></i></span></a>');
            //
            //             $('#newProfile_panel').append($input_new);
            //             $('#edit_panel').append($input_edit);
            //
            //             var $input_edit= $('<div id="edit'+counter.id+'" class="panel-collapse collapse"></div> </div>');
            //             var $input_new = $('<div id="new'+counter.id+'" class="panel-collapse collapse"></div> </div>');
            //
            //             $('#newProfile_panel').append($input_new);
            //             $('#edit_panel').append($input_edit);
            //
            //             for(var j = 0; j < counter.list.length ; j++) {
            //                 var idcounter = counter.list[j];
            //                 var $input = $('<div class="form-group"><a class="" href="#"><span  class="sign">'+counter.list[j].DisplayName +'</span>' +
            //                      '<input class="inpt" id = "edit' + idcounter.id + '" type="number"  step="0.01"></a></div>');
            //                 $('#edit'+ counter.id ).append($input);
            //             }
            //
            //             for(var j = 0; j < counter.list.length ; j++) {
            //                 var idcounter = counter.list[j];
            //                 var $input = $('<div class="form-group"><a class="" href="#"><span  class="sign">'+counter.list[j].DisplayName +'</span>' +
            //                      '<input class="inpt" id = "new' + idcounter.id + '" type="number"  step="0.01"></a></div>');
            //                 $('#new'+ counter.id ).append($input);
            //             }
            //         }
            //     },
            // });

            var ids = $('.panel_input').map(function () {
                return this;
            }).get();

            for (var i = 0; i < ids.length; i++) {
                var $txt = $(ids[i]).children('.sign').attr('href');
                if($($txt).hasClass('collapse in')){
                     $(ids[i]).find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
                }else{
                     $(ids[i]).find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
                }
            }

            var ids = $('.panel_accordion').map(function () {
                return this;
            }).get();

            for( var i = 0; i < ids.length; i++){
                var $txt = $(ids[i]).children('.sign').attr('href');
                if($($txt).hasClass('collapse in')){
                     $(ids[i]).find('i:first').removeClass('icon-chevron-down').addClass('icon-chevron-up');
                }else{
                     $(ids[i]).find('i:first').removeClass('icon-chevron-up').addClass('icon-chevron-down');
                }
            }

        });
    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        curaXViewModel,
        ["loginStateViewModel", "settingsViewModel", "slicingViewModel"],
        "#settings_plugin_curaX"
    ]);
});
