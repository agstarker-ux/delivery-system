const CENTRO_PORANGA = [-3.115, -58.435];
const RAIO_KM = 3;

const SEQUENCIA_STATUS = [
  'aceito',
  'a_caminho_coleta',
  'coletado',
  'a_caminho_entrega',
  'entregue'
];

const CORES_STATUS = {
  pendente: '#f59e0b',
  aceito: '#3b82f6',
  a_caminho_coleta: '#3b82f6',
  coletado: '#3b82f6',
  a_caminho_entrega: '#3b82f6',
  entregue: '#16a34a',
  cancelado: '#dc2626'
};

let token = null;
let motoboyId = null;
let motoboyNome = null;
let statusMotoboy = 'offline';
let pedidoAtual = null;
let ws = null;
let watchId = null;
let ultimoEnvioGps = 0;
let pollingPendentes = null;
let mapa = null;
let marcadorOrigemMapa = null;
let marcadorMotoboyMapa = null;

function escapeHtml(valor) {
  return String(valor ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function mostrarMsg(texto, tipoErro) {
  const el = document.getElementById('mensagem-flutuante');
  el.textContent = texto;
  el.classList.toggle('erro', tipoErro !== false);
  el.classList.add('visivel');
  clearTimeout(window.__timeoutMsg);
  window.__timeoutMsg = setTimeout(() => { el.classList.remove('visivel'); }, 3500);
}

// --- AUTENTICAÇÃO ----------------------------------------------------------

async function fazerLogin() {
  const telefone = document.getElementById('login-telefone').value;
  const senha = document.getElementById('login-senha').value;

  try {
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefone, senha })
    });
    const data = await lerJsonSeguro(resp);
    if (!resp.ok) { mostrarMsg(data.detail || 'Telefone ou senha incorretos'); return; }
    if (data.tipo !== 'motoboy') { mostrarMsg('Esta conta não é de motoboy.'); return; }

    token = data.access_token;
    motoboyNome = data.nome;

    const perfilResp = await fetch('/motoboys/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const perfil = await perfilResp.json();
    if (!perfilResp.ok) {
      mostrarMsg(perfil.detail || 'Perfil de motoboy não encontrado');
      token = null;
      return;
    }
    motoboyId = perfil.id;
    statusMotoboy = perfil.status || 'offline';

    document.getElementById('auth-section').classList.add('hidden');
    document.getElementById('logado-section').classList.remove('hidden');
    document.getElementById('saudacao').textContent = `Olá, ${motoboyNome}!`;

    atualizarBadgeStatus();
    await carregarPedidoAtual();
  } catch (e) {
    mostrarMsg('Erro de rede ao entrar');
  }
}

function sair() {
  pararTudo();
  token = null;
  location.reload();
}

async function apiFetch(url, opcoes = {}) {
  opcoes.headers = opcoes.headers || {};
  opcoes.headers['Authorization'] = `Bearer ${token}`;
  if (opcoes.body) opcoes.headers['Content-Type'] = 'application/json';
  const resp = await fetch(url, opcoes);
  if (resp.status === 401) {
    mostrarMsg('Sessão expirada, faça login de novo');
    sair();
    throw new Error('401');
  }
  return resp;
}

async function lerJsonSeguro(resp, fallback = {}) {
  const contentType = resp.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return fallback;
  try {
    return await resp.json();
  } catch (e) {
    return fallback;
  }
}


async function obterTokenWs() {
  const resp = await apiFetch('/auth/ws-token', { method: 'POST' });
  const data = await lerJsonSeguro(resp);
  return data.ws_token;
}

// --- STATUS DISPONÍVEL / OFFLINE -------------------------------------------

function atualizarBadgeStatus() {
  const badge = document.getElementById('status-badge');
  const labels = { offline: 'Offline', disponivel: 'Disponível', em_entrega: 'Em entrega' };
  badge.textContent = labels[statusMotoboy] || statusMotoboy;
  badge.style.background = statusMotoboy === 'disponivel' ? '#16a34a' : statusMotoboy === 'em_entrega' ? '#3b82f6' : '#6b7280';

  const btn = document.getElementById('btn-alternar-status');
  const emEntrega = statusMotoboy === 'em_entrega';
  btn.disabled = emEntrega;
  btn.textContent = emEntrega ? 'Entrega em andamento' : statusMotoboy === 'disponivel' ? 'Ficar offline' : 'Ficar disponível';
  btn.className = emEntrega ? 'secundario' : statusMotoboy === 'disponivel' ? 'perigo' : 'sucesso';
}

async function carregarPedidoAtual() {
  try {
    const resp = await apiFetch('/pedidos/me/atual');
    if (!resp.ok) return;
    const pedido = await lerJsonSeguro(resp, null);
    if (!pedido) return;

    pedidoAtual = pedido;
    statusMotoboy = 'em_entrega';
    atualizarBadgeStatus();
    document.getElementById('pendentes-section').classList.add('hidden');
    document.getElementById('pedido-atual-section').classList.remove('hidden');
    renderizarPedidoAtual();
    await conectarWebSocketGPS();
    iniciarEnvioGPS();
  } catch (e) {
    /* restauração opcional da sessão */
  }
}

async function alternarStatus() {
  if (statusMotoboy === 'em_entrega') {
    mostrarMsg('Finalize ou cancele a entrega atual antes de alterar a disponibilidade.');
    return;
  }

  const novoStatus = statusMotoboy === 'disponivel' ? 'offline' : 'disponivel';

  try {
    const resp = await apiFetch('/motoboys/me/status', {
      method: 'PATCH',
      body: JSON.stringify({ status: novoStatus })
    });
    const data = await lerJsonSeguro(resp);
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao mudar status'); return; }

    statusMotoboy = novoStatus;
    atualizarBadgeStatus();

    if (statusMotoboy === 'disponivel' && !pedidoAtual) {
      document.getElementById('pendentes-section').classList.remove('hidden');
      carregarPendentes();
      pollingPendentes = setInterval(carregarPendentes, 8000);
    } else {
      document.getElementById('pendentes-section').classList.add('hidden');
      if (pollingPendentes) { clearInterval(pollingPendentes); pollingPendentes = null; }
    }
  } catch (e) { /* já tratado */ }
}

// --- PEDIDOS PENDENTES ------------------------------------------------------

async function carregarPendentes() {
  if (pedidoAtual) return;

  try {
    const resp = await apiFetch('/pedidos/pendentes');
    const pedidos = await lerJsonSeguro(resp, []);
    if (!Array.isArray(pedidos)) {
      mostrarMsg('Resposta inválida do servidor ao carregar pedidos.');
      return;
    }
    renderizarPendentes(pedidos);
  } catch (e) { /* já tratado */ }
}

function renderizarPendentes(pedidos) {
  const lista = document.getElementById('lista-pendentes');

  if (!pedidos || pedidos.length === 0) {
    lista.innerHTML = '<p class="estado-vazio"><small>Nenhum pedido pendente no momento.</small></p>';
    return;
  }

  lista.innerHTML = pedidos.map(p => `
    <div class="pedido-item" data-pedido-id="${escapeHtml(p.id)}">
      <strong>${escapeHtml(p.origem_nome || 'Estabelecimento')}</strong><br>
      <small>${escapeHtml(p.itens_descricao || '')}</small><br>
      <small>Valor: R$ ${Number(p.valor_total || 0).toFixed(2)} | Taxa: R$ ${Number(p.taxa_entrega || 0).toFixed(2)}</small><br>
      <button type="button" class="js-aceitar-pedido">Aceitar</button>
    </div>
  `).join('');

  lista.querySelectorAll('.js-aceitar-pedido').forEach((botao) => {
    botao.addEventListener('click', () => {
      const item = botao.closest('[data-pedido-id]');
      if (item) aceitarPedido(item.dataset.pedidoId);
    });
  });
}

async function aceitarPedido(pedidoId) {
  try {
    const resp = await apiFetch(`/pedidos/${pedidoId}/aceitar`, { method: 'POST' });
    const data = await lerJsonSeguro(resp);
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao aceitar pedido'); return; }

    pedidoAtual = data;
    statusMotoboy = 'em_entrega';
    atualizarBadgeStatus();

    if (pollingPendentes) {
      clearInterval(pollingPendentes);
      pollingPendentes = null;
    }
    document.getElementById('pendentes-section').classList.add('hidden');
    document.getElementById('pedido-atual-section').classList.remove('hidden');

    renderizarPedidoAtual();
    await conectarWebSocketGPS();
    iniciarEnvioGPS();
  } catch (e) { /* já tratado */ }
}

// --- PEDIDO ATUAL / AVANÇO DE STATUS ---------------------------------------

function renderizarPedidoAtual() {
  document.getElementById('pa-origem').textContent = pedidoAtual.origem_nome || 'Estabelecimento';
  document.getElementById('pa-itens').textContent = pedidoAtual.itens_descricao || '';
  document.getElementById('pa-valor').textContent = `Valor: R$ ${Number(pedidoAtual.valor_total || 0).toFixed(2)}`;

  const badge = document.getElementById('pa-status');
  badge.textContent = pedidoAtual.status;
  badge.style.background = CORES_STATUS[pedidoAtual.status] || '#6b7280';

  const indiceAtual = SEQUENCIA_STATUS.indexOf(pedidoAtual.status);
  const btnAvancar = document.getElementById('btn-avancar');
  if (indiceAtual === SEQUENCIA_STATUS.length - 1) {
    btnAvancar.disabled = true;
    btnAvancar.textContent = 'Pedido entregue';
  } else {
    btnAvancar.disabled = false;
    btnAvancar.textContent = `Avançar para: ${SEQUENCIA_STATUS[indiceAtual + 1]}`;
  }

  inicializarMapaPedido();
}

function inicializarMapaPedido() {
  const lat = pedidoAtual.origem_latitude ?? CENTRO_PORANGA[0];
  const lon = pedidoAtual.origem_longitude ?? CENTRO_PORANGA[1];

  if (!mapa) {
    mapa = L.map('mapa').setView([lat, lon], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
    }).addTo(mapa);
    L.circle(CENTRO_PORANGA, { radius: RAIO_KM * 1000, color: '#3388ff', fillOpacity: 0.05 }).addTo(mapa);
  } else {
    mapa.setView([lat, lon], 14);
  }

  if (marcadorOrigemMapa) mapa.removeLayer(marcadorOrigemMapa);
  marcadorOrigemMapa = L.marker([lat, lon]).addTo(mapa).bindPopup(`📍 ${escapeHtml(pedidoAtual.origem_nome || 'Estabelecimento')}`);

  setTimeout(() => mapa.invalidateSize(), 100);
}

async function avancarStatus() {
  const indiceAtual = SEQUENCIA_STATUS.indexOf(pedidoAtual.status);
  const proximoStatus = SEQUENCIA_STATUS[indiceAtual + 1];
  if (!proximoStatus) return;

  try {
    const resp = await apiFetch(`/pedidos/${pedidoAtual.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: proximoStatus })
    });
    const data = await lerJsonSeguro(resp);
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao avançar status'); return; }

    pedidoAtual = data;
    renderizarPedidoAtual();

    if (pedidoAtual.status === 'entregue') {
      finalizarPedido();
    }
  } catch (e) { /* já tratado */ }
}

async function cancelarPedido() {
  if (!confirm('Cancelar este pedido?')) return;

  try {
    const resp = await apiFetch(`/pedidos/${pedidoAtual.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'cancelado' })
    });
    if (!resp.ok) { const data = await lerJsonSeguro(resp); mostrarMsg(data.detail || 'Erro ao cancelar'); return; }
    finalizarPedido();
  } catch (e) { /* já tratado */ }
}

function finalizarPedido() {
  pararEnvioGPS();
  fecharWebSocketGPS();

  pedidoAtual = null;
  statusMotoboy = 'disponivel';
  atualizarBadgeStatus();
  document.getElementById('pedido-atual-section').classList.add('hidden');

  if (statusMotoboy === 'disponivel') {
    document.getElementById('pendentes-section').classList.remove('hidden');
    carregarPendentes();
    pollingPendentes = setInterval(carregarPendentes, 8000);
  }
}

// --- WEBSOCKET GPS (mesmo padrão de simular_gps.py) -------------------------

async function conectarWebSocketGPS() {
  if (ws) return;

  let wsToken;

  try {
    wsToken = await obterTokenWs();
  } catch (e) {
    return;
  }

  const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${wsProtocol}://${location.host}/ws/motoboy/${motoboyId}?token=${wsToken}`);

  ws.onopen = () => console.log('WebSocket GPS conectado.');
  ws.onmessage = (event) => {
    try {
      const resposta = JSON.parse(event.data);
      if (resposta.erro) mostrarMsg(resposta.erro);
    } catch (e) {
      console.warn('Resposta inesperada do servidor GPS');
    }
  };
  ws.onerror = (err) => console.error('Erro WebSocket GPS:', err);
  ws.onclose = () => { console.log('WebSocket GPS fechado.'); ws = null; };
}

function fecharWebSocketGPS() {
  if (ws) { ws.close(); ws = null; }
}

function iniciarEnvioGPS() {
  if (!navigator.geolocation) {
    mostrarMsg('Geolocalização não suportada neste navegador.');
    return;
  }

  watchId = navigator.geolocation.watchPosition(
    (posicao) => {
      const payload = {
        latitude: posicao.coords.latitude,
        longitude: posicao.coords.longitude,
        velocidade: posicao.coords.speed || null,
        precisao: posicao.coords.accuracy || null,
        pedido_id: pedidoAtual ? pedidoAtual.id : null
      };

      const agora = Date.now();
      if (ws && ws.readyState === WebSocket.OPEN && agora - ultimoEnvioGps >= 1000) {
        ws.send(JSON.stringify(payload));
        ultimoEnvioGps = agora;
      }

      atualizarMarcadorMotoboyNoMapa(posicao.coords.latitude, posicao.coords.longitude);
    },
    (erro) => console.error('Erro ao obter posição GPS:', erro),
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  );
}

function pararEnvioGPS() {
  ultimoEnvioGps = 0;
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
}

function atualizarMarcadorMotoboyNoMapa(lat, lon) {
  if (!mapa) return;
  const pos = [lat, lon];
  if (marcadorMotoboyMapa) {
    marcadorMotoboyMapa.setLatLng(pos);
  } else {
    marcadorMotoboyMapa = L.marker(pos).addTo(mapa).bindPopup('🛵 Você está aqui');
  }
}

function pararTudo() {
  pararEnvioGPS();
  fecharWebSocketGPS();
  if (pollingPendentes) clearInterval(pollingPendentes);
  pollingPendentes = null;
}
