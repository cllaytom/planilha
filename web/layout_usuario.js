(() => {
 if(location.pathname!='/clientes')return;
 const botao=document.getElementById('novo');if(!botao)return;
 const estilo=document.createElement('style');estilo.textContent='.dv-criar-linha{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.dv-criar-linha #novo{padding:7px 9px;font-size:11px;margin:8px 0 0;white-space:nowrap}.dv-criar-linha strong{margin-right:auto}';document.head.appendChild(estilo);
 botao.addEventListener('click',e=>e.stopPropagation());
 botao.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')e.stopPropagation()});
 function posicionar(){const card=Array.from(document.querySelectorAll('#dashboardVencimentos .dv-kpi')).find(c=>c.querySelector('span')?.textContent?.trim()==='Clientes na base');if(!card||card.contains(botao))return;const numero=card.querySelector('strong');if(!numero)return;const linha=document.createElement('div');linha.className='dv-criar-linha';linha.appendChild(numero);linha.appendChild(botao);card.appendChild(linha);botao.title='Cadastrar novo cliente';botao.setAttribute('aria-label','Cadastrar novo cliente')}
 new MutationObserver(posicionar).observe(document.querySelector('main'),{childList:true,subtree:true});posicionar();
})();
