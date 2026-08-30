// Centro do Poranga — mesma coordenada real usada no painel admin
const CENTRO_PORANGA = [-3.110897, -58.458911];
const RAIO_KM = 3;

let token = localStorage.getItem('cliente_token') || null;
let nomeUsuario = localStorage.getItem('cliente_nome') || null;

let mapPicker = null, marcadorPicker = null, coordEndereco = null;
let mapPickerOrigem = null, marcadorOrigem = null, coordOrigem = null;
let mapAcompanhar = null, marcadorMotoboyMap = null, marcadorEnderecoMap = null, marcadorOrigemMap = null;
let pedidoAtualId = null;
let wsAcompanhar = null;
let pollingInterval = null;

function mostrarMsg(texto) {
  document.getElementById('msg').textContent = texto;
  setTimeout(() => { document.getElementById('msg').textContent = ''; }, 5000);
}

function mostrarAba(aba) {
  document.getElementById('aba-login').classList.toggle('hidden', aba !== 'login');
  document.getElementById('aba-cadastro').classList.toggle('hidden', aba !== 'cadastro');
}

// --- AUTENTICAÇÃO ----------------------------------------------------------

async function fazerCadastro() {
  const nome = document.getElementById('cad-nome').value;
  const telefone = document.getElementById('cad-telefone').value;
  const senha = document.getElementById('cad-senha').value;

  try {
    const resp = await fetch('/auth/registrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, telefone, senha, tipo: 'cliente' })
    });
    const data = await resp.json();
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao cadastrar'); return; }
    entrarComToken(data.access_token, data.nome);
  } catch (e) {
    mostrarMsg('Erro de rede ao cadastrar');
  }
}

async function fazerLogin() {
  const telefone = document.getElementById('login-telefone').value;
  const senha = document.getElementById('login-senha').value;

  try {
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefone, senha })
    });
    const data = await resp.json();
    if (!resp.ok) { mostrarMsg(data.detail || 'Telefone ou senha incorretos'); return; }
    entrarComToken(data.access_token, data.nome);
  } catch (e) {
    mostrarMsg('Erro de rede ao entrar');
  }
}

function entrarComToken(novoToken, nome) {
  token = novoToken;
  nomeUsuario = nome;
  localStorage.setItem('cliente_token', token);
  localStorage.setItem('cliente_nome', nome);
  document.getElementById('auth-section').classList.add('hidden');
  document.getElementById('logado-section').classList.remove('hidden');
  document.getElementById('saudacao').textContent = `Olá, ${nome}!`;
  carregarEnderecos();
}

function sair() {
  localStorage.removeItem('cliente_token');
  localStorage.removeItem('cliente_nome');
  token = null;
  location.reload();
}

// Helper: toda chamada autenticada usa isso
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

// --- ENDEREÇOS ---------------------------------------------------------------

async function carregarEnderecos() {
  try {
    const resp = await apiFetch('/enderecos/');
    const enderecos = await resp.json();
    const lista = document.getElementById('lista-enderecos');

    if (enderecos.length === 0) {
      lista.innerHTML = '<p><small>Nenhum endereço cadastrado ainda.</small></p>';
      return;
    }

    lista.innerHTML = enderecos.map(e => `
      <div style="border:1px solid #eee;padding:8px;border-radius:4px;margin-bottom:6px;">
        <strong>${e.apelido}</strong> — ${e.logradouro}, ${e.numero}<br>
        <small>${e.bairro}, ${e.cidade}/${e.estado}</small><br>
        <button style="width:auto;padding:4px 10px;font-size:12px;margin-top:4px;" onclick="escolherEnderecoParaPedido('${e.id}')">Pedir aqui</button>
        <button style="width:auto;padding:4px 10px;font-size:12px;margin-top:4px;background:#dc2626;" onclick="removerEndereco('${e.id}')">Remover</button>
      </div>
    `).join('');
  } catch (e) { /* já tratado no apiFetch */ }
}

function mostrarFormEndereco() {
  document.getElementById('form-endereco').classList.remove('hidden');
  if (!mapPicker) {
    mapPicker = L.map('map-picker').setView(CENTRO_PORANGA, 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
    }).addTo(mapPicker);
    L.circle(CENTRO_PORANGA, { radius: RAIO_KM * 1000, color: '#3388ff', fillOpacity: 0.05 }).addTo(mapPicker);
    mapPicker.on('click', (e) => {
      coordEndereco = e.latlng;
      if (marcadorPicker) mapPicker.removeLayer(marcadorPicker);
      marcadorPicker = L.marker(coordEndereco).addTo(mapPicker);
    });
  }
  setTimeout(() => mapPicker.invalidateSize(), 100);
}

function esconderFormEndereco() {
  document.getElementById('form-endereco').classList.add('hidden');
}

async function salvarEndereco() {
  if (!coordEndereco) { mostrarMsg('Clica no mapa pra marcar o local'); return; }

  const payload = {
    apelido: document.getElementById('end-apelido').value || 'Casa',
    logradouro: document.getElementById('end-logradouro').value,
    numero: document.getElementById('end-numero').value,
    bairro: document.getElementById('end-bairro').value,
    complemento: document.getElementById('end-complemento').value || null,
    referencia: document.getElementById('end-referencia').value || null,
    cidade: document.getElementById('end-cidade').value || 'Itacoatiara',
    estado: document.getElementById('end-estado').value || 'AM',
    latitude: coordEndereco.lat,
    longitude: coordEndereco.lng
  };

  try {
    const resp = await apiFetch('/enderecos/', { method: 'POST', body: JSON.stringify(payload) });
    const data = await resp.json();
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao salvar endereço'); return; }
    mostrarMsg('Endereço salvo!');
    esconderFormEndereco();
    carregarEnderecos();
  } catch (e) { /* já tratado */ }
}

async function removerEndereco(id) {
  try {
    await apiFetch(`/enderecos/${id}`, { method: 'DELETE' });
    carregarEnderecos();
  } catch (e) { /* já tratado */ }
}

// --- PEDIDO ------------------------------------------------------------------

let enderecoEscolhidoId = null;

function escolherEnderecoParaPedido(enderecoId) {
  enderecoEscolhidoId = enderecoId;
  document.getElementById('pedido-section').classList.remove('hidden');
  document.getElementById('acompanhar-section').classList.add('hidden');

  if (!mapPickerOrigem) {
    mapPickerOrigem = L.map('map-picker-origem').setView(CENTRO_PORANGA, 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
    }).addTo(mapPickerOrigem);
    L.circle(CENTRO_PORANGA, { radius: RAIO_KM * 1000, color: '#3388ff', fillOpacity: 0.05 }).addTo(mapPickerOrigem);
    mapPickerOrigem.on('click', (e) => {
      coordOrigem = e.latlng;
      if (marcadorOrigem) mapPickerOrigem.removeLayer(marcadorOrigem);
      marcadorOrigem = L.marker(coordOrigem).addTo(mapPickerOrigem);
    });
  }
  setTimeout(() => mapPickerOrigem.invalidateSize(), 100);
  window.scrollTo({ top: document.getElementById('pedido-section').offsetTop, behavior: 'smooth' });
}

async function criarPedido() {
  if (!enderecoEscolhidoId) { mostrarMsg('Escolha um endereço primeiro'); return; }
  if (!coordOrigem) { mostrarMsg('Clica no mapa pra marcar o estabelecimento'); return; }

  const valor = parseFloat(document.getElementById('ped-valor').value);
  if (!valor || valor <= 0) { mostrarMsg('Informe um valor válido'); return; }

  const payload = {
    endereco_id: enderecoEscolhidoId,
    origem_nome: document.getElementById('ped-origem-nome').value,
    origem_latitude: coordOrigem.lat,
    origem_longitude: coordOrigem.lng,
    itens_descricao: document.getElementById('ped-itens').value,
    valor_total: valor,
    taxa_entrega: parseFloat(document.getElementById('ped-taxa').value) || 0,
    observacoes: document.getElementById('ped-obs').value || null
  };

  try {
    const resp = await apiFetch('/pedidos/', { method: 'POST', body: JSON.stringify(payload) });
    const data = await resp.json();
    if (!resp.ok) { mostrarMsg(data.detail || 'Erro ao criar pedido'); return; }
    mostrarMsg('Pedido criado! Aguardando um motoboy aceitar...');
    iniciarAcompanhamento(data);
  } catch (e) { /* já tratado */ }
}

// --- ACOMPANHAMENTO ------------------------------------------------------------

const CORES_STATUS = {
  PENDENTE: '#f59e0b', ACEITO: '#3b82f6', EM_ROTA: '#3b82f6',
  ENTREGUE: '#16a34a', CANCELADO: '#dc2626'
};

function iniciarAcompanhamento(pedido) {
  pedidoAtualId = pedido.id;
  document.getElementById('pedido-section').classList.add('hidden');
  document.getElementById('acompanhar-section').classList.remove('hidden');

  if (!mapAcompanhar) {
    mapAcompanhar = L.map('map-acompanhar').setView(CENTRO_PORANGA, 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
    }).addTo(mapAcompanhar);
    L.circle(CENTRO_PORANGA, { radius: RAIO_KM * 1000, color: '#3388ff', fillOpacity: 0.05 }).addTo(mapAcompanhar);
  }
  setTimeout(() => mapAcompanhar.invalidateSize(), 100);

  marcadorOrigemMap = L.marker([pedido.origem_latitude, pedido.origem_longitude], {
    title: 'Estabelecimento'
  }).addTo(mapAcompanhar).bindPopup(`📍 ${pedido.origem_nome}`);

  atualizarStatusVisual(pedido.status);
  conectarWebSocketPedido(pedido.id);

  if (pollingInterval) clearInterval(pollingInterval);
  pollingInterval = setInterval(() => verificarStatusPedido(pedido.id), 5000);
}

function atualizarStatusVisual(status) {
  const el = document.getElementById('pedido-status');
  el.textContent = status;
  el.style.background = CORES_STATUS[status] || '#6b7280';
}

async function verificarStatusPedido(pedidoId) {
  try {
    const resp = await apiFetch(`/pedidos/${pedidoId}`);
    const pedido = await resp.json();
    atualizarStatusVisual(pedido.status);
    if (pedido.status === 'ENTREGUE' || pedido.status === 'CANCELADO') {
      clearInterval(pollingInterval);
      if (wsAcompanhar) wsAcompanhar.close();
    }
  } catch (e) { /* já tratado */ }
}

function conectarWebSocketPedido(pedidoId) {
  const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
  wsAcompanhar = new WebSocket(`${wsProtocol}://${location.host}/ws/cliente/${pedidoId}?token=${token}`);

  wsAcompanhar.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.tipo === 'posicao_gps') {
      const pos = [msg.latitude, msg.longitude];
      if (marcadorMotoboyMap) {
        marcadorMotoboyMap.setLatLng(pos);
      } else {
        marcadorMotoboyMap = L.marker(pos).addTo(mapAcompanhar).bindPopup('🛵 Seu motoboy');
      }
    }
  };
}

function voltarParaNovoPedido() {
  document.getElementById('acompanhar-section').classList.add('hidden');
  document.getElementById('enderecos-section').classList.remove('hidden');
  if (wsAcompanhar) wsAcompanhar.close();
  if (pollingInterval) clearInterval(pollingInterval);
  carregarEnderecos();
}

// --- INICIALIZAÇÃO -------------------------------------------------------------

if (token && nomeUsuario) {
  document.getElementById('auth-section').classList.add('hidden');
  document.getElementById('logado-section').classList.remove('hidden');
  document.getElementById('saudacao').textContent = `Olá, ${nomeUsuario}!`;
  carregarEnderecos();
}
