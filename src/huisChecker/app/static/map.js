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

  var NO_DATA_COLOR = "#d1d5db";

  function featureStyle(props, fallbackColor, opacity) {
    // Base choropleth: one uniform stroke for every feature so the
    // selected PC4 is not emphasised here. The highlight layer renders
    // a separate outline-only overlay for the selected cell.
    var isNoData = !!(props && props._no_data);
    var color =
      (props && props._color) ||
      (isNoData ? NO_DATA_COLOR : fallbackColor || "#334155");
    return {
      color: "#475569",
      weight: 1.0,
      dashArray: isNoData ? "2,3" : null,
      fillColor: color,
      fillOpacity: isNoData ? Math.min(opacity, 0.35) : Math.max(opacity, 0.35),
      opacity: 0.75,
    };
  }

  function highlightStyle() {
    return {
      color: "#0f172a",
      weight: 3.5,
      opacity: 1.0,
      fill: false,
      fillOpacity: 0,
      interactive: false,
    };
  }

  function bindFeatureTooltip(feature, layerObj, meta, selectedPc4) {
    var props = feature.properties || {};
    var parts = [];
    if (meta.label) parts.push("<strong>" + meta.label + "</strong>");
    if (props._label) parts.push(escapeHtml(props._label));
    else if (meta.legend && props[meta.key]) parts.push(escapeHtml(String(props[meta.key])));
    if (props.postcode4) {
      var pc4 = String(props.postcode4);
      var label = "PC4 " + escapeHtml(pc4);
      if (selectedPc4 && pc4 === selectedPc4) label += " (geselecteerd)";
      parts.push(label);
    }
    if (props.reference_period) {
      parts.push("peiljaar " + escapeHtml(String(props.reference_period)));
    }
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
    var focusPc4 = (root.dataset.focusPostcode4 || "").trim();
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
        // Placeholder for the per-layer PC4-coverage note, populated after
        // the geojson arrives if no feature matches the focused PC4.
        var coverage = document.createElement("span");
        coverage.className = "hc-layer-coverage hidden";
        coverage.dataset.layerKey = key;
        togglesEl.appendChild(coverage);

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
        if (state.highlightLayer) state.highlightLayer.addTo(map);
        return Promise.resolve(state.leafletLayer);
      }
      if (state.meta && state.meta.remote && state.meta.remote.tile_url) {
        var r = state.meta.remote;
        var lyr;
        if (r.kind === "wms") {
          lyr = L.tileLayer.wms(r.tile_url, {
            layers: r.layer_name || "",
            format: r.format || "image/png",
            transparent: r.transparent !== false,
            attribution: r.attribution || "",
            opacity: state.opacity,
          });
        } else {
          lyr = L.tileLayer(r.tile_url, {
            attribution: r.attribution || "",
            opacity: state.opacity,
          });
        }
        lyr.addTo(map);
        state.leafletLayer = lyr;
        setCoverageNote(
          key,
          r.explanatory_note || "Laag wordt remote gerenderd."
        );
        return Promise.resolve(lyr);
      }
      return fetch("/map/layers/" + encodeURIComponent(key) + ".geojson")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (gj) {
          if (!gj) {
            setCoverageNote(key, "Geen lokale laagdata geladen.");
            return null;
          }
          updateCoverageFromGeoJSON(key, gj);
          var base = L.geoJSON(gj, {
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
              bindFeatureTooltip(feature, l, state.meta, focusPc4);
            },
          });
          base.addTo(map);
          state.leafletLayer = base;
          // Selected-PC4 highlight: rendered as a separate outline-only
          // overlay on top of the base fill, so the base layer stays a
          // clean choropleth with one feature per PC4.
          var selected = selectedFeature(gj, focusPc4);
          if (selected) {
            var hl = L.geoJSON(selected, { style: highlightStyle });
            hl.addTo(map);
            state.highlightLayer = hl;
          }
          return base;
        });
    }

    function selectedFeature(gj, pc4) {
      if (!pc4) return null;
      var features = (gj && gj.features) || [];
      for (var i = 0; i < features.length; i++) {
        var f = features[i];
        var p = (f && f.properties) || {};
        if (String(p.postcode4 || "") === pc4) {
          var geom = f.geometry;
          if (!geom) return null;
          if (geom.type !== "Polygon" && geom.type !== "MultiPolygon") return null;
          return f;
        }
      }
      return null;
    }

    function removeLayer(key) {
      var state = layerState[key];
      if (!state) return;
      if (state.leafletLayer) map.removeLayer(state.leafletLayer);
      if (state.highlightLayer) map.removeLayer(state.highlightLayer);
    }

    function setCoverageNote(key, text) {
      var el = togglesEl.querySelector('.hc-layer-coverage[data-layer-key="' + key + '"]');
      if (!el) return;
      if (!text) {
        el.classList.add("hidden");
        el.textContent = "";
      } else {
        el.classList.remove("hidden");
        el.textContent = text;
      }
    }

    function updateCoverageFromGeoJSON(key, gj) {
      var features = (gj && gj.features) || [];
      if (!features.length) {
        setCoverageNote(key, "Geen lokale features in deze laag.");
        return;
      }
      if (!focusPc4) {
        setCoverageNote(key, null);
        return;
      }
      var matched = null;
      for (var i = 0; i < features.length; i++) {
        var f = features[i];
        var p = (f && f.properties) || {};
        if (String(p.postcode4 || "") === focusPc4) { matched = f; break; }
      }
      if (!matched) {
        setCoverageNote(key, "Geen lokale data voor PC4 " + focusPc4 + ".");
        return;
      }
      if (isNilIslandGeometry(matched.geometry)) {
        setCoverageNote(
          key,
          "Data aanwezig, maar geometrie ontbreekt voor PC4 " + focusPc4 +
          " (overlay niet zichtbaar op kaart)."
        );
        return;
      }
      setCoverageNote(key, null);
    }

    function isNilIslandGeometry(geometry) {
      if (!geometry || !geometry.coordinates) return false;
      function flat(coords, out) {
        if (typeof coords[0] === "number") { out.push(coords); return; }
        for (var i = 0; i < coords.length; i++) flat(coords[i], out);
      }
      var pts = [];
      flat(geometry.coordinates, pts);
      if (!pts.length) return true;
      return pts.every(function (pt) {
        return Math.abs(pt[0]) < 0.1 && Math.abs(pt[1]) < 0.1;
      });
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
      if (state.leafletLayer.setOpacity) {
        state.leafletLayer.setOpacity(value);
        return;
      }
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
