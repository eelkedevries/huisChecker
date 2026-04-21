/* huisChecker shared map. Reads layer keys from data attributes, fetches
   metadata + geojson from /map endpoints, wires legend + toggle + opacity.
   No one-off per-page map code: every overlay is driven by the layer
   registry on the backend. */
(function () {
  "use strict";

  var NL_CENTER = [52.15, 5.3];
  var DEFAULT_ZOOM = 12;

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function parseKeys(raw) {
    if (!raw) return [];
    return raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function createFocusMarker(lat, lon, label) {
    var icon = L.divIcon({
      className: "hc-focus",
      html: '<div class="hc-map-focus-icon"></div>',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });
    var marker = L.marker([lat, lon], { icon: icon, keyboard: false });
    if (label) marker.bindPopup(label);
    return marker;
  }

  function featureStyle(props, fallbackColor, opacity) {
    var color = (props && props._color) || fallbackColor || "#334155";
    return {
      color: "#1e293b",
      weight: 1,
      fillColor: color,
      fillOpacity: opacity,
      opacity: 0.8,
    };
  }

  function bindFeatureTooltip(feature, layerObj, meta) {
    var props = feature.properties || {};
    var parts = [];
    if (meta.label) parts.push("<strong>" + meta.label + "</strong>");
    if (props._label) parts.push(escapeHtml(props._label));
    else if (meta.legend && props[meta.key]) parts.push(escapeHtml(String(props[meta.key])));
    if (props.postcode4) parts.push("PC4 " + escapeHtml(String(props.postcode4)));
    if (parts.length) layerObj.bindTooltip(parts.join("<br>"), { sticky: true });
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function buildLegendSection(meta) {
    if (!meta.legend) return null;
    var wrap = document.createElement("div");
    var title = document.createElement("div");
    title.className = "hc-legend-group-title";
    title.textContent = meta.label + (meta.legend.unit ? " (" + meta.legend.unit + ")" : "");
    wrap.appendChild(title);
    meta.legend.stops.forEach(function (stop) {
      var row = document.createElement("div");
      row.className = "hc-legend-row";
      var sw = document.createElement("span");
      sw.className = "hc-legend-swatch";
      sw.style.background = stop.color;
      row.appendChild(sw);
      var lbl = document.createElement("span");
      lbl.textContent = stop.label;
      row.appendChild(lbl);
      wrap.appendChild(row);
    });
    return wrap;
  }

  function initMap(root) {
    var mapId = root.id;
    var layerKeys = parseKeys(root.dataset.layerKeys);
    if (!layerKeys.length) return;

    var focusLat = parseFloat(root.dataset.focusLat);
    var focusLon = parseFloat(root.dataset.focusLon);
    var hasFocus = !isNaN(focusLat) && !isNaN(focusLon);
    var zoom = parseInt(root.dataset.zoom, 10);
    if (isNaN(zoom)) zoom = DEFAULT_ZOOM;

    var map = L.map(root, {
      center: hasFocus ? [focusLat, focusLon] : NL_CENTER,
      zoom: zoom,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    map.on("blur", function () { map.scrollWheelZoom.disable(); });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    if (hasFocus) {
      createFocusMarker(focusLat, focusLon, root.dataset.focusLabel || "").addTo(map);
    }

    var togglesEl = document.getElementById(mapId + "-toggles");
    var legendEl = document.getElementById(mapId + "-legend");
    var opacityEl = document.getElementById(mapId + "-opacity");
    togglesEl.innerHTML = "";
    legendEl.innerHTML = "";

    var layerState = {}; // key -> { leafletLayer, meta, opacity }

    Promise.all(layerKeys.map(function (key) {
      return fetch("/map/layers/" + encodeURIComponent(key) + ".json")
        .then(function (r) { return r.ok ? r.json() : null; });
    })).then(function (metas) {
      var featureBounds = null;

      metas.forEach(function (meta, idx) {
        if (!meta) return;
        var key = layerKeys[idx];
        var opacity = meta.opacity && typeof meta.opacity.default === "number"
          ? meta.opacity.default : 0.6;
        layerState[key] = { meta: meta, opacity: opacity, leafletLayer: null };

        // Toggle row
        var row = document.createElement("label");
        row.className = "hc-layer-toggle";
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = !!meta.default_visible;
        cb.dataset.layerKey = key;
        row.appendChild(cb);
        var txt = document.createElement("span");
        txt.textContent = meta.label;
        row.appendChild(txt);
        togglesEl.appendChild(row);
        if (meta.caveat) {
          var cav = document.createElement("span");
          cav.className = "hc-layer-caveat";
          cav.textContent = meta.caveat;
          togglesEl.appendChild(cav);
        }

        // Legend
        var legSec = buildLegendSection(meta);
        if (legSec) legendEl.appendChild(legSec);

        cb.addEventListener("change", function () {
          if (cb.checked) ensureLayerLoaded(key);
          else removeLayer(key);
        });
      });

      // Kick off default-visible loads, fit bounds when they arrive.
      var pending = [];
      Object.keys(layerState).forEach(function (key) {
        if (layerState[key].meta.default_visible) {
          pending.push(ensureLayerLoaded(key).then(function (lyr) {
            if (!lyr) return;
            try {
              var b = lyr.getBounds();
              if (b.isValid()) featureBounds = featureBounds ? featureBounds.extend(b) : b;
            } catch (_) { /* point layers etc. */ }
          }));
        }
      });
      Promise.all(pending).then(function () {
        if (!hasFocus && featureBounds && featureBounds.isValid()) {
          map.fitBounds(featureBounds.pad(0.25));
        }
      });
    });

    function ensureLayerLoaded(key) {
      var state = layerState[key];
      if (!state) return Promise.resolve(null);
      if (state.leafletLayer) {
        state.leafletLayer.addTo(map);
        return Promise.resolve(state.leafletLayer);
      }
      return fetch("/map/layers/" + encodeURIComponent(key) + ".geojson")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (gj) {
          if (!gj) return null;
          var lyr = L.geoJSON(gj, {
            style: function (feature) {
              return featureStyle(feature.properties, null, state.opacity);
            },
            pointToLayer: function (feature, latlng) {
              return L.circleMarker(latlng, {
                radius: 5,
                color: "#1e293b",
                weight: 1,
                fillColor: (feature.properties && feature.properties._color) || "#334155",
                fillOpacity: state.opacity,
              });
            },
            onEachFeature: function (feature, l) {
              bindFeatureTooltip(feature, l, state.meta);
            },
          });
          lyr.addTo(map);
          state.leafletLayer = lyr;
          return lyr;
        });
    }

    function removeLayer(key) {
      var state = layerState[key];
      if (state && state.leafletLayer) map.removeLayer(state.leafletLayer);
    }

    function activeLayerKey() {
      var checked = togglesEl.querySelectorAll("input[type=checkbox]:checked");
      if (!checked.length) return null;
      return checked[checked.length - 1].dataset.layerKey;
    }

    opacityEl.addEventListener("input", function () {
      var value = parseInt(opacityEl.value, 10) / 100;
      var key = activeLayerKey();
      if (!key) return;
      var state = layerState[key];
      if (!state) return;
      state.opacity = value;
      if (!state.leafletLayer) return;
      state.leafletLayer.setStyle(function (feature) {
        return featureStyle(feature.properties, null, value);
      });
    });

    // Keep Leaflet sized correctly when the container resizes (responsive).
    if (window.ResizeObserver) {
      new ResizeObserver(function () { map.invalidateSize(); }).observe(root);
    } else {
      window.addEventListener("resize", function () { map.invalidateSize(); });
    }
  }

  ready(function () {
    document.querySelectorAll(".hc-map").forEach(initMap);
  });
})();
