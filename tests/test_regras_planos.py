import unittest
from aplicar_integracao import retorno_da_funcao
from app.regras_planos import validar_campos


class RegressaoPlanos(unittest.TestCase):
    def test_rotas_independentes_e_idempotentes(self):
        texto = 'def cadastro_produtos():\n    return FileResponse("produtos.html")\n\ndef tela_planos():\n    return HTMLResponse(PLANOS_HTML)\n\ndef health():\n    return {"status":"ok"}\n'
        expressao = 'FileResponse(BASE_DIR / "web" / "gestao.html")'
        parcial = retorno_da_funcao(texto, 'cadastro_produtos', expressao)
        final = retorno_da_funcao(parcial, 'tela_planos', expressao)
        self.assertEqual(final.count('return ' + expressao), 2)
        self.assertEqual(retorno_da_funcao(final, 'tela_planos', expressao), final)
        self.assertIn('return {"status":"ok"}', final)

    def test_rejeita_campos_invalidos(self):
        casos = [{'nome':'   '}, {'nome':'a'*81}, {'valor':-1}, {'valor':float('nan')}, {'valor':float('inf')}, {'dias':0}, {'dias':3651}, {'conexoes':0}, {'conexoes':None}, {'conexoes':True}, {'ativo':None}]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                validar_campos(caso)

    def test_normaliza_sem_recalcular_precos(self):
        dados = validar_campos({'nome':' MENSAL ', 'produto':' IPTV ', 'valor':20, 'dias':30, 'conexoes':3})
        self.assertEqual(dados['nome'], 'MENSAL')
        self.assertEqual(dados['produto'], 'IPTV')
        self.assertEqual(dados['valor'], 20)

    def test_arquivar_legado_nao_exige_reescrever_campos(self):
        self.assertEqual(validar_campos({'ativo':False}), {'ativo':False})

if __name__ == '__main__':
    unittest.main()
