var getJSON = function(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'json';
    xhr.onload = function() {
        var status = xhr.status;
        if (status === 200) {
            callback(xhr.response);
        }
    };
    xhr.send();
};

function drawPoly(coords) {
    // Construct the polygon.
    var polygon = new google.maps.Polygon({
        paths: coords,
        strokeColor: '#FF0000',
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: '#FF0000',
        fillOpacity: 0.35
    });
    polygon.setMap(map);
}

function drawState(abbr) {
    getJSON(document.location.origin + '/static/polygons/' + abbr + '.json',
	    drawPoly);
}

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 4,
        center: {lat: 40.0, lng: -96.0},
        mapTypeId: 'roadmap'
    });

    [].forEach.call(
	document.getElementsByClassName("notify-state"),
	function(x) { drawState(x.dataset.state); }
    );
}
