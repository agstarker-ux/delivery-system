const CENTRO_PORANGA = [-3.110897, -58.458911];
const RAIO_KM = 3;

let token = localStorage.getItem('cliente_token') || null;
let nomeUsuario = localStorage.getItem('cliente_nome') || null;

let mapPicker = null;
let marcadorPicker = null;
let coordEndereco = null;

let mapPickerOrigem = null;
let marcadorOrigem = null;
let coordOrigem = null;

let mapAcompanhar = null;
let marcadorMotoboyMap = null;
let marcadorEnderecoMap = null;
let marcadorOrigemMap = null;

let pedidoAtualId = null;
let wsAcompanhar = null;
let pollingInterval = null;

let enderecoEscolhidoId = null;
let pedidoEtapaAtual = 1;


/* -------------------------------------------------------------------------- */
/* MENSAGENS                                                                  */
/* -------------------------------------------------------------------------- */

function mostrarMsg(texto, tipoErro = true) {
  const el = document.getElementById('mensagem-flutuante');

  if (!el) {
    alert(texto);
    return;
  }

  el.textContent = texto;
  el.classList.toggle('erro', tipoErro !== false);
  el.classList.add('visivel');

  clearTimeout(window.__timeoutMsg);

  window.__timeoutMsg = setTimeout(() => {
    el.classList.remove('visivel');
  }, 3500);
}


/* -------------------------------------------------------------------------- */
/* AUTENTICAÇÃO                                                               */
/* -------------------------------------------------------------------------- */

function mostrarAba(aba) {
  document
    .getElementById('aba-login')
    .classList.toggle('hidden', aba !== 'login');

  document
    .getElementById('aba-cadastro')
    .classList.toggle('hidden', aba !== 'cadastro');

  document
    .getElementById('btn-aba-login')
    .classList.toggle('ativa', aba === 'login');

  document
    .getElementById('btn-aba-cadastro')
    .classList.toggle('ativa', aba === 'cadastro');
}


async function fazerCadastro() {
  const nome = document.getElementById('cad-nome').value.trim();
  const telefone = document.getElementById('cad-telefone').value.trim();
  const senha = document.getElementById('cad-senha').value;

  if (!nome || !telefone || !senha) {
    mostrarMsg('Preencha todos os campos.');
    return;
  }

  try {
    const resp = await fetch('/auth/registrar', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        nome,
        telefone,
        senha,
        tipo: 'cliente'
      })
    });

    const data = await resp.json();

    if (!resp.ok) {
      mostrarMsg(data.detail || 'Erro ao cadastrar');
      return;
    }

    entrarComToken(data.access_token, data.nome);

  } catch (e) {
    mostrarMsg('Erro de rede ao cadastrar');
  }
}


async function fazerLogin() {
  const telefone = document.getElementById('login-telefone').value.trim();
  const senha = document.getElementById('login-senha').value;

  if (!telefone || !senha) {
    mostrarMsg('Informe telefone e senha.');
    return;
  }

  try {
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        telefone,
        senha
      })
    });

    const data = await resp.json();

    if (!resp.ok) {
      mostrarMsg(data.detail || 'Telefone ou senha incorretos');
      return;
    }

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

  document
    .getElementById('auth-section')
    .classList.add('hidden');

  document
    .getElementById('logado-section')
    .classList.remove('hidden');

  document.getElementById('saudacao').textContent =
    `Olá, ${nome}!`;

  carregarEnderecos();
  carregarPedidoAtivo();
}


function sair() {
  if (wsAcompanhar) wsAcompanhar.close();
  if (pollingInterval) clearInterval(pollingInterval);
  wsAcompanhar = null;
  pollingInterval = null;
  localStorage.removeItem('cliente_token');
  localStorage.removeItem('cliente_nome');

  token = null;
  nomeUsuario = null;

  location.reload();
}


/* -------------------------------------------------------------------------- */
/* API                                                                        */
/* -------------------------------------------------------------------------- */

async function apiFetch(url, opcoes = {}) {
  opcoes.headers = opcoes.headers || {};

  opcoes.headers['Authorization'] = `Bearer ${token}`;

  if (opcoes.body) {
    opcoes.headers['Content-Type'] = 'application/json';
  }

  const resp = await fetch(url, opcoes);

  if (resp.status === 401) {
    mostrarMsg('Sessão expirada, faça login de novo');
    sair();
    throw new Error('401');
  }

  return resp;
}


async function obterTokenWs() {
  const resp = await apiFetch('/auth/ws-token', { method: 'POST' });
  const data = await resp.json();
  return data.ws_token;
}


/* -------------------------------------------------------------------------- */
/* ENDEREÇOS                                                                   */
/* -------------------------------------------------------------------------- */

async function carregarEnderecos() {
  try {
    const resp = await apiFetch('/enderecos/');
    const enderecos = await resp.json();

    const lista = document.getElementById('lista-enderecos');

    if (enderecos.length === 0) {
      lista.innerHTML = `
        <div class="estado-vazio">
          <div style="font-size:28px;margin-bottom:8px;">📍</div>
          <div>Você ainda não tem um endereço.</div>
          <small>Adicione onde deseja receber seus pedidos.</small>
        </div>
      `;
      return;
    }

    lista.innerHTML = enderecos.map(e => `
      <div class="linha-endereco" data-endereco-id="${escapeHtml(e.id)}">

        <div class="linha-endereco-topo">
          <strong class="linha-endereco-apelido">
            ${escapeHtml(e.apelido)}
          </strong>
        </div>

        <div class="linha-endereco-texto">
          ${escapeHtml(e.logradouro)}, ${escapeHtml(e.numero)}
          <br>
          ${escapeHtml(e.bairro)}, ${escapeHtml(e.cidade)}/${escapeHtml(e.estado)}
        </div>

        <div class="linha-endereco-acoes">

          <button
            class="pequeno"
            onclick="escolherEnderecoParaPedido('${e.id}')"
          >
            Pedir aqui
          </button>

          <button
            class="pequeno perigo"
            onclick="removerEndereco('${e.id}')"
          >
            Remover
          </button>

        </div>

      </div>
    `).join('');

  } catch (e) {
    /* já tratado pelo apiFetch */
  }
}


function mostrarFormEndereco() {
  document
    .getElementById('form-endereco')
    .classList.remove('hidden');

  if (!mapPicker) {

    mapPicker = L
      .map('map-picker')
      .setView(CENTRO_PORANGA, 16);

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }
    ).addTo(mapPicker);

    L.circle(
      CENTRO_PORANGA,
      {
        radius: RAIO_KM * 1000,
        color: '#3388ff',
        fillOpacity: 0.05
      }
    ).addTo(mapPicker);

    mapPicker.on('click', (e) => {

      coordEndereco = e.latlng;

      if (marcadorPicker) {
        mapPicker.removeLayer(marcadorPicker);
      }

      marcadorPicker = L
        .marker(coordEndereco)
        .addTo(mapPicker);
    });
  }

  setTimeout(() => {
    mapPicker.invalidateSize();
  }, 100);
}


function esconderFormEndereco() {
  document
    .getElementById('form-endereco')
    .classList.add('hidden');
}


async function salvarEndereco() {

  if (!coordEndereco) {
    mostrarMsg('Marque o local de entrega no mapa.');
    return;
  }

  const payload = {
    apelido:
      document.getElementById('end-apelido').value.trim() ||
      'Casa',

    logradouro:
      document.getElementById('end-logradouro').value.trim(),

    numero:
      document.getElementById('end-numero').value.trim(),

    bairro:
      document.getElementById('end-bairro').value.trim(),

    complemento:
      document.getElementById('end-complemento').value.trim() ||
      null,

    referencia:
      document.getElementById('end-referencia').value.trim() ||
      null,

    cidade:
      document.getElementById('end-cidade').value.trim() ||
      'Itacoatiara',

    estado:
      document.getElementById('end-estado').value.trim() ||
      'AM',

    latitude: coordEndereco.lat,
    longitude: coordEndereco.lng
  };

  if (!payload.logradouro || !payload.numero || !payload.bairro) {
    mostrarMsg('Informe rua, número e bairro.');
    return;
  }

  try {

    const resp = await apiFetch(
      '/enderecos/',
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );

    const data = await resp.json();

    if (!resp.ok) {
      mostrarMsg(
        data.detail ||
        'Erro ao salvar endereço'
      );
      return;
    }

    mostrarMsg('Endereço salvo!', false);

    esconderFormEndereco();

    carregarEnderecos();

  } catch (e) {
    /* já tratado */
  }
}


async function removerEndereco(id) {
  if (!confirm('Remover este endereço?')) return;

  try {
    const resp = await apiFetch(`/enderecos/${id}`, { method: 'DELETE' });
    if (!resp.ok) {
      const data = await resp.json();
      mostrarMsg(data.detail || 'Não foi possível remover o endereço.');
      return;
    }

    if (enderecoEscolhidoId === id) enderecoEscolhidoId = null;
    mostrarMsg('Endereço removido.', false);
    await carregarEnderecos();
  } catch (e) {
    /* já tratado */
  }
}


/* -------------------------------------------------------------------------- */
/* WIZARD DO PEDIDO                                                           */
/* -------------------------------------------------------------------------- */

function escolherEnderecoParaPedido(enderecoId) {

  enderecoEscolhidoId = enderecoId;

  document
    .getElementById('pedido-section')
    .classList.remove('hidden');

  document
    .getElementById('acompanhar-section')
    .classList.add('hidden');

  iniciarWizardPedido();

  setTimeout(() => {

    if (mapPickerOrigem) {
      mapPickerOrigem.invalidateSize();
    }

  }, 150);

  window.scrollTo({
    top:
      document.getElementById('pedido-section').offsetTop - 10,
    behavior: 'smooth'
  });
}


function iniciarWizardPedido() {

  pedidoEtapaAtual = 1;

  atualizarEtapaPedido(1);

  if (!mapPickerOrigem) {

    mapPickerOrigem = L
      .map('map-picker-origem')
      .setView(CENTRO_PORANGA, 16);

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }
    ).addTo(mapPickerOrigem);

    L.circle(
      CENTRO_PORANGA,
      {
        radius: RAIO_KM * 1000,
        color: '#3388ff',
        fillOpacity: 0.05
      }
    ).addTo(mapPickerOrigem);

    mapPickerOrigem.on('click', (e) => {

      coordOrigem = e.latlng;

      if (marcadorOrigem) {
        mapPickerOrigem.removeLayer(marcadorOrigem);
      }

      marcadorOrigem = L
        .marker(coordOrigem)
        .addTo(mapPickerOrigem);
    });
  }
}


function atualizarEtapaPedido(etapa) {

  pedidoEtapaAtual = etapa;

  for (let i = 1; i <= 3; i++) {

    const passo = document.getElementById(
      `pedido-passo-${i}`
    );

    if (passo) {
      passo.classList.toggle(
        'hidden',
        i !== etapa
      );
    }
  }

  const barra =
    document.getElementById('progresso-barra');

  if (barra) {
    barra.style.width =
      `${(etapa / 3) * 100}%`;
  }

  const texto =
    document.getElementById('pedido-etapa-texto');

  if (texto) {
    texto.textContent =
      `Passo ${etapa} de 3`;
  }

  if (etapa === 1 && mapPickerOrigem) {

    setTimeout(() => {
      mapPickerOrigem.invalidateSize();
    }, 100);
  }

  if (etapa === 3) {
    montarResumoPedido();
  }
}


function irParaPassoPedido(etapa) {

  if (etapa === 2) {

    if (!coordOrigem) {
      mostrarMsg(
        'Marque no mapa onde fica o estabelecimento.'
      );
      return;
    }

    const origemNome =
      document
        .getElementById('ped-origem-nome')
        .value
        .trim();

    if (!origemNome) {
      mostrarMsg(
        'Informe o nome do estabelecimento.'
      );
      return;
    }
  }


  if (etapa === 3) {

    const itens =
      document
        .getElementById('ped-itens')
        .value
        .trim();

    const valor =
      parseFloat(
        document.getElementById('ped-valor').value
      );

    if (!itens) {
      mostrarMsg(
        'Informe o que você quer comprar.'
      );
      return;
    }

    if (!valor || valor <= 0) {
      mostrarMsg(
        'Informe um valor válido para os produtos.'
      );
      return;
    }
  }

  atualizarEtapaPedido(etapa);
}


function montarResumoPedido() {

  const origem =
    document
      .getElementById('ped-origem-nome')
      .value
      .trim();

  const itens =
    document
      .getElementById('ped-itens')
      .value
      .trim();

  const valor =
    parseFloat(
      document.getElementById('ped-valor').value
    ) || 0;

  const taxa =
    parseFloat(
      document.getElementById('ped-taxa').value
    ) || 0;

  const obs =
    document
      .getElementById('ped-obs')
      .value
      .trim();

  document.getElementById(
    'resumo-origem'
  ).textContent = origem || '-';

  document.getElementById(
    'resumo-itens'
  ).textContent = itens || '-';

  document.getElementById(
    'resumo-valor'
  ).textContent = formatarMoeda(valor);

  document.getElementById(
    'resumo-taxa'
  ).textContent = formatarMoeda(taxa);

  document.getElementById(
    'resumo-total'
  ).textContent = formatarMoeda(
    valor + taxa
  );

  const observacao =
    document.getElementById(
      'resumo-observacao'
    );

  const textoObservacao =
    document.getElementById(
      'resumo-obs-texto'
    );

  if (obs) {

    textoObservacao.textContent = obs;

    observacao.classList.remove('hidden');

  } else {

    observacao.classList.add('hidden');

  }

  const enderecoSelecionado =
    Array.from(document.querySelectorAll('.linha-endereco'))
      .find((elemento) => elemento.dataset.enderecoId === String(enderecoEscolhidoId));

  if (enderecoSelecionado) {

    const apelido =
      enderecoSelecionado.querySelector(
        '.linha-endereco-apelido'
      );

    const texto =
      enderecoSelecionado.querySelector(
        '.linha-endereco-texto'
      );

    if (apelido && texto) {

      document.getElementById(
        'resumo-endereco'
      ).textContent =
        `${apelido.textContent} — ${texto.textContent.replace(/\s+/g, ' ').trim()}`;

    }
  }
}


function cancelarPedidoWizard() {

  document
    .getElementById('pedido-section')
    .classList.add('hidden');

  enderecoEscolhidoId = null;

  resetarFormularioPedido();
}


function resetarFormularioPedido() {

  pedidoEtapaAtual = 1;

  coordOrigem = null;

  if (marcadorOrigem && mapPickerOrigem) {

    mapPickerOrigem.removeLayer(
      marcadorOrigem
    );

    marcadorOrigem = null;
  }

  const campos = [
    'ped-origem-nome',
    'ped-itens',
    'ped-valor',
    'ped-obs'
  ];

  campos.forEach(id => {

    const el = document.getElementById(id);

    if (el) {
      el.value = '';
    }

  });

  const taxa =
    document.getElementById('ped-taxa');

  if (taxa) {
    taxa.value = '0';
  }

  atualizarEtapaPedido(1);
}


/* -------------------------------------------------------------------------- */
/* CRIAÇÃO DO PEDIDO                                                          */
/* -------------------------------------------------------------------------- */

async function criarPedido() {

  if (!enderecoEscolhidoId) {
    mostrarMsg('Escolha um endereço primeiro.');
    return;
  }

  if (!coordOrigem) {
    mostrarMsg(
      'Marque no mapa onde fica o estabelecimento.'
    );
    atualizarEtapaPedido(1);
    return;
  }

  const origemNome =
    document
      .getElementById('ped-origem-nome')
      .value
      .trim();

  const itens =
    document
      .getElementById('ped-itens')
      .value
      .trim();

  const valor =
    parseFloat(
      document.getElementById('ped-valor').value
    );

  const taxa =
    parseFloat(
      document.getElementById('ped-taxa').value
    ) || 0;

  const obs =
    document
      .getElementById('ped-obs')
      .value
      .trim();

  if (!origemNome) {
    mostrarMsg('Informe o estabelecimento.');
    atualizarEtapaPedido(1);
    return;
  }

  if (!itens) {
    mostrarMsg('Informe o que você quer comprar.');
    atualizarEtapaPedido(2);
    return;
  }

  if (!valor || valor <= 0) {
    mostrarMsg('Informe um valor válido.');
    atualizarEtapaPedido(2);
    return;
  }

  const payload = {

    endereco_id:
      enderecoEscolhidoId,

    origem_nome:
      origemNome,

    origem_latitude:
      coordOrigem.lat,

    origem_longitude:
      coordOrigem.lng,

    itens_descricao:
      itens,

    valor_total:
      valor,

    taxa_entrega:
      taxa,

    observacoes:
      obs || null
  };

  try {

    const resp = await apiFetch(
      '/pedidos/',
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );

    const data = await resp.json();

    if (!resp.ok) {

      mostrarMsg(
        data.detail ||
        'Erro ao criar pedido'
      );

      return;
    }

    mostrarMsg(
      'Pedido criado! Aguardando um motoboy aceitar...',
      false
    );

    iniciarAcompanhamento(data);

  } catch (e) {
    /* já tratado */
  }
}


/* -------------------------------------------------------------------------- */
/* ACOMPANHAMENTO                                                             */
/* -------------------------------------------------------------------------- */

const CORES_STATUS = {
  pendente: '#f59e0b',
  aceito: '#3b82f6',
  a_caminho_coleta: '#3b82f6',
  coletado: '#3b82f6',
  a_caminho_entrega: '#3b82f6',
  entregue: '#16a34a',
  cancelado: '#dc2626'
};


const LABELS_STATUS = {
  pendente: 'Pendente',
  aceito: 'Aceito',
  a_caminho_coleta: 'A caminho da coleta',
  coletado: 'Coletado',
  a_caminho_entrega: 'A caminho da entrega',
  entregue: 'Entregue',
  cancelado: 'Cancelado'
};


async function carregarPedidoAtivo() {
  try {
    const resp = await apiFetch('/pedidos/me/atual');
    if (!resp.ok) return;
    const pedido = await resp.json();
    if (pedido) iniciarAcompanhamento(pedido);
  } catch (e) {
    /* restauração opcional da sessão */
  }
}


function iniciarAcompanhamento(pedido) {

  pedidoAtualId = pedido.id;

  document
    .getElementById('pedido-section')
    .classList.add('hidden');

  document
    .getElementById('acompanhar-section')
    .classList.remove('hidden');

  if (!mapAcompanhar) {

    mapAcompanhar = L
      .map('map-acompanhar')
      .setView(CENTRO_PORANGA, 16);

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }
    ).addTo(mapAcompanhar);

    L.circle(
      CENTRO_PORANGA,
      {
        radius: RAIO_KM * 1000,
        color: '#3388ff',
        fillOpacity: 0.05
      }
    ).addTo(mapAcompanhar);
  }

  setTimeout(() => {
    mapAcompanhar.invalidateSize();
  }, 100);

  if (marcadorOrigemMap) {
    mapAcompanhar.removeLayer(marcadorOrigemMap);
  }

  marcadorOrigemMap =
    L.marker(
      [
        pedido.origem_latitude,
        pedido.origem_longitude
      ]
    )
    .addTo(mapAcompanhar)
    .bindPopup(
      `📍 ${escapeHtml(pedido.origem_nome)}`
    );

  atualizarStatusVisual(pedido.status);

  conectarWebSocketPedido(pedido.id);

  if (pollingInterval) {
    clearInterval(pollingInterval);
  }

  pollingInterval =
    setInterval(
      () => verificarStatusPedido(pedido.id),
      5000
    );
}


function atualizarStatusVisual(status) {

  const el =
    document.getElementById('pedido-status');

  el.textContent =
    LABELS_STATUS[status] || status;

  el.style.background =
    CORES_STATUS[status] || '#6b7280';
}


async function verificarStatusPedido(pedidoId) {

  try {

    const resp =
      await apiFetch(
        `/pedidos/${pedidoId}`
      );

    const pedido =
      await resp.json();

    atualizarStatusVisual(
      pedido.status
    );

    if (
      pedido.status === 'entregue' ||
      pedido.status === 'cancelado'
    ) {

      clearInterval(pollingInterval);
      pollingInterval = null;

      if (wsAcompanhar) {
        wsAcompanhar.close();
        wsAcompanhar = null;
      }
    }

  } catch (e) {
    /* já tratado */
  }
}


async function conectarWebSocketPedido(pedidoId) {

  if (wsAcompanhar) {
    wsAcompanhar.close();
  }

  let wsToken;

  try {
    wsToken = await obterTokenWs();
  } catch (e) {
    return;
  }

  const wsProtocol =
    location.protocol === 'https:'
      ? 'wss'
      : 'ws';

  wsAcompanhar =
    new WebSocket(
      `${wsProtocol}://${location.host}/ws/cliente/${pedidoId}?token=${wsToken}`
    );

  wsAcompanhar.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (e) {
      return;
    }

    if (msg.tipo === 'posicao_gps' && Number.isFinite(msg.latitude) && Number.isFinite(msg.longitude)) {
      const pos = [msg.latitude, msg.longitude];

      if (marcadorMotoboyMap) {
        marcadorMotoboyMap.setLatLng(pos);
      } else {
        marcadorMotoboyMap = L.marker(pos)
          .addTo(mapAcompanhar)
          .bindPopup('🛵 Seu motoboy');
      }
    }
  };

  wsAcompanhar.onerror = () => mostrarMsg('Não foi possível atualizar a localização em tempo real.');
  wsAcompanhar.onclose = () => { wsAcompanhar = null; };
}


function voltarParaNovoPedido() {

  document
    .getElementById('acompanhar-section')
    .classList.add('hidden');

  document
    .getElementById('enderecos-section')
    .classList.remove('hidden');

  if (wsAcompanhar) {
    wsAcompanhar.close();
    wsAcompanhar = null;
  }

  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }

  carregarEnderecos();
}


/* -------------------------------------------------------------------------- */
/* UTILITÁRIOS                                                                */
/* -------------------------------------------------------------------------- */

function formatarMoeda(valor) {

  return valor.toLocaleString(
    'pt-BR',
    {
      style: 'currency',
      currency: 'BRL'
    }
  );
}


function escapeHtml(valor) {

  if (valor === null || valor === undefined) {
    return '';
  }

  return String(valor)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}


/* -------------------------------------------------------------------------- */
/* INICIALIZAÇÃO                                                              */
/* -------------------------------------------------------------------------- */

if (token && nomeUsuario) {

  document
    .getElementById('auth-section')
    .classList.add('hidden');

  document
    .getElementById('logado-section')
    .classList.remove('hidden');

  document.getElementById('saudacao').textContent =
    `Olá, ${nomeUsuario}!`;

  carregarEnderecos();
  carregarPedidoAtivo();
}


function alternarDetalhesEndereco() {
    document.getElementById('detalhes-endereco-extra').classList.toggle('hidden');
}
