// ============================================
// NAVEGACIÓN EXTERNA + REFRESH PARA CONDUCTORES
// ============================================

// ✅ Viaje actual (el que usa el chofer para navegar)
let viajeActual = null;

// ✅ polling
let __pollViajes = null;
let __ultimoViajeId = null;

// Arrancar cuando carga la página del conductor
document.addEventListener("DOMContentLoaded", () => {
  // 1ra carga inmediata
  cargarViajesActivosConductor();

  // refrescar cada 4s (ajústalo si quieres)
  __pollViajes = setInterval(cargarViajesActivosConductor, 4000);
});

window.addEventListener("beforeunload", () => {
  if (__pollViajes) clearInterval(__pollViajes);
});

// ============================================
// ✅ POLLING: si el pasajero cancela => el API devuelve [] => limpiamos UI
// ============================================
async function cargarViajesActivosConductor() {
  try {
    const res = await fetch("/api/conductor/mis-viajes-activos", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const viajes = await res.json();

    // ✅ Si no hay viajes activos => limpiar todo
    if (!Array.isArray(viajes) || viajes.length === 0) {
      if (__ultimoViajeId !== null) {
        // antes había viaje y ahora ya no => probablemente el pasajero canceló
        alert("🚫 El viaje ya no está activo. (Posible cancelación del pasajero)");
      }

      __ultimoViajeId = null;
      viajeActual = null;

      // 1) Limpia panel/tabla
      renderEmptyStateConductor();

      // 2) Limpia mapa/ruta si existe
      limpiarMapaRutaConductor();

      // 3) Si tú tienes funciones propias, las llamamos si existen
      if (typeof window.onViajesConductorVacios === "function") {
        window.onViajesConductorVacios();
      }

      return;
    }

    // ✅ Hay viajes: tomamos el primero (como tú vienes trabajando)
    const v0 = viajes[0];
    __ultimoViajeId = v0.id ?? v0.solicitud_id ?? __ultimoViajeId;
    viajeActual = v0;

    // Si tú ya tienes renderer propio, úsalo
    if (typeof window.renderViajesConductor === "function") {
      window.renderViajesConductor(viajes);
    } else if (typeof window.actualizarVistaViajeConductor === "function") {
      window.actualizarVistaViajeConductor(v0);
    } else {
      // fallback básico (para no quedar en blanco)
      renderViajeBasicoConductor(v0);
    }

  } catch (e) {
    console.error("❌ Error cargando viajes activos conductor:", e);
  }
}

// ============================================
// ✅ UI helpers (no rompe si no existen elementos)
// ============================================
function renderEmptyStateConductor() {
  const cont =
    document.getElementById("viajesConductorContainer") ||
    document.getElementById("viajesContainer") ||
    document.getElementById("listaViajes") ||
    document.getElementById("panelViajeConductor");

  if (!cont) return;

  cont.innerHTML = `
    <div style="text-align:center;padding:2rem;color:#666;background:#fff;border:1px dashed rgba(0,0,0,.15);border-radius:16px;">
      <i class="fas fa-route" style="font-size:2.5rem;color:#ddd;margin-bottom:1rem;"></i>
      <p style="margin:0;">No tienes viajes activos en este momento.</p>
    </div>
  `;
}

function renderViajeBasicoConductor(v) {
  const cont =
    document.getElementById("viajesConductorContainer") ||
    document.getElementById("viajesContainer") ||
    document.getElementById("listaViajes") ||
    document.getElementById("panelViajeConductor");

  if (!cont) return;

  cont.innerHTML = `
    <div style="padding:1rem;border:1px solid #eee;border-radius:12px;background:#fff;">
      <div><b>Viaje activo:</b> #${v.id ?? "?"}</div>
      <div><b>Estado:</b> ${(v.estado ?? "").toString()}</div>
    </div>
  `;
}

function limpiarMapaRutaConductor() {
  try {
    // ✅ Si usas Google Maps DirectionsRenderer:
    if (window.directionsRenderer && typeof window.directionsRenderer.setDirections === "function") {
      window.directionsRenderer.setDirections({ routes: [] });
    }

    // ✅ Si guardas polylines:
    if (window.polylineRuta && typeof window.polylineRuta.setMap === "function") {
      window.polylineRuta.setMap(null);
      window.polylineRuta = null;
    }

    // ✅ Si guardas markers:
    if (Array.isArray(window.markersRuta)) {
      window.markersRuta.forEach(m => m && m.setMap && m.setMap(null));
      window.markersRuta = [];
    }
  } catch (e) {
    console.warn("⚠️ No se pudo limpiar el mapa:", e);
  }
}

// ============================================
// ✅ TUS FUNCIONES: NAVEGAR a recojo/destino
// ============================================
function navegarARecojo() {
  const o = viajeActual?.origen;
  if (!o || o.lat == null || o.lng == null) {
    alert("No hay punto de recojo disponible");
    return;
  }

  const lat = o.lat;
  const lng = o.lng;
  const nombre = o.nombre || "Recojo";

  if (confirm(`¿Abrir Google Maps para ir a:\n📍 ${nombre}?`)) {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
    window.open(url, "_blank");
  }
}

function navegarARecojoWaze() {
  const o = viajeActual?.origen;
  if (!o || o.lat == null || o.lng == null) {
    alert("No hay punto de recojo disponible");
    return;
  }

  const lat = o.lat;
  const lng = o.lng;
  const nombre = o.nombre || "Recojo";

  if (confirm(`¿Abrir Waze para ir a:\n📍 ${nombre}?`)) {
    const url = `https://www.waze.com/ul?ll=${lat},${lng}&navigate=yes`;
    window.open(url, "_blank");
  }
}

function navegarADestino() {
  const d = viajeActual?.destino;
  if (!d || d.lat == null || d.lng == null) {
    alert("No hay destino disponible");
    return;
  }

  const lat = d.lat;
  const lng = d.lng;
  const nombre = d.nombre || "Destino";

  if (confirm(`¿Abrir Google Maps para ir a:\n🏁 ${nombre}?`)) {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
    window.open(url, "_blank");
  }
}

function navegarADestinoWaze() {
  const d = viajeActual?.destino;
  if (!d || d.lat == null || d.lng == null) {
    alert("No hay destino disponible");
    return;
  }

  const lat = d.lat;
  const lng = d.lng;
  const nombre = d.nombre || "Destino";

  if (confirm(`¿Abrir Waze para ir a:\n🏁 ${nombre}?`)) {
    const url = `https://www.waze.com/ul?ll=${lat},${lng}&navigate=yes`;
    window.open(url, "_blank");
  }
}


// ============================================
// ✅ AVISO + LIMPIEZA si el pasajero canceló
// (Polling a /api/conductor/mis-viajes-activos)
// ============================================

(function () {
  const POLL_MS = 3000; // 3s
  let habiaViaje = false;
  let ultimoId = null;

  async function pollViajes() {
    try {
      const res = await fetch("/api/conductor/mis-viajes-activos", {
        credentials: "same-origin",
        headers: { "Accept": "application/json" }
      });

      if (!res.ok) return;

      const viajes = await res.json();

      // Si tu API devuelve {error:...} en vez de lista:
      if (!Array.isArray(viajes)) return;

      if (viajes.length === 0) {
        // ✅ antes había viaje y ahora ya no => cancelación/fin/limpieza
        if (habiaViaje) {
          alert("🚫 El pasajero canceló el viaje (o ya no está activo). Se limpiará la pantalla.");
          // lo más estable: recargar vista para que se borre panel + mapa
          window.location.reload();
          return;
        }
        habiaViaje = false;
        ultimoId = null;
        return;
      }

      // ✅ hay viaje
      habiaViaje = true;
      const v0 = viajes[0];
      ultimoId = v0?.id ?? v0?.solicitud_id ?? ultimoId;

      // si tu app usa variable global viajeActual, la actualizamos sin romper
      try {
        window.viajeActual = v0;
      } catch (_) {}

    } catch (e) {
      console.warn("pollViajes error:", e);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    pollViajes();
    setInterval(pollViajes, POLL_MS);
  });
})();
