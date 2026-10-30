# Próximo lote separado — atribuição fechada de módulo nativo sem arquivo

**2026-10-21 — plano revisado; implementação diagnóstica em revisão de código.**
Não repetir a terceira rodada nem alterar seus artefatos/fontes/resultados.
`PHASE-9-STAGE-8-LINUX-IMPORTS-NAME-VALIDATION.md` nomeou `_openssl` como
FILELESS_UNATTRIBUTED na auditoria da etapa1. Isso não autoriza simplesmente
liberar esse nome, aceitar todo CFFI/PyO3 ou atribuir a cryptography por palpite.

Indício estático, não identidade medida: o arquivo já verificado
cryptography/hazmat/bindings/openssl/binding.py da árvore parcial contém
`from cryptography.hazmat.bindings._rust import _openssl, openssl` (linha14).
É candidato a relação de identidade, não prova de autoria independente.

Proposta estreita para revisão antes de código:

1. Apenas para o módulo fileless `_openssl`, exigir que a extensão exata
   `cryptography.hazmat.bindings._rust` já esteja carregada, file-backed em
   `/installed/cryptography/hazmat/bindings/_rust.abi3.so`, com origem/owner
   cryptography verificados pelas mesmas regras e árvore/hash conferidos
   pelo host. Nenhum import novo, DNS, filesystem fora da árvore ou lib extra.
2. Exigir **identidade de objeto**: o valor de `_openssl` no __dict__ dessa
   extensão deve ser o próprio objeto de sys.modules['_openssl']. Usar
   leitura direta do dicionário, sem getattr dinâmico, repr ou conteúdo.
   Nome, presença da lib, semelhança de path ou símbolo no binário não bastam.
3. Só com ambas as provas o inventário pode registrar associação gerada
   explícita ao caminho relativo da extensão, nunca __file__ inventado ou
   afirmação de código independente. Se faltar qualquer condição, manter
   FILELESS_UNATTRIBUTED/erro fechado; sem wildcard ou fallback adicional.
4. Testes puros primeiro: identidade verdadeira e falsa com mesmo nome,
   provider ausente/fileless/fora da árvore, path/owner diferentes e segredo
   em atributo que não deve ser lido; todos os guards/codec/caps preservados.
   Revisar código com Claude2 antes de uma nova rodada identificada.
5. O controle real é a primeira prova dessa relação no runtime Linux: se
   não existir a identidade, parar inconclusivo. AS32 só se todo controle
   for normal, mesmos limites/casos, sem repetir até verde ou elevar quota.

O revisor considerou a prova suficiente para implementar e revisar o código
antes de executar, com condições abaixo. Implementada depois desse aval,
com regressões e releitura ainda antes de qualquer execução nova. Não fecha
B-1/B-2/D-090.
Sem produto, worker, SQL de cliente, banco, dependência, bind ou produção.

Condições da revisão na sessão51ea0d85: associação constante única; tipos
exatos ModuleType de ambos os objetos antes de ler atributos; __dict__
exatamente dict, leitura por get e identidade por is, nunca ==. Nenhum
__getattr__ dinâmico; provider exige __file__ str no próprio dict antes da
verificação normal de origem. Owner cryptography e caminho exato precisam
coincidir; erro de origem é propagado. Tag distinta attached-by-identity.
Contraprovas incluem subclass hostil, igualdade falsa positiva, outro nome
fileless, provider/path/owner errado, alvo file-backed na regra normal e
segredo em atributo não consultado. Hash do .so instalado conferido:
3d6423664bffe926fd91d1913d1c5ddda5c31ee7ff1cae06fc8b71c47c9501a1,
14.389.392 bytes. Isso não mede identidade no Linux; o controle futuro é a
primeira medição. Opção de coletar vários candidatos foi considerada, mas
não adotada: muda mais o protocolo; o vínculo exato é o menor incremento.

Código diagnóstico implementado em linux_import_probe.py, não src. Treze
casos novos: dois falharam e onze já recusavam antes da implementação;
mais um garante ausência de __getattr__ também na emissão do erro.
170 testes relacionados verdes; Ruff/format e mypy3.11/3.14 limpos.
Revisão de código somente leitura solicitada antes de outra rodada.
