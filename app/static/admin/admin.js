const CENTRO_PORANGA = [-3.110897, -58.458911];
const RAIO_KM = 3;

const map = L.map('map').setView(CENTRO_PORANGA, 14);

L.control.zoom({ position: 'topright' }).addTo(map);

const recentralizarControl = L.control({ position: 'topright' });
recentralizarControl.onAdd = function() {
  const btn = L.DomUtil.create('button');
  btn.innerHTML = '⌖ Centralizar';
  btn.style.cssText = 'background:white;padding:6px 10px;border-radius:4px;border:2px solid rgba(0,0,0,0.2);cursor:pointer;font-size:13px;';
  btn.onclick = () => map.setView(CENTRO_PORANGA, 14);
  return btn;
};
recentralizarControl.addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

L.circle(CENTRO_PORANGA, {
  radius: RAIO_KM * 1000,
  color: '#3388ff',
  fillOpacity: 0.05
}).addTo(map);

const marcadoresMotoboys = {};

function statusEl() {
  return document.getElementById('status');
}

async function conectar() {
  const telefone = document.getElementById('telefone').value;
  const senha = document.getElementById('senha').value;

  let resp;
  try {
    resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefone, senha })
    });
  } catch (e) {
    statusEl().textContent = 'Erro de rede no login';
    return;
  }

  if (!resp.ok) {
    statusEl().textContent = `Login falhou (${resp.status})`;
    return;
  }

  const data = await resp.json();
  const token = data.access_token;

  const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${wsProtocol}://${location.host}/ws/admin?token=${token}`);

  ws.onopen = () => { statusEl().textContent = 'Conectado — aguardando GPS...'; };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    // Formato real enviado por broadcast_posicao() em websocket_manager.py:
    // { tipo: "posicao_gps", motoboy_id, latitude, longitude, velocidade, pedido_id, timestamp }
    if (msg.tipo === 'posicao_gps') {
      atualizarMarcador(msg);
    } else if (msg.tipo === 'motoboy_offline') {
      removerMarcador(msg.motoboy_id);
    }
  };

  ws.onerror = () => { statusEl().textContent = 'Erro no WebSocket'; };
  ws.onclose = () => { statusEl().textContent = 'Desconectado'; };
}

function atualizarMarcador(msg) {
  const { motoboy_id, latitude, longitude, velocidade, pedido_id } = msg;
  const pos = [latitude, longitude];

  if (marcadoresMotoboys[motoboy_id]) {
    marcadoresMotoboys[motoboy_id].setLatLng(pos);
  } else {
    marcadoresMotoboys[motoboy_id] = L.marker(pos)
      .addTo(map)
      .bindPopup(`Motoboy #${motoboy_id}`);
  }

  marcadoresMotoboys[motoboy_id].getPopup().setContent(
    `Motoboy #${motoboy_id}` +
    (velocidade != null ? ` — ${velocidade.toFixed(1)} km/h` : '') +
    (pedido_id ? `<br>Pedido: ${pedido_id}` : '<br><em>Sem pedido ativo</em>')
  );
}

function removerMarcador(motoboy_id) {
  const marcador = marcadoresMotoboys[motoboy_id];
  if (marcador) {
    map.removeLayer(marcador);
    delete marcadoresMotoboys[motoboy_id];
  }
}
