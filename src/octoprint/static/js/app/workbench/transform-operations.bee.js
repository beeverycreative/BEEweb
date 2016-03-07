// global namespace
var BEEwb = BEEwb || {};

BEEwb.transformOps = {
    selectedMode: 'translate',
    initialSize: null
}

BEEwb.transformOps.resetObjectData = function() {
    this.initialSize = null;
}

/**
 * Moves the selected model to the input text boxes axis values
 *
 */
BEEwb.transformOps.move = function() {

    if (BEEwb.main.selectedObject !== null) {
        var x = $('#x-axis').val();
        var y = $('#y-axis').val();
        var z = $('#z-axis').val();
        BEEwb.main.selectedObject.position.set( x, y, z );
        BEEwb.main.transformControls.update();
    }
}

/**
 * Scales the selected model to the input text boxes axis values
 *
 */
BEEwb.transformOps.scale = function() {

    if (BEEwb.main.selectedObject !== null) {
        var x = $('#scalex-axis').val();
        var y = $('#scaley-axis').val();
        var z = $('#scalez-axis').val();

        this.scaleBySize(x, y ,z);
        BEEwb.main.transformControls.update();
    }
}

/**
 * Rotates the selected model to the input text boxes axis values
 *
 */
BEEwb.transformOps.rotate = function() {

    if (BEEwb.main.selectedObject !== null) {
        var x = $('#rotx-axis').val();
        var y = $('#roty-axis').val();
        var z = $('#rotz-axis').val();

        this._rotateByDegrees(x, y ,z);
        BEEwb.main.transformControls.update();
    }
}

/**
 * Rotates the selected model 90 degrees to the left (counter clockwise)
 * in the selected axis in the radio input control
 *
 */
BEEwb.transformOps.rotateCCW = function() {

    if (BEEwb.main.selectedObject !== null) {
        this._rotateStep(90);

        this.updateRotationInputs();
    }
}

/**
 * Rotates the selected model 90 degrees to the right (clockwise)
 * in the selected axis in the radio input control
 *
 */
BEEwb.transformOps.rotateCW = function() {

    if (BEEwb.main.selectedObject !== null) {
        this._rotateStep(-90);

        this.updateRotationInputs();
    }
}

/**
 * Rotates the selected model 'n' degrees
 * in the selected axis in the radio input control
 *
 */
BEEwb.transformOps._rotateStep = function( degrees ) {

    var radStep = BEEwb.helpers.convertToRadians(degrees);
    var selAxis = $('input[name=rot-axis-sel]:checked').val();

    if (selAxis == 'x')
        BEEwb.main.selectedObject.rotation.set(
            BEEwb.main.selectedObject.rotation.x + radStep,
            BEEwb.main.selectedObject.rotation.y,
            BEEwb.main.selectedObject.rotation.z
        );
    else if (selAxis == 'y')
        BEEwb.main.selectedObject.rotation.set(
            BEEwb.main.selectedObject.rotation.x,
            BEEwb.main.selectedObject.rotation.y + radStep,
            BEEwb.main.selectedObject.rotation.z
        );
    else if (selAxis == 'z')
        BEEwb.main.selectedObject.rotation.set(
            BEEwb.main.selectedObject.rotation.x,
            BEEwb.main.selectedObject.rotation.y,
            BEEwb.main.selectedObject.rotation.z + radStep
        );
}

/**
 * Centers the selected model on the platform
 *
 */
BEEwb.transformOps.scaleToMax = function() {

    if (BEEwb.main.selectedObject !== null) {
        BEEwb.main.selectedObject.position.set( 0, 0, 0 );

        var hLimit = BEEwb.main.bedHeight;// z
        var wLimit = BEEwb.main.bedWidth; // x
        var dLimit = BEEwb.main.bedDepth; // y

        var xScale = wLimit / this.initialSize['x'];
        var yScale = dLimit / this.initialSize['y'];
        var zScale = hLimit / this.initialSize['z'];

        var scale = Math.min(xScale, Math.min (yScale, zScale));
        // Small adjustment to avoid false positive out of bounds message due to precision errors
        scale -= 0.01;

        BEEwb.main.selectedObject.scale.set(scale, scale ,scale);
        BEEwb.main.transformControls.update();

        this.updateScaleSizeInputs();
    }
}

/**
 * Centers the selected model on the platform
 *
 */
BEEwb.transformOps.centerModel = function() {

    if (BEEwb.main.selectedObject !== null) {
        BEEwb.main.selectedObject.position.setX( 0 );
        BEEwb.main.selectedObject.position.setY( 0 );
        this.placeOnBed();
    }
}


/**
 * Places the selected model on top of the platform
 *
 */
BEEwb.transformOps.placeOnBed = function() {

    if (BEEwb.main.selectedObject !== null) {

        // Computes the box after any transformations
        var bbox = new THREE.Box3().setFromObject( BEEwb.main.selectedObject );

        if (bbox.min.z != 0) {

            var zShift = BEEwb.main.selectedObject.position.z - bbox.min.z;

            BEEwb.main.selectedObject.position.setZ( zShift );
        }

        // Recomputes the bounding box to check for rounding errors
        bbox = new THREE.Box3().setFromObject( BEEwb.main.selectedObject );
        if (bbox.min.z < 0) {
            zShift += (-bbox.min.z + 0.0001); // Increment the shift by a small amount in case of the model being below the platform
            BEEwb.main.selectedObject.position.setZ( zShift );
        }

        BEEwb.main.transformControls.update();
        this.updatePositionInputs();
    }
}

/**
 * Resets the transformations of the selected object
 *
 */
BEEwb.transformOps.resetSelectedModel = function() {

    if (BEEwb.main.selectedObject !== null) {
        BEEwb.main.selectedObject.position.set( 0, 0, 0 );
		BEEwb.main.selectedObject.rotation.set( 0, 0, 0 );
		BEEwb.main.selectedObject.scale.set( 1, 1, 1 );

        BEEwb.main.transformControls.update();

        // Updates the size/scale/rotation input boxes
        this.updatePositionInputs();

        this.updateScaleSizeInputs();

        this.updateRotationInputs();
    }
}

/**
 * Removes a model from the scene
 *
 */
BEEwb.transformOps.removeModel = function(modelObj) {

    if (null !== modelObj) {
        BEEwb.main.scene.remove(modelObj);
        BEEwb.main.objects.remove(modelObj);
        BEEwb.main.scene.remove(BEEwb.main.transformControls);

        BEEwb.main.toggleObjectOutOfBounds(BEEwb.main.selectedObject, false);
    }
}

/**
 * Removes the selected model from the scene
 *
 */
BEEwb.transformOps.removeSelected = function() {

    if (BEEwb.main.selectedObject != null) {
        this.removeModel(BEEwb.main.selectedObject);

        BEEwb.main.selectedObject = null;
        $('.model-selection').prop('disabled', true);

        // Hides the side panel and removes selections
        BEEwb.main.removeAllSelections();
    }
}


/**
 * Activates the rotate mode for the selected object
 *
 */
BEEwb.transformOps.activateRotate = function() {

    if (BEEwb.main.transformControls != null && BEEwb.main.selectedObject != null) {

        this.selectedMode = 'rotate';
        BEEwb.main.transformControls.setMode("rotate");

        $('#btn-move').removeClass('btn-primary');
        $('#btn-scale').removeClass('btn-primary');
        $('#btn-rotate').removeClass('btn-default');
        $('#btn-rotate').addClass('btn-primary');

        $('#move-axis-form').slideUp();
        $('#scale-values-form').slideUp();
        $('#rotate-values-form').slideDown();
    }
}

/**
 * Activates the scale mode for the selected object
 *
 */
BEEwb.transformOps.activateScale = function() {

    if (BEEwb.main.transformControls != null && BEEwb.main.selectedObject != null) {

        this.selectedMode = 'scale';
        BEEwb.main.transformControls.setMode("scale");

        $('#btn-move').removeClass('btn-primary');
        $('#btn-rotate').removeClass('btn-primary');
        $('#btn-scale').removeClass('btn-default');
        $('#btn-scale').addClass('btn-primary');

        $('#move-axis-form').slideUp();
        $('#scale-values-form').slideDown();
        $('#rotate-values-form').slideUp();

        this.updateScaleSizeInputs();
    }
}

/**
 * Activates the translate (move) mode for the selected object
 *
 */
BEEwb.transformOps.activateMove = function() {

    if (BEEwb.main.transformControls != null && BEEwb.main.selectedObject != null) {

        BEEwb.main.transformControls.setMode("translate");
        this.selectedMode = 'translate';

        $('#btn-scale').removeClass('btn-primary');
        $('#btn-rotate').removeClass('btn-primary');
        $('#btn-move').removeClass('btn-default');
        $('#btn-move').addClass('btn-primary');

        $('#move-axis-form').slideDown();
        $('#scale-values-form').slideUp();
        $('#rotate-values-form').slideUp();
    }
}

/**
 * Updates the selected object position input boxes
 *
 */
BEEwb.transformOps.updatePositionInputs = function() {

    if (BEEwb.main.selectedObject != null) {
        $('#x-axis').val(BEEwb.main.selectedObject.position.x.toFixed(1));
        $('#y-axis').val(BEEwb.main.selectedObject.position.y.toFixed(1));
        $('#z-axis').val(BEEwb.main.selectedObject.position.z.toFixed(1));

        // Checks if the selected object is out of bounds
        BEEwb.main.isSelectedObjectOutOfBounds();
    }
}

/**
 * Updates the selected object scale/size input boxes
 *
 */
BEEwb.transformOps.updateScaleSizeInputs = function() {

    if (BEEwb.main.selectedObject != null) {
        if (this.initialSize == null) {
            this.initialSize = BEEwb.helpers.objectSize(BEEwb.main.selectedObject.geometry);
        }

        var newX = this.initialSize['x'] * BEEwb.main.selectedObject.scale.x;
        var newY = this.initialSize['y'] * BEEwb.main.selectedObject.scale.y;
        var newZ = this.initialSize['z'] * BEEwb.main.selectedObject.scale.z;

        $('#scalex-axis').val(newX.toFixed(2));
        $('#scaley-axis').val(newY.toFixed(2));
        $('#scalez-axis').val(newZ.toFixed(2));

        // Checks if the selected object is out of bounds
        BEEwb.main.isSelectedObjectOutOfBounds();
    }
}

/**
 * Updates the selected object rotation angles input boxes
 *
 */
BEEwb.transformOps.updateRotationInputs = function() {

    if (BEEwb.main.selectedObject != null) {

        var newX = BEEwb.helpers.convertToDegrees(BEEwb.main.selectedObject.rotation.x);
        var newY = BEEwb.helpers.convertToDegrees(BEEwb.main.selectedObject.rotation.y);
        var newZ = BEEwb.helpers.convertToDegrees(BEEwb.main.selectedObject.rotation.z);

        $('#rotx-axis').val(newX.toFixed(2));
        $('#roty-axis').val(newY.toFixed(2));
        $('#rotz-axis').val(newZ.toFixed(2));

        // Checks if the selected object is out of bounds
        BEEwb.main.isSelectedObjectOutOfBounds();
    }
}

/**
 * Scales the selected object converting size passed in the parameters to the appropriate scale
 *
 */
BEEwb.transformOps.scaleBySize = function(x, y, z) {

    if (BEEwb.main.selectedObject != null) {
        var xScale = x / this.initialSize['x'];
        var yScale = y / this.initialSize['y'];
        var zScale = z / this.initialSize['z'];

        BEEwb.main.selectedObject.scale.set( xScale, yScale, zScale );
        BEEwb.main.transformControls.update();
    }
}

/**
 * Rotates the selected object converting size passed in the parameters to the appropriate scale
 *
 */
BEEwb.transformOps._rotateByDegrees = function(x, y, z) {

    if (BEEwb.main.selectedObject != null) {
        var xRotation = BEEwb.helpers.convertToRadians(x);
        var yRotation = BEEwb.helpers.convertToRadians(y);
        var zRotation = BEEwb.helpers.convertToRadians(z);

        BEEwb.main.selectedObject.rotation.set( xRotation, yRotation, zRotation );
    }
}


/**
 * Sets the initial size for the transform operations
 *
 */
BEEwb.transformOps.setInitialSize = function() {

    if (BEEwb.main.selectedObject != null) {
        this.initialSize = BEEwb.helpers.objectSize(BEEwb.main.selectedObject.geometry);
    }
}
