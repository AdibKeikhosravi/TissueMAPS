angular.module('tmaps.core')
.factory('AppInstance',
         ['createViewport', 'openlayers', '$q', 'CellSelectionHandler', 'CycleLayer', 'OutlineLayer', 'Experiment', '$http',
         function(createViewport, ol, $q, CellSelectionHandler, CycleLayer, OutlineLayer, Experiment, $http) {

    /**
     * AppInstance is the main class for handling the visualization and
     * interaction with a specific experiment. It is responsible for drawing
     * layers and selecting cells.
     *
     * This class is also responsible for creating the openlayers map object and
     * injecting it into the DOM. The map object can be used by helper classes via
     * the 'map'-promise.
     */
    function AppInstance(experiment) {
        this.experiment = experiment;

        var viewportDef = $q.defer();
        var mapDef = $q.defer();

        // Use these to interact with the map/viewport
        this.viewport = viewportDef.promise;
        this.map = mapDef.promise;

        // Internal representation of map state
        this.cycleLayers = [];
        this.outlineLayers = [];

        // Keep track of the click listeners that were added to the map
        // s.t. they can be removed later
        this.clickListeners = {};

        // Helper class to manage the differently marker selections
        this.selectionHandler = new CellSelectionHandler(this);

        createViewport(this, 'viewports', '/templates/main/viewport.html')
        .then(function(viewport) {
            viewportDef.resolve(viewport);
            mapDef.resolve(viewport.map);
        });
    }

    // TODO: Consider throwing everything cell position related into own
    // CellPositionHandler or something like that.
    AppInstance.prototype.getCellAtPos = function(x, y) {
        return $http.get('/experiments/' + this.experiment.id + '/cells?x=' + x + '&y=' + y)
        .then(function(resp) {
            console.log(resp);
            return resp.data['cell_id'];
        });
    };

    AppInstance.prototype.addChannelLayers = function(layerOptions) {
        var self = this;
        // Only the first layer should be visible
        _.each(layerOptions, function(opt, i) {
            opt = _.defaults(opt, {
                visible: i === 0,
                color: [1, 1, 1]
            });
            self.addCycleLayer(opt);
        });
    };

    AppInstance.prototype.addMaskLayers = function(layerOptions) {
        var self = this;
        // Add the layers that are flagged as masking layers
        // If there are multiple such layers, the first will be
        // initially visible and the others invisible.
        _.each(layerOptions, function(opt, i) {
            opt = _.defaults(opt, {
                visible: i === 0,
                color: [1, 1, 1]
            });
            self.addOutlineLayer(opt);
        });
    };

    AppInstance.prototype.getExperimentName = function() {
        return this.experiment.name;
    };

    /**
     * Clean up method when the instance is closed (e.g. by deleting the Tab).
     */
    AppInstance.prototype.destroy = function() {
        this.viewport.then(function(viewport) {
            // Destroy the stuff that this instance created
            viewport.scope.$destroy();
            viewport.element.remove();
        });
    };

    /**
     * Set this instance active: display the map container and handle the case
     * when the browser window was resized.
     * NOTE: Always call the setActiveInstance method on the application global
     * object since that function will also deactivate other instances.
     */
    AppInstance.prototype.setActive = function() {
        this.viewport.then(function(viewport) {
            viewport.element.show();
            viewport.map.updateSize();
        });
    };

    /**
     * Hide the openlayers canvas.
     * As with setInactive: the Application object should call this function
     * and make sure that exactly one AppInstance is set active at all times.
     */
    AppInstance.prototype.setInactive = function() {
        this.viewport.then(function(viewport) {
            viewport.element.hide();
        });
    };

    /*
     * Add a segmentation layer for this experiment
     * The main difference to setting a cycle layer is that
     * 1. The created class is a OutlineLayer and as such it is not blended
     *    additively but black parts of the image aren't drawn anyway.
     * 2. The layer won't get added to the AppInstance.cycleLayers array.
     */
    AppInstance.prototype.addOutlineLayer = function(opt) {
        var outlineLayer = new OutlineLayer(opt);
        this.outlineLayers.push(outlineLayer);

        return this.map.then(function(map) {
            outlineLayer.addToMap(map);
            return outlineLayer;
        });
    };

    AppInstance.prototype.addLayerMod = function(opt) {
        _.defaults(opt, {
            color: [1, 1, 1],
            visible: true,
            drawBlackPixels: true
        });
        this.addOutlineLayer(opt);

        // Kind of a hack: whenever a new mask layer is added, all
        // selection layers are removed and added again so that they come after
        // the masks and therefore are rendered on top of them.
        // z-Index was removed in OL3 apparently.
        var olLayers = _(this.selectionHandler.selections).map(function(sel) {
            return sel.layer.layer;
        });
        this.map.then(function(map) {
            _(olLayers).each(function(l) {
                map.removeLayer(l);
                console.log(l);
                map.addLayer(l);
            });
        });
    };

    /**
     * Remove a outlineLayer from the map.
     * Use this method whenever a layer should be removed since it also updates
     * the app instance's internal state.
     */
    AppInstance.prototype.removeOutlineLayer = function(outlineLayer) {
        this.map.then(function(map) {
            outlineLayer.removeFromMap(map);
        });
        var idx = this.outlineLayers.indexOf(outlineLayer);
        this.outlineLayers.splice(idx, 1);
    };

    /*
     * Add a cycle layer to the underlying map object
     * Always use this smethod when adding new cycles.
     */
    AppInstance.prototype.addCycleLayer = function(opt) {
        var cycleLayer = new CycleLayer(opt);
        if (!window.layers) {
            window.layers = [];
        }

        window.layers.push(cycleLayer);

        var alreadyHasLayers = this.cycleLayers.length !== 0;

        // If this is the first time a layer is added, create a view and add it to the map.
        if (!alreadyHasLayers) {
            // Center the view in the iddle of the image
            // (Note the negative sign in front of half the height)
            var width = opt.imageSize[0];
            var height = opt.imageSize[1];
            var center = [width / 2, - height / 2];
            var view = new ol.View({
                // We create a custom (dummy) projection that is based on pixels
                projection: new ol.proj.Projection({
                    code: 'ZOOMIFY',
                    units: 'pixels',
                    extent: [0, 0, width, height]
                }),
                center: center,
                zoom: 0, // 0 is zoomed out all the way
                // starting at maxResolution where maxResolution
                // is

            });

            this.map.then(function(map) {
                map.setView(view);
            });
        }

        // Add the layer as soon as the map is created (i.e. resolved after
        // viewport injection)
        this.map.then(function(map) {
            cycleLayer.addToMap(map);
        });
        this.cycleLayers.push(cycleLayer);
    };

    /**
     * Remove a cycleLayer from the map.
     * Use this method whenever a layer should be removed since it also updates
     * the app instance's internal state.
     */
    AppInstance.prototype.removeCycleLayer = function(cycleLayer) {
        this.map.then(function(map) {
            cycleLayer.removeFromMap(map);
        });
        var idx = this.cycleLayers.indexOf(cycleLayer);
        this.cycleLayers.splice(idx, 1);
    };

    AppInstance.prototype.toBlueprint = function() {
        var bpPromise = this.map.then(function(map) {
            var v = map.getView();

            var mapState = {
                zoom: v.getZoom(),
                center: v.getCenter(),
                resolution: v.getResolution(),
                rotation: v.getRotation()
            };

            var channelOpts = _(this.cycleLayers).map(function(l) {
                return l.toBlueprint();
            });
            var maskOpts = _(this.outlineLayers).map(function(l) {
                return l.toBlueprint();
            });

            return {
                experiment: this.experiment.toBlueprint(),
                selectionHandler: this.selectionHandler.toBlueprint(),
                channelLayerOptions: channelOpts,
                maskLayerOptions: maskOpts,
                mapState: mapState
            };
        }.bind(this));

        return bpPromise;
    };

    /**
     * Create and initialize an AppInstance from a blueprint and return it.
     */
    AppInstance.fromBlueprint = function(bp) {
        var inst = new AppInstance(new Experiment(bp.experiment));

        inst.addChannelLayers(bp.channelLayerOptions);
        inst.addMaskLayers(bp.maskLayerOptions);

        inst.map.then(function(map) {
            var v = map.getView();
            v.setZoom(bp.mapState.zoom);
            v.setCenter(bp.mapState.center);
            v.setResolution(bp.mapState.resolution);
            v.setRotation(bp.mapState.rotation);
        });

        inst.selectionHandler.initFromBlueprint(bp.selectionHandler);

        return inst;
    };

    return AppInstance;
}]);

