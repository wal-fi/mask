# Nota estática — candidatos algorithms e modes, não identidade em runtime

**2026-10-21 — somente leitura do texto já instalado/verificado.**
Solicitação Q2 do Claude2 na revisão da quinta rodada. Nenhum módulo da
árvore Linux foi importado, nenhum caso repetido, nenhuma aceitação nova.
Árvore parcial externa: maskgw-linux-imports-20261021-a81ce6d2/installed.
Os três arquivos foram lidos como bytes, tamanho e SHA-256 conferidos
individualmente contra tree.json; não são hashes deduzidos da versão.

| Caminho relativo | Bytes | SHA-256 |
|---|---:|---|
| cryptography/utils.py | 4635 | 21aed2d106734b47b3c2920741f63c1b57bea381a3ac78a31175e3c00af58ae2 |
| cryptography/hazmat/primitives/ciphers/algorithms.py | 3496 | 2067c2c9c6093a1d53be8237e2b7f0f0a7c9ff19add69fc3a4186dd8582171ea |
| cryptography/hazmat/primitives/ciphers/modes.py | 6003 | 1fb0194a02624930428b482b2fdecdc5a912f79d09c852982ecadaf2d8c73f14 |

## O que o texto mostra

- utils.py:73 define _ModuleWithDeprecations como **subclasse** de ModuleType;
  :76 guarda o módulo original no dict sob _module. __getattr__ (:78–89)
  delega lookup a esse módulo, trata _DeprecatedValue e pode cachear atributo.
- deprecated (:119–121) lê sys.modules[module_name] e o substitui pelo
  wrapper quando ainda não é instância dessa classe. :124–125 pode registrar
  valor depreciado por setattr no wrapper, sem origem nova de código.
- algorithms.py:70/82/94 chama utils.deprecated com __name__, para Camellia,
  ARC4 e TripleDES. modes.py:159/171/183 faz isso para OFB/CFB/CFB8.

Isso é evidência estática de um mecanismo que pode explicar os candidatos.
NON_MODULE no protocolo quer dizer **não é exatamente ModuleType**: inclui
subclasses e não prova que o objeto não é módulo. dict_file=null não prova
ausência de arquivo. Não foi medida a classe/identidade real dos objetos
nesses nomes e não se alega que seu __file__ foi conferido em runtime.

## Decisão sob delegação

**Não propor regra para algorithms/modes.** Uma futura rodada própria, só
após preflight obrigatório e revisão de eventual regra exata de .lib, deve
deixar a auditoria antiga decidir suas origens. O texto sugere que lookup
de __file__ poderia ser delegado ao módulo real, mas não garante sucesso:
origem/owner ou outra etapa podem falhar fechado. Também29 módulos exatos
pulados no batch ainda não receberam veredito de origem na etapa1.

Nenhum wildcard de wrapper/CFFI, introspecção de candidato em lote, SQL,
worker ou gate B-1/B-2/D-090/produção foi ampliado ou fechado por esta nota.
