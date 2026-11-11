(() => {
 const limite=999999999999;
 function deDigitacao(t){const d=String(t).replace(/\D/g,'')||'0';const n=Number(d);if(!Number.isSafeInteger(n)||n>limite)throw Error('Valor acima do limite permitido.');return n}
 function dePrograma(v){if(v===''||v==null)return 0;let t=String(v).trim().replace(/^R\$\s*/,'');if(t.includes(','))t=t.replace(/\./g,'').replace(',','.');const n=Number(t);if(!Number.isFinite(n)||n<0)throw Error('Valor inválido.');const c=Math.round(n*100);if(!Number.isSafeInteger(c)||c>limite)throw Error('Valor acima do limite permitido.');return c}
 function formatar(n){return(n/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
 globalThis.MoedaCliente={deDigitacao,dePrograma,formatar};
 if(typeof document==='undefined')return;
 const $=id=>document.getElementById(id),estados=new Map(),nativo=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
 for(const id of ['novoValor','novoDesconto','renovarValor']){
  const campo=$(id);if(!campo||campo.dataset.mascaraMoeda==='v2')continue;
  const inicial=nativo.get.call(campo);campo.type='text';campo.inputMode='numeric';campo.removeAttribute('step');campo.placeholder='R$ 0,00';campo.dataset.mascaraMoeda='v2';
  const estado={centavos:0,valido:true};estados.set(id,estado);
  function mostrar(){nativo.set.call(campo,formatar(estado.centavos))}
  function definir(v){try{estado.centavos=dePrograma(v);estado.valido=true;campo.setCustomValidity('')}catch(e){estado.valido=false;campo.setCustomValidity(e.message)}mostrar()}
  Object.defineProperty(campo,'value',{configurable:true,get(){return(estado.centavos/100).toFixed(2)},set(v){definir(v)}});
  definir(inicial);
  campo.addEventListener('input',e=>{e.stopImmediatePropagation();try{estado.centavos=deDigitacao(nativo.get.call(campo));estado.valido=true;campo.setCustomValidity('')}catch(err){estado.valido=false;campo.setCustomValidity(err.message)}mostrar();try{campo.setSelectionRange(nativo.get.call(campo).length,nativo.get.call(campo).length)}catch(_){}},true);
  campo.addEventListener('blur',()=>mostrar(),true);
  campo.addEventListener('focus',()=>{if(estado.centavos===0)campo.select()});
 }
 for(const [botao,campos] of [['btnSalvarCliente',['novoValor','novoDesconto']],['btnConfirmarRenovar',['renovarValor']]]){
  $(botao)?.addEventListener('click',e=>{try{for(const id of campos){if(estados.has(id)&&!estados.get(id).valido)throw Error('Confira o valor informado.')}if(campos.length===2&&(estados.get('novoDesconto')?.centavos||0)>(estados.get('novoValor')?.centavos||0))throw Error('O desconto não pode ser maior que o valor da venda.')}catch(err){e.preventDefault();e.stopImmediatePropagation();const aviso=$('avisoProduto');if(aviso)aviso.textContent=err.message;window.alert(err.message)}},true);
 }
})();
