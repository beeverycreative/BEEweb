var SELECT_COLOR = '#ECC459';
var DEFAULT_COLOR = '#8C8C8C';
var OUT_BOUNDS_COLOR = '#BD362F';

// global namespace
var BEEwb = BEEwb || {};

/**
 * Global Variables declaration
 */
BEEwb.main = {
    transformControls: null,
    container: null,
    camera: null,
    scene: null,
    renderer: null,
    sceneControls: null,
    objects: null,
    raycaster: null,
    mouseVector: null,
    containerWidthOffset: 0,
    containerHeightOffset: 0,
    bed: 0,
    selectedObject: null,
    bedHeight: 0,
    bedWidth: 0,
    bedDepth: 0,
    savedScenesFiles: [],
    lastLoadedModel: null,
    topPanelVerticalOffset: 0,

    /**
     * Main initialization function
     */
    init: function() {

        var that = this;
        // Loads the printer profile
        $.ajax({
            url: BEE_CUSTOM_API_BASEURL + "printer",
            type: 'GET',
            success: function(data) {
                that.bedDepth = data.profile.volume.depth;
                that.bedWidth = data.profile.volume.width;
                that.bedHeight = data.profile.volume.height;
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                that._initializeGraphics();
                that.render();
                that.animate();
            }
        });
    },

    /**
     * Initialization function callback
     */
    _initializeGraphics: function() {

        if ( !Detector.webgl ) Detector.addGetWebGLMessage();

        this.container = document.getElementById( 'stl_container' );
        var bondingOffset = this.container.getBoundingClientRect();

        this.containerWidthOffset = bondingOffset.left;
        this.containerHeightOffset = bondingOffset.top;

        // renderer
        this.renderer = new THREE.WebGLRenderer({ alpha: true , antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight / 1.5);
        this.container.appendChild( this.renderer.domElement );

        this.camera = new THREE.PerspectiveCamera(
            53, this.renderer.domElement.clientWidth / this.renderer.domElement.clientHeight, 1, 3000
        );

        this.resetCamera();

        this.scene = new THREE.Scene();
        //this.scene.add( new THREE.GridHelper( 90, 30 ) );

        var light1 = new THREE.PointLight( 0xffffff, 0.5 );
        light1.position.set( 200, 200, 200 );

        var light2 = new THREE.PointLight( 0xffffff, 0.5 );
        light2.position.set( -200, 200, 200 );

        var light3 = new THREE.PointLight( 0xffffff, 0.5 );
        light3.position.set( 200, -200, 200 );

        var light4 = new THREE.PointLight( 0xffffff, 0.5 );
        light4.position.set( -200, -200, 200 );

        this.scene.add( light1 );
        this.scene.add( light2 );
        this.scene.add( light3 );
        this.scene.add( light4 );

        this.objects = new THREE.Object3D();
        this.scene.add(this.objects);

        // Loads the model
        var lastModel = document.cookie.replace(/(?:(?:^|.*;\s*)lastModel\s*\=\s*([^;]*).*$)|^.*$/, "$1");

        if (!lastModel) {
            lastModel = 'BEE.stl';
            this.loadModel(lastModel, true, true);
        } else {
            var that = this;
            $.ajax({
                url:'./downloads/files/local/' + lastModel,
                type:'HEAD',
                error: function() {
                    console.log('Last printed model does not exist.')
                },
                success: function() {
                    that.loadModel(lastModel, false, true);
                }
            });
        }

        // Uncomment this if you want Trackball controls instead of Orbit controls
        // this.sceneControls = new THREE.TrackballControls( this.camera, this.container );
        // this.sceneControls.noZoom = false;
        // this.sceneControls.dynamicDampingFactor = 0.3;

        this.sceneControls = new THREE.OrbitControls( this.camera, this.container );
        this.sceneControls.enableZoom = true;
        this.sceneControls.zoomSpeed = 0.9;
        this.sceneControls.rotateSpeed = 0.1;
        this.sceneControls.enablePan = false;
        this.sceneControls.enableDamping = true;
        this.sceneControls.dampingFactor = 0.25;

        // Auxiliary objects for model selection
        this.raycaster = new THREE.Raycaster();
        this.mouseVector = new THREE.Vector3();

        this.selectedObject = null;
        this.transformControls = null;

        // Adds the printer bed auxiliary object
        this._addBed();

        window.addEventListener('resize', BEEwb.events.onWindowResize, false );
        this.container.addEventListener('mouseup', BEEwb.events.onMouseUp, false );
        this.container.addEventListener('mousedown', BEEwb.events.onMouseDown, false );

        this.activateWorkbenchKeys();
    },

    render: function () {

        if (this.transformControls != null) {
            this.transformControls.update();
        }
        this.renderer.render( this.scene, this.camera );
    },

    animate: function () {
        requestAnimationFrame( this.animate.bind(this) );
        this.sceneControls.update();
        this.renderer.render( this.scene, this.camera );
    },

    /**
     * Clears the 3D scene
     */
    clearBed: function () {
        if (this.objects !== null) {
            if (this.objects.children.length > 0) {
                var iter = this.objects.children.length;
                for (var i=0; i < iter; i++) {
                    var targetObj = this.objects.children[0];
                    BEEwb.transformOps.removeModel(targetObj);
                }
            }
        }

        this.removeAllSelections();
    },

    /**
     * Loads an STL model into the canvas
     *
     * The forceLoad parameter is used to force the loading of the model even if it is found in the list of saved scenes
     */
    loadModel: function (modelName, systemFile, forceLoad) {

        // Workaround to prevent the "double" loading of a saved scene
        if (this.savedScenesFiles.indexOf(modelName) !== -1 && !forceLoad) {
            return null;
        }

        var folder = './downloads/files/local/';
        if (systemFile === true) {
            folder = './stl/';
        } else {
            // Extracts the extension from filename
            var modelNameWOExtension = modelName.substr(0, modelName.lastIndexOf("."));

            // Checks if the model name already contains a bee timestamp and removes it
            if (modelNameWOExtension.indexOf('__bee') !== -1) {
                modelNameWOExtension = modelNameWOExtension.split("__bee")[0];
            }
            this.lastLoadedModel = modelNameWOExtension;

            // Only shows the loading modal if it's model loaded by the user
            $('#loadingDialog').modal('show');
        }

        // Removes previous object
        this.scene.remove(this.transformControls);

        var loader = new THREE.STLLoader();

        var that = this;
        // Colored binary STL
        loader.load(folder + modelName, function ( geometry ) {
            var material = new THREE.MeshPhongMaterial( { color: 0x8C8C8C, specular: 0x111111, shininess: 100 } );

            // Centers the object if it's not centered
            BEEwb.helpers.centerModelBasedOnBoundingBox(geometry);

            // Calculates any possible translation in the X axis due to the previously loaded model
            var xShift = BEEwb.helpers.calculateObjectShift( geometry );

            var mesh = new THREE.Mesh( geometry, material );
            mesh.position.set( xShift, 0, 0 );

            //mesh.rotation.set( - Math.PI , Math.PI , 0 );
            //mesh.scale.set( 1.5, 1.5, 1.5 );
            mesh.castShadow = true;

            that.scene.add( mesh );
            that.objects.add(mesh);

            // Runs the placeOnBed algorithm
            that.selectModel(mesh);
            BEEwb.transformOps.placeOnBed();

            $('#loadingDialog').modal('hide');
            document.cookie="lastModel=" + modelName;
        });
    },

    /**
     * Saves the current scene
     *
     * @param filename
     * @returns Promise object of the Ajax call to the server
     */
    saveScene: function ( filename ) {
        var scope = this;
        var stlData = BEEwb.helpers.generateSTLFromScene( this.objects );

        if (filename === undefined) {
            filename = BEEwb.helpers.generateSceneName();
        }

        var data = new FormData();
        data.append('file', stlData, filename);

        scope.savedScenesFiles.push(filename);

        return $.ajax({
            url: API_BASEURL + "files/local",
            type: 'POST',
            data: data,
            contentType: false,
            processData: false,
            success: function(data) {

                var html = _.sprintf(gettext("The scene was saved to the local filesystem."));
                new PNotify({title: gettext("Save success"), text: html, type: "success", hide: true});

            },
            error: function() {
                var html = _.sprintf(gettext("Could not save the scene in the server filesystem. Make sure you have the right permissions and disk space."));
                new PNotify({title: gettext("Save failed"), text: html, type: "error", hide: false});

                // removes the generated file name from the names array
                for (var i = scope.savedScenesFiles.length-1; i >= 0; i--) {
                    if (scope.savedScenesFiles[i] === filename) {
                        array.splice(i, 1);
                        break;
                    }
                }
            }
        });
    },

    /**
     * Downloads the current scene in STL format
     *
     */
    downloadScene: function () {

        var stlData = BEEwb.helpers.generateSTLFromScene( this.objects );

        saveAs(stlData, BEEwb.helpers.generateSceneName());
    },

    /**
     * Selects a model in the canvas
     */
    selectModel: function ( model ) {

        // De-selects other objects
        this.objects.children.forEach(function( obj ) {
            //sets the default color in the object
            obj.material.color = new THREE.Color(DEFAULT_COLOR) ;
        });
        if (this.transformControls != null) {
            this.transformControls.detach();
        }

        //sets the selected color in the object
        model.material.color = new THREE.Color(SELECT_COLOR);

        // Attaches the transform controls to the newly selected object
        if (this.selectedObject == null || this.selectedObject !== model) {
            this.scene.remove(this.transformControls);
            this.transformControls = new THREE.TransformControls( this.camera, this.renderer.domElement );
            this.transformControls.addEventListener( 'change', this.render.bind(this) );
            this.transformControls.attach( model );
            this.scene.add( this.transformControls );

            // Sets the selected object to the first selected model
            this.selectedObject = model;
        }

        // Activates the side buttons
        $('.model-selection').prop('disabled', false);

        // Shows the controls panel
        if ($('#workbench_ctrls_wrapper').is(':visible')) {
            if (!$('#workbench_ctrls').hasClass('in')) {
                $("#workbench_ctrls").collapse("show");
            }
        } else {
            $('#workbench_ctrls_wrapper').slideDown();
        }

        // Activates the default transform operation
        BEEwb.transformOps.activateMove();

        // Sets the initial size for the transform operations
        BEEwb.transformOps.setInitialSize();
    },

    /**
     * Checks if the selected object is out of the printing area
     */
    isSelectedObjectOutOfBounds: function () {

        if (BEEwb.helpers.objectOutOfBounds(BEEwb.main.selectedObject, [BEEwb.main.bedWidth, BEEwb.main.bedDepth, BEEwb.main.bedHeight])) {
            BEEwb.main.toggleObjectOutOfBounds(BEEwb.main.selectedObject, true);
        } else {
            BEEwb.main.toggleObjectOutOfBounds(BEEwb.main.selectedObject, false);
        }
    },

    /**
     * Toogles the out of bounds state for a model in the scene
     */
    toggleObjectOutOfBounds: function ( model, toogle ) {
        //sets the out of bounds color in the object
        if (model != null) {
            if (toogle) {
                model.material.color = new THREE.Color(OUT_BOUNDS_COLOR);
                $('#out-bound-msg').show();
            } else {
                model.material.color = new THREE.Color(SELECT_COLOR);
                $('#out-bound-msg').hide();
            }
        }
    },

    /**
     * Removes all selections from the objects in the canvas
     */
     removeAllSelections: function() {

        this.objects.children.forEach(function( obj ) {
            //sets the default color in the object
            obj.material.color = new THREE.Color(DEFAULT_COLOR);
        });

        if (this.transformControls != null) {

            this.transformControls.detach();
            //transformControls.dispose();
        }

        this.selectedObject = null;

        $('.model-selection').prop('disabled', true);

        $('#btn-scale').removeClass('btn-primary');
        $('#btn-rotate').removeClass('btn-primary');
        $('#btn-move').removeClass('btn-primary');

        if ($('#workbench_ctrls_wrapper').is(':visible')) {
            if ($("#workbench_ctrls").hasClass('in')) {
                $("#workbench_ctrls").collapse('hide');
            }
        }
    },

    /**
     * Resets the camera position
     */
     resetCamera: function() {

        this.camera.position.set( 0, -200, 100 );

        this.camera.up.set( 0, 0, 1 ); // Without this the model is seen upside down
        this.camera.lookAt( new THREE.Vector3( 0, -100, 0 ) );

     },

    /**
     * Adds the printer bed to the canvas
     *
     */
     _addBed: function( ) {

        // Rectangle
        var rectHeight = this.bedDepth;
        var rectWidth = this.bedWidth;

        // Loads bed support stl
        var that = this;
        var loader = new THREE.STLLoader();
        loader.load('./stl/btf_bed.stl', function ( geometry ) {
            var material = new THREE.MeshPhongMaterial( { color: 0x8C8C8C, specular: 0x111111, shininess: 200 } );

            // Transparent shape
            // var material = new THREE.MeshBasicMaterial(
            //     {color: 0x8C8C8C, side: THREE.DoubleSide, opacity: 0.5, transparent: true, depthWrite: false}
            // );

            var printerBed = new THREE.Mesh( geometry, material );
            printerBed.position.set( 0, 0, -0.1 );
            printerBed.receiveShadow = true;

            that.scene.add( printerBed );

        });

        // Bed blue cover plane
        var color = 0x468AC7;

        var rectShape = new THREE.Shape();
        rectShape.moveTo( 0,0 );
        rectShape.lineTo( 0, rectHeight );
        rectShape.lineTo( rectWidth, rectHeight );
        rectShape.lineTo( rectWidth, 0 );
        rectShape.lineTo( 0, 0 );

        // 3D shape
        //var extrudeSettings = { amount: 0.0, bevelEnabled: false}; //amount = thickness
        //var geometry = new THREE.ExtrudeGeometry( rectShape, extrudeSettings );

        var geometry = new THREE.ShapeGeometry( rectShape );
        var bedCover = new THREE.Mesh( geometry, new THREE.MeshPhongMaterial( { color: color } ) );

        // Transparent shape
        // var mesh = new THREE.Mesh( geometry, new THREE.MeshBasicMaterial(
        //         {color: color, side: THREE.DoubleSide, opacity: 0.5, transparent: true, depthWrite: false}
        //     )
        // );

        bedCover.position.set( -(rectWidth / 2), -(rectHeight / 2), 0 );
        bedCover.rotation.set( 0, 0, 0 );
        bedCover.scale.set( 1, 1, 1 );
        bedCover.receiveShadow = true;

        // Sets the global bed var
        this.bed = bedCover;

        this.scene.add( this.bed );

        // Grid
        // We must overlap 2 grids, in order to fill the entire bed space because,
        // they are exact square and the bed is not
        var normalizedBedDepth = this.bedDepth + 5; // We add 5 to round out the bedDepth to facilitate grid size calculations
        var widthHeightDiff = this.bedWidth - normalizedBedDepth;
        var gridXY1 = new THREE.GridHelper(normalizedBedDepth, normalizedBedDepth / 10, '#666666', '#666666');
        gridXY1.position.set(-widthHeightDiff/2, 0, 0);
        gridXY1.rotation.x = Math.PI/2;
        this.scene.add(gridXY1);

        var gridXY2 = new THREE.GridHelper(normalizedBedDepth, normalizedBedDepth / 10, '#666666', '#666666');
        gridXY2.position.set(+widthHeightDiff/2, 0, 0);
        gridXY2.rotation.x = Math.PI/2;
        this.scene.add(gridXY2);
    },

    /**
     * Activates the workbench shortcut keys
     *
     */
    activateWorkbenchKeys: function () {
        window.addEventListener('keydown', BEEwb.events.onKeyDown);
        window.addEventListener('keyup', BEEwb.events.onKeyUp);
    },

    /**
     * De-activates the workbench shortcut keys
     *
     */
    deactivateWorkbenchKeys: function () {
        window.removeEventListener('keydown', BEEwb.events.onKeyDown);
        window.removeEventListener('keyup', BEEwb.events.onKeyUp);
    }
};
