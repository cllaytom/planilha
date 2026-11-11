(() => {
  const original = window.fetch.bind(window);
  const campo = document.createElement('div');
  campo.innerHTML = '<label for="quantidadeAcessos">Quantidade de acessos</label><input id="quantidadeAcessos" type="number" min="1" step="1" value="1"><small>Multiplica somente o custo do produto. O valor de venda continua sendo o total informado.</small>';
  const modal = document.getElementById('modalNovoCliente');
  if (!modal) return;
  modal.querySelector('.rodape').before(campo);
  const input = campo.querySelector('input');
  let ultimoCliente = null;
  new MutationObserver(() => {
    if (!modal.classList.contains('aberto')) return;
    const titulo = document.getElementById('tituloCliente').textContent;
    input.value = /novo/i.test(titulo) ? 1 : (ultimoCliente?.conexoes || 1);
  }).observe(modal, {attributes: true, attributeFilter: ['class']});
  window.fetch = async function(resource, options) {
    const url = new URL(typeof resource === 'string' ? resource : resource.url, location.href);
    const path = url.pathname.replace(/\/$/, '');
    const method = (options?.method || (resource instanceof Request ? resource.method : 'GET')).toUpperCase();
    if (method === 'GET' && path === '/planos') url.searchParams.set('apenas_ativos', 'true');
    let opts = options;
    if ((method === 'POST' && path === '/assinaturas') || (method === 'PATCH' && /^\/assinaturas\/\d+$/.test(path) && modal.classList.contains('aberto'))) {
      const n = Number(input.value);
      if (!Number.isInteger(n) || n < 1) throw Error('Informe uma quantidade inteira de acessos, maior que zero.');
      if (typeof options?.body !== 'string') throw Error('Nao foi possivel ler os dados do cliente.');
      const payload = JSON.parse(options.body);
      payload.conexoes = n;
      opts = {...options, body: JSON.stringify(payload)};
    }
    const target = method === 'GET' && path === '/planos' && !(resource instanceof Request) ? url.toString() : resource;
    const response = await original(target, opts);
    if (method === 'GET' && /^\/assinaturas\/\d+$/.test(path) && response.ok) {
      ultimoCliente = await response.clone().json();
      if (modal.classList.contains('aberto') && !/novo/i.test(document.getElementById('tituloCliente').textContent)) input.value = ultimoCliente.conexoes || 1;
    }
    return response;
  };
})();
