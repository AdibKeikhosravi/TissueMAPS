angular.module('tmaps.shared.thirdpartymodules')
.factory('openlayers', function() {
    return window.ol;
})
.factory('_', function() {
    return window._;
});
