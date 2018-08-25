colorDefaults = {
    strokeColor: '#0000ff',
    strokeOpacity: 0.7,
    strokeWeight: 1,
    fillColor: '#0000ff',
    fillOpacity: 0.3
};

// map markers for each level of tournament
markerSublists = { M: [], H: [], C: [], O: [], T: [] };

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 4,
        center: {lat: 40.0, lng: -96.0},
        mapTypeId: 'roadmap'
    });
    
    // state notifications
    [].forEach.call(
      document.getElementsByClassName('notify-state'),
      function(elem) { drawState(elem.dataset.state); }
    );

    map.data.setStyle(colorDefaults);
    
    // circular notifications
    [].forEach.call(
      document.getElementsByClassName('notify-circle'),
      function(elem) {
          var radius = parseFloat(elem.dataset.radius);
          // google maps accepts radius in meters, we need to convert
          switch(elem.dataset.unit) {
          case 'mi':
            radius *= 1609.3;
            break;
          case 'ft':
            radius *= 0.3048;
            break;
          case 'km':
            radius *= 1000.0;
            break;
          default:
            radius *= 1.0;
          }
          
          drawCircle(
            parseFloat(elem.dataset.lat),
            parseFloat(elem.dataset.lng),
            radius
          );
      }
    );

    // markers for upcoming tournaments
    getJSON(
        document.location.origin + '/static/upcoming.json',
        function(tournaments) {
            var levelDict = { M: 'Middle school', H: 'High school', C: 'College',
                              O: 'Open', T: 'Trash' };

            infWindow = new google.maps.InfoWindow();
            tournaments.forEach(function(t) {
                var marker = new google.maps.Marker({
                    // jiggle so overlapping markers are visible
                    position: {lat: t.lat + 0.0002 * (Math.random() - 0.5),
                               lng: t.lon + 0.0002 * (Math.random() - 0.5)},
                    map: map,
                    title: t.name,
                    icon: '/static/markers/' + t.level + '.png'
                });

                markerSublists[t.level].push(marker);

                // pull up description when marker is clicked
                marker.addListener('click', function() {
                    var cont = '<a href="http://hsquizbowl.org/db/tournaments/'+t.id+'">'
                        + t.name + '</a><br />'
                        + levelDict[t.level] + ' tournament on ' + t.date;
                    infWindow.setContent(cont);
                    infWindow.open(map, marker);
                });
            });
        }
    );
}

// JSON XHR wrapper for convenience
function getJSON(url, callback) {
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

function drawCircle(lat, lng, radius) {
    var params = Object.assign({
        center: {lat: lat, lng: lng},
        radius: radius,
    }, colorDefaults);
    var circle = new google.maps.Circle(params);
    circle.setMap(map);
}

function drawState(abbr) {
    map.data.loadGeoJson('static/geojson/' + abbr + '.json');
}

function checkFunc(box) {
    var markers = markerSublists[box.getAttribute('name')];
    markers.forEach(function(m) { m.setVisible(box.checked); });
}
