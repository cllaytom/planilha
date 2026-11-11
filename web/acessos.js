(() => {
  const original = window.fetch.bind(window);
  const modal = document.getElementById('modalNovoCliente');
  if (!modal) return;
  const campo = document.createElement('div');
  campo.innerHTML = '<label for="quantidadeAcessos">Quantidade de acessos</label><input id="quantidadeAcessos" type="number" min="1" step="1" value="1"><small>Multiplica somente o custo do produto. O valor de venda continua sendo o total informado.</small>';
  modal.querySelector('.rodape').before(campo);
  const input = campo.querySelector('input');
  let ultimoCliente = null;
  new MutationObserver(() => {
    if (!modal.classList.contains('aberto')) return;
    input.value = /novo/i.test(document.getElementById('tituloCliente').textContent) ? 1 : (ultimoCliente?.conexoes || 1);
  }).observe(modal, {attributes:true, attributeFilter:['class']});
  window.fetch = async function(resource, options) {
    const req = resource instanceof Request;
    const url = new URL(typeof resource === 'string' ? resource : (req ? resource.url : String(resource)), location.href);
    const path = url.pathname.replace(/\/$/, '');
    const method = (options?.method || (req ? resource.method : 'GET')).toUpperCase();
    let opts = options;
    if ((method === 'POST' && path === '/assinaturas') || (method === 'PATCH' && /^\/assinaturas\/\d+$/.test(path) && modal.classList.contains('aberto'))) {
      const n = Number(input.value);
      if (!Number.isInteger(n) || n < 1) throw Error('Informe uma quantidade inteira de acessos, maior que zero.');
      if (typeof options?.body !== 'string') throw Error('Nao foi possivel ler os dados do cliente.');
      const payload = JSON.parse(options.body);
      payload.conexoes = n;
      const select = document.getElementById('novoPlano');
      const escolhido = select?.value || '';
      const rotulo = select?.selectedOptions[0]?.textContent?.trim() || '';
      if (method === 'POST' || escolhido) {
        const r = await original('/planos?apenas_ativos=true', {headers:{'X-API-Key':localStorage.getItem('assinaturas.apiKey') || ''}});
        if (!r.ok) throw Error('Nao foi possivel consultar os planos. Nenhum cliente foi criado.');
        const planos = await r.json();
        const plano = planos.find(p => String(p.id) === escolhido || p.nome === escolhido)
          || planos.find(p => rotulo === p.nome || rotulo.startsWith(p.nome + ' — ') || rotulo.startsWith(p.nome + ' - '));
        if (!plano) throw Error('Selecione um plano ativo valido antes de salvar. Nenhum dado do cliente foi salvo.');
        if (!plano.produto) throw Error('Este plano esta sem produto. Vincule um produto em Planos antes de salvar o cliente.');
        payload.plano_id = plano.id;
        payload.plano_nome = plano.nome;
        payload.produto = plano.produto;
      }
      opts = {...options, body:JSON.stringify(payload)};
    }
    let target = resource;
    if (method === 'GET' && path === '/planos') {
      url.searchParams.set('apenas_ativos','true');
      target = req ? new Request(url.toString(), resource) : url.toString();
    }
    const response = await original(target, opts);
    if (method === 'GET' && /^\/assinaturas\/\d+$/.test(path) && response.ok) {
      ultimoCliente = await response.clone().json();
      if (modal.classList.contains('aberto') && !/novo/i.test(document.getElementById('tituloCliente').textContent)) input.value = ultimoCliente.conexoes || 1;
    }
    return response;
  };
})();
