// global namespace
var BEEwb = BEEwb || {};

BEEwb.helpers = {};

/**
 * Auxiliary function to generate the STL file and Scene name from the current canvas scene.
 *
 * param objects: Array of objects from a Threejs scene
 *
 * Return dictionary with 'stl' -> File and 'sceneName' -> File name
 */
BEEwb.helpers.generateSTLFromScene = function( objects ) {

    var exporter = new THREE.STLBinaryExporter();

    var stlData = exporter.parse( objects );

    // plain text ascii
    //var blob = new Blob([stlData], {type: 'text/plain'});
    // binary
    return new Blob([stlData], {type: 'application/octet-binary'});
};

/**
 * Generates the workbench scene name based on current date/time
 *
 * Return string with the generated name
 */
BEEwb.helpers.generateSceneName = function( ) {
    var now = new Date();
    var prefix = 'bee';
    var workbenchTempFileMarker = '__tmp-scn';

    if (BEEwb.main.lastLoadedModel != null) {
        prefix = BEEwb.main.lastLoadedModel;
    }
    var sceneName = prefix + '_' + now.getDate() + (now.getMonth()+1) + now.getFullYear()
    + '_' + now.getHours() + '-' + now.getMinutes() + '-' + now.getSeconds() + workbenchTempFileMarker + '.stl';

    return sceneName;
};

/**
 * Calculates the size of an object
 *
 * param geometry: THREEJS.Object3D object
 *
 * Returns dictionary with size { 'x': ..., 'y': ..., 'z': ...}
 */
BEEwb.helpers.objectSize = function( object ) {

    if ( object == null) {
        return { 'x': 0, 'y': 0, 'z': 0};
    }

    var bbox = new THREE.Box3().setFromObject( object );

    var xSize = 0;
    var ySize = 0;
    var zSize = 0;

    // X size
    if (bbox.max.x < 0) {
        xSize -= bbox.max.x;
    } else {
        xSize += bbox.max.x;
    }

    if (bbox.min.x < 0) {
        xSize -= bbox.min.x
    } else {
        xSize += bbox.min.x;
    }

    // Y size
    if (bbox.max.y < 0) {
        ySize -= bbox.max.y;
    } else {
        ySize += bbox.max.y;
    }

    if (bbox.min.y < 0) {
        ySize -= bbox.min.y
    } else {
        ySize += bbox.min.y;
    }

    // Z size
    if (bbox.max.z < 0) {
        zSize -= bbox.max.z;
    } else {
        zSize += bbox.max.z;
    }

    if (bbox.min.z < 0) {
        zSize -= bbox.min.z
    } else {
        zSize += bbox.min.z;
    }

    return { 'x': xSize, 'y': ySize, 'z': zSize};
};

/**
 * Checks if the object is out of bounds
 *
 * param obj: THREEJS.Object3D object
 * param bboxSize: array { x, y, z } with bounding box size
 *
 * Returns true if the object is out of bounds
 */
BEEwb.helpers.objectOutOfBounds = function( obj, bboxSize ) {
    if ( obj == null) {
        return false;
    }

    // Computes the box after any transformations
    var bbox = new THREE.Box3().setFromObject( obj );
    if ( bbox.max.x > (bboxSize[0] / 2) || bbox.max.y > (bboxSize[1] / 2) || bbox.max.z > bboxSize[2]) {
        return true;
    }

    if ( bbox.min.x < -(bboxSize[0] / 2) || bbox.min.y < -(bboxSize[1] / 2) || bbox.min.z < 0) {
        return true;
    }

    return false;
};

/**
 * Calculates if the total bounding box created by all the objects in the print bed
 * are over a pre defined adhesion threshold, after which the adhesion print options
 * cannot be used.
 *
 * @returns {boolean}
 */
BEEwb.helpers.isSceneOverAdhesionThreshold = function( ) {
    var sceneBoundingBox = BEEwb.main.getSceneBoundingBox();
    var printingSpace = [BEEwb.main.bedWidth, BEEwb.main.bedDepth, BEEwb.main.bedHeight];
    var ADHESION_THRESHOLD = 5;

    if ( sceneBoundingBox["max_x"] > ((printingSpace[0] / 2) - ADHESION_THRESHOLD)
    	|| sceneBoundingBox["min_x"] < -((printingSpace[0] / 2) - ADHESION_THRESHOLD)) {
        return true;
    }

    if ( sceneBoundingBox["max_y"] > ((printingSpace[1] / 2) - ADHESION_THRESHOLD)
    	|| sceneBoundingBox["min_y"] < -((printingSpace[1] / 2) - ADHESION_THRESHOLD)) {
        return true;
    }

    return false;
};

/**
 * Converts radians to degrees
 *
 * param radians: Angle in radians value
 *
 * Returns value in degrees
 */
BEEwb.helpers.convertToDegrees = function( radians ) {
    if (radians != null) {
        return radians * (180/3.1416);
    } else {
        return 0;
    }
};

/**
 * Converts degress to radians
 *
 * param degrees: Angle in degrees value
 *
 * Returns value in degrees
 */
BEEwb.helpers.convertToRadians = function( degrees ) {
    if (degrees != null) {
        return degrees * (3.1416/180);
    } else {
        return 0;
    }
};


/**
 * Calculates any possible object shift to avoid overlapping of models in the scene
 *
 * param geometry: THREEJS.BufferGeometry geometry new object to be loaded
 *
 * Returns float value with amount to shift the new object
 */
BEEwb.helpers.calculateObjectShift = function( geometry ) {

    geometry.computeBoundingBox();
    var shift = 0;
    if (BEEwb.main.objects.children.length > 0) {
        var lastObj = BEEwb.main.objects.children[BEEwb.main.objects.children.length-1];

        if (lastObj.geometry != null) {
            var objBox = new THREE.Box3().setFromObject( lastObj );

            shift = objBox.max.x;
        }

        // Final shift calculation with the "left" side of the new object
        shift = shift - geometry.boundingBox.min.x + 1; // +1 for a small padding between the objects
    }

    return shift;
};

/**
 * Calculates and centers an object if its bounding box center does not match the scene center
 *
 * @param geometry
 */
BEEwb.helpers.centerModelBasedOnBoundingBox = function(geometry) {

    geometry.computeBoundingBox();
    var bbox = geometry.boundingBox;

    var xShift = 0;
    var yShift = 0;
    var zShift = 0;

    var centerX = 0.5 * ( bbox.max.x - bbox.min.x );
    var centerY = 0.5 * ( bbox.max.y - bbox.min.y );
    var centerZ = 0.5 * ( bbox.max.z - bbox.min.z );

    // Checks if the object is out of center in any axis
    //Check x axis
    if ( bbox.min.x >= 0) {
        xShift = bbox.min.x + centerX;
    } else if ( bbox.max.x <= 0) {
        xShift = bbox.max.x - centerX;
    } else{
        xShift = bbox.max.x - centerX;
    }

    //Check y axis
    if ( bbox.min.y >= 0) {
        yShift = bbox.min.y + centerY;
    } else if ( bbox.max.y <= 0) {
        yShift = bbox.max.y - centerY;
    } else{
        yShift = bbox.max.y - centerY;
    }

    //Check z axis
    if ( bbox.min.z >= 0) {
        zShift = bbox.min.z + centerZ;
    } else if ( bbox.max.z <= 0 ) {
        zShift = bbox.max.z - centerZ;
    } else{
        zShift = bbox.max.z - centerZ;
    }

    // Applies the transformation matrix for any necessary shift in position
    geometry.applyMatrix( new THREE.Matrix4().makeTranslation( -xShift, -yShift, -zShift ) );
};


function saveCookie(name, value, days) {
    var expires;
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toGMTString();
    }
    else {
        expires = "";
    }
    document.cookie = name + "=" + value + expires + "; path=/";
}

function readCookie(name) {

	var nameEQ = name + "=";
	var ca = document.cookie.split(';');

	for(var i=0;i < ca.length;i++) {
		var cookie = ca[i];
		while (cookie.charAt(0) === ' ')
		    cookie = cookie.substring(1, cookie.length);
		if (cookie.indexOf(nameEQ) === 0)
		    return cookie.substring(nameEQ.length, cookie.length);
	}
	return null;
}


//#### additional functions for splitting the filaments list into two sub-lists:
//#### begin section...
function f_on_change_radiobtn(on_startup, select_id){
	//INPUT:
	//			on_startup is a flag true/false that indicates if we need to initialize the vars;
	//			select_id is a string with the object id: "select_supply" or "select_supply_mtc".
	var select_obj = document.getElementById(select_id);
	var op = select_obj.options;

	var offset;
	if (select_id==="select_supply"){
		offset=0;
	}
	else if (select_id==="select_supply_mtc"){
		offset=1;	//there is an extra item in the list on the change filaments section: "select filament type...".
	}
	
	
	if (on_startup==true){
		BEEwb.types_of_filaments=[];									//this is a list that will contain the distinction between new and old filaments, through the presence or absence of "#".
		var n_filaments_mcpp = 0;
		for (var i=0; i<op.length; i++){
			BEEwb.types_of_filaments.push(op[i].value.includes("#") || (i==0));
			if (op[i].value.includes("#")){
				n_filaments_mcpp++;
			}
		}
		BEEwb.n_filaments_mcpp = n_filaments_mcpp;
		
		BEEwb.opt_mcpp=select_obj.options[0].value;
		BEEwb.opt_beesupply=select_obj.options[BEEwb.n_filaments_mcpp-offset].value;
	}
	
	
	//#### important: ####
	// the goal is to find the elements of filaments profiles list, and show only new profiles or old profiles, accordingly to the option "mcpp (default)" or "bee_supply"
	var option = cur_filament_type(select_id);
	
	// get all options within <select id='select_supply'/'select_supply_mtc'>...</select>
	offset=0;
	
	for (var i=0; i<(op.length-offset); i++){
		//if the option mcpp is selected: display only new profiles...
		if (option==="mcpp"){
			if (BEEwb.types_of_filaments[i]==true){		//if they contained originaly the "#" symbol
				op[i+offset].hidden = false;
				if (op[i+offset].innerHTML.includes("#")){
					op[i+offset].innerHTML = op[i+offset].value.replace("#", "")
                                                               .replace("BTF ", "")
                                                               .replace("BTF+ ", "")
                                                               .replace("TPU 04 ", "TPU ");
				}
			}
			else{
				op[i+offset].hidden = true;
			}
		}
		//else [the option beesupply is selected]: display only old profiles...
		else{
			(BEEwb.types_of_filaments[i])
				? op[i+offset].hidden = true
				: op[i+offset].hidden = false;
		}
	}
	
	if (option==="mcpp"){
		select_obj.value = BEEwb.opt_mcpp;
	}
	else{
		select_obj.value = BEEwb.opt_beesupply;
	}
}


function cur_filament_type(select_id){
	var radios;
	if (select_id==="select_supply"){
		radios = document.getElementsByName('filament_type');
	}
	else if (select_id==="select_supply_mtc"){
		radios = document.getElementsByName('filament_type_mtc');
	}
	var option;
	
	for (var j=0, length=radios.length; j<length; j++) {
		if (radios[j].checked) {
			// find the checked radio
			option = radios[j].value;

			// only one radio can be logically checked, don't check the rest
			break;
		}
	}
	
	return option;
}

function save_cur_opt(select_id){
	//INPUT:
	//			select_id is a string with the object id: "select_supply" or "select_supply_mtc".
	var select_obj = document.getElementById(select_id);
	if (cur_filament_type(select_id)==="mcpp"){
		BEEwb.opt_mcpp = select_obj.value;
	}
	else{
		BEEwb.opt_beesupply = select_obj.value;
	}
}


function fix_filament_name(){
	var fil_colour = document.getElementById("filament_colour");
	fil_colour.textContent=fil_colour.textContent.replace("#", "")
                                                 .replace("BTF ", "")
                                                 .replace("BTF+ ", "")
                                                 .replace("TPU 04 ", "TPU ");
}
//####... end section.
