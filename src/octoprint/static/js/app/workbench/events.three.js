// global namespace
var BEEwb = BEEwb || {};

BEEwb.events = {};

/**
 * OnWindowResize event function
 */
BEEwb.events.onWindowResize = function() {
    // Updates container bounds
    var container = document.getElementById( 'stl_container' );
    var bondingOffset = container.getBoundingClientRect();
    BEEwb.main.containerWidthOffset = bondingOffset.left;
    BEEwb.main.containerHeightOffset = bondingOffset.top;

    BEEwb.main.camera.aspect = BEEwb.main.container.clientWidth / BEEwb.main.container.clientHeight;
    BEEwb.main.camera.updateProjectionMatrix();

    BEEwb.main.renderer.setSize( window.innerWidth, window.innerHeight / 1.5 );

    BEEwb.main.render();
};

/**
 * OnMouseDown event function
 */
BEEwb.events.onMouseDown = function( e ) {

    // Records the first click position
    BEEwb.main.mouseVector.x = 2 * ( (e.clientX - BEEwb.main.containerWidthOffset) /
        BEEwb.main.renderer.domElement.clientWidth) - 1;

    BEEwb.main.mouseVector.y = 1 - 2 * ( (e.clientY - BEEwb.main.containerHeightOffset - BEEwb.main.topPanelVerticalOffset) /
        BEEwb.main.renderer.domElement.clientHeight );

    BEEwb.main.mouseVector.z = 0.5;
};

/**
 * OnMouseUp event function
 */
BEEwb.events.onMouseUp = function( e ) {

    var prevMouseVector = BEEwb.main.mouseVector.clone();

    BEEwb.main.mouseVector.x = 2 * ( (e.clientX - BEEwb.main.containerWidthOffset) /
        BEEwb.main.renderer.domElement.clientWidth) - 1;
    BEEwb.main.mouseVector.y = 1 - 2 * ( (e.clientY - BEEwb.main.containerHeightOffset - BEEwb.main.topPanelVerticalOffset) /
        BEEwb.main.renderer.domElement.clientHeight );
    BEEwb.main.mouseVector.z = 0.5;

    BEEwb.main.raycaster.setFromCamera( BEEwb.main.mouseVector.clone(), BEEwb.main.camera );

    var intersects = BEEwb.main.raycaster.intersectObjects( BEEwb.main.objects.children );

    // Selects the first found intersection
    if (intersects.length > 0) {

        var intersection = intersects[ 0 ];
        var model = intersection.object;

        if (BEEwb.main.selectedObject !== model) {
            //BEEwb.main.removeAllSelections();
            BEEwb.main.selectModel(model);
        }

    } else if (prevMouseVector.x == BEEwb.main.mouseVector.x
        && prevMouseVector.y == BEEwb.main.mouseVector.y
        && prevMouseVector.z == BEEwb.main.mouseVector.z) {
        // It means the scene wasn't dragged and so we should remove all selections

        BEEwb.main.removeAllSelections();
    }

    // Updates the size/scale/rotation input boxes
    if (BEEwb.transformOps.selectedMode == 'translate') {
        BEEwb.transformOps.updatePositionInputs();
    }

    if (BEEwb.transformOps.selectedMode == 'scale') {
        if ($('#scaleby-per').is(':checked')) {
            BEEwb.transformOps.updateScaleSizeInputsByPercentage();
        } else {
            BEEwb.transformOps.updateScaleSizeInputs();
        }
    }

    if (BEEwb.transformOps.selectedMode == 'rotate') {
        BEEwb.transformOps.updateRotationInputs();
    }
};

/**
 * OnKeyDown event function
 */
BEEwb.events.keyMap = {};
BEEwb.events.onKeyDown = function( event ) {
    BEEwb.events.keyMap[event.keyCode] = (event.type == 'keydown');

    if (BEEwb.events.keyMap[18] == true) { // Alt pressed
        switch ( event.keyCode ) {

            case 77: // M - Move
                BEEwb.transformOps.activateMove();
                break;

            case 82: // R - Rotate
                BEEwb.transformOps.activateRotate();
                break;

            case 83: // S - Scale
                BEEwb.transformOps.activateScale();
                break;

            case 67: // C - Clone model
                BEEwb.transformOps.cloneSelected();
                break;
        }
    } else {
        if (event.keyCode == 46){
        	// checks if any of the axis input boxes has focus and prevents the deletiong of the model in that case
			var inputBoxActive = false;
			var axisInputBoxes = $('.axis-input-box');
			axisInputBoxes.each(function () {
				if ($(this).is(':focus')) {
					inputBoxActive = true;
					return;
				}
			});

            // Delete model
            if (!inputBoxActive) {
            	BEEwb.transformOps.removeSelected();
            }
        }
    }
};

/**
 * OnKeyUp event function
 *
 * @param event
 */
BEEwb.events.onKeyUp = function( event ) {
    BEEwb.events.keyMap[event.keyCode] = (event.type == 'keydown');
};
