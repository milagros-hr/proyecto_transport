// Script para Crear Ruta: mapa + solicitudes alrededor del conductor
(function () {
  const mapDiv = document.getElementById('map');
  if (!mapDiv) return;

  let map = null;
  let conductorMarker = null;
  let solicitudMarkers = [];
  let pollId = null;

  function initMap(lat, lng) {
    map = L.map('map').setView([lat, lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }).addTo(map);

    const carIcon = L.icon({
      iconUrl: 'https://cdn-icons-png.flaticon.com/512/743/743007.png',
      iconSize: [36, 36],
      iconAnchor: [18, 18]
    });

    conductorMarker = L.marker([lat, lng], { icon: carIcon }).addTo(map)
      .bindPopup('🚗 Tu ubicación (conductor)').openPopup();
  }

  function clearSolicitudMarkers() {
    solicitudMarkers.forEach(m => map.removeLayer(m));
    solicitudMarkers = [];
  }

  function drawSolicitudes(sols, lat, lng) {
    clearSolicitudMarkers();
    const listDiv = document.getElementById('sol-list');
    listDiv.innerHTML = '';
    if (!Array.isArray(sols) || sols.length === 0) {
      listDiv.innerHTML = '<div class="sol-item">No hay solicitudes por el momento.</div>';
      return;
    }

    const radiusDeg = 0.0012; // pequeño radio alrededor del conductor (~120m)
    sols.forEach((s, i) => {
      let latO = null, lngO = null;
      if (s && s.origen && typeof s.origen === 'object' && s.origen.lat != null && s.origen.lng != null) {
        latO = parseFloat(s.origen.lat); lngO = parseFloat(s.origen.lng);
      }

      let markerPos;
      if (latO && lngO) {
        markerPos = [latO, lngO];
      } else {
        const angle = (i / sols.length) * Math.PI * 2;
        markerPos = [lat + Math.cos(angle) * radiusDeg, lng + Math.sin(angle) * radiusDeg];
      }

      const alertIcon = L.circleMarker(markerPos, {
        radius: 9,
        color: '#c0392b',
        fillColor: '#e74c3c',
        fillOpacity: 0.9,
        weight: 1.2
      }).addTo(map);

      const infoHtml = `
        <div><strong>Solicitud</strong></div>
        <div>Pasajero: ${s.pasajero_id || s.pasajero || 'N/A'}</div>
        <div>Origen: ${s.origen && (s.origen.nombre || s.origen.texto) ? (s.origen.nombre || s.origen.texto) : 'Desconocido'}</div>
        <div>Destino: ${s.destino && (s.destino.nombre || s.destino.texto) ? (s.destino.nombre || s.destino.texto) : (s.destino || 'N/A')}</div>
      `;
      alertIcon.bindPopup(infoHtml);
      solicitudMarkers.push(alertIcon);

      const item = document.createElement('div');
      item.className = 'sol-item';
      item.innerHTML = infoHtml + `<div style="margin-top:6px"><button data-idx="${i}">Ver en mapa</button></div>`;
      const btn = item.querySelector('button');
      btn.addEventListener('click', () => {
        map.setView(markerPos, 16);
        alertIcon.openPopup();
      });
      listDiv.appendChild(item);
    });
  }

  function fetchSolicitudesAndDraw(lat, lng) {
    fetch('/api/solicitudes')
      .then(r => r.json())
      .then(data => drawSolicitudes(data || [], lat, lng))
      .catch(err => console.error('Error fetching solicitudes', err));
  }

  function onPosition(pos) {
    const lat = pos.coords.latitude, lng = pos.coords.longitude;
    if (!map) initMap(lat, lng);
    conductorMarker.setLatLng([lat, lng]);
    map.setView([lat, lng]);
    fetchSolicitudesAndDraw(lat, lng);
    if (pollId) clearInterval(pollId);
    pollId = setInterval(() => fetchSolicitudesAndDraw(lat, lng), 8000);
  }

  function onError() {
    // fallback a Centro de Lima si geolocalización falla
    const lat = -12.0464, lng = -77.0428;
    initMap(lat, lng);
    fetchSolicitudesAndDraw(lat, lng);
  }

  document.getElementById('btn-refresh').addEventListener('click', () => {
    if (conductorMarker) {
      const p = conductorMarker.getLatLng();
      fetchSolicitudesAndDraw(p.lat, p.lng);
    }
  });

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(onPosition, onError, { enableHighAccuracy: true, timeout: 8000 });
  } else {
    onError();
  }
})();