(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["OctoPrintClient"], factory);
    } else {
        factory(global.OctoPrintClient);
    }
})(this, function(OctoPrintClient) {
    var url = "api/remote";


    var OctoPrintRemotePrintersClient = function(base) {
        this.base = base;
    };

    OctoPrintClient.registerComponent("remote", OctoPrintRemotePrintersClient);
    return OctoPrintRemotePrintersClient;
});
