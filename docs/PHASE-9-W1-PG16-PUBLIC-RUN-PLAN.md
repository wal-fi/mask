# Proposta exata — uma sonda pública PG16

2026-10-30 sob delegação. Preparador02d1/desenho aceitos55166, exportador95f0
aceito94684, entradaa608/host7275 aceitos anteriormente.378 testes/52,39s e
estáticos326 limpos; código publicado emf40d4a6. O texto abaixo preserva
a proposta anterior à execução; resultado medido em PUBLIC-RUN-VALIDATION.

## Proposta pública original, antes de materializar a raiz

Três arquivos em `docs/poc/evidence/pg16-public-prep-20261030/`:

- Task: `81e727564dff42578c0aa93a9a470d72`.
- Raiz: `C:/Users/w.filho/AppData/Local/Temp/maskgw-pg16-public-20261030-c3a916a7a7ff43f89608c6e8a1d26428`.
- Estado canônico1935 bytes, SHA-256
  `721f642f890058722c0fd5a49368c9f61b76b36feedc15e37f97edf098d83d79`.
- Script v2 ASCII9700 bytes, SHA-256
  `37de40fe2f2597bb4989561ca1e382b1a5161c4e7a838e38e11bf85c25546676`.
- createprocess2570 caracteres/margem23430. Imagem PG16cf78 pinada, nunca pull.
- Pins de fontes/CLI/PS/config/endpoint conferidos por Host.pins sem efeito
  de laboratório. Desktop observado Off em2026-10-30T14:10:14.3655804Z.

Estado/argv/script completos estão na proposta. O script confere34 pins de
fontes/stdlib/binários/config/launcher/Python base/pyvenv.cfg, raiz não-reparse
com só attempt.json e o SHA exato do estado, no instante da chamada. Exige DesktopOff
pelo mesmo filtro de nomes do coordenador, antes de invocar Python. Somente
python -I -B entrada root, sem shell aninhado, expansão de argumentos ou
variável de segredo. Execução futura será pelo mesmo texto ASCII revisado,
sem alterar ExecutionPolicy ou executar arquivo de origem não conferida.

## Ordem e invariantes

1. Revisão da proposta/estado/script antes de materialização. Confirmar que
   a raiz não existe, Desktop ainda Off e os quatro helpers têm os hashes
   aceitos. Não há outro DockerCLI/escritor em execução.
2. Chamar materialize02d1 uma vez. Conferir que a raiz contém só attempt.json,
   com bytes/SHA iguais à proposta, e argv exatamente igual. Esse passo só
   escreve estado público, sem Desktop/Docker/clock operacional.
3. Invocar o texto ASCII9700 uma única vez. Registrar a intenção de execução
   antes da chamada, guardar sessão/exit/console. Não repetir root/main/script.
4. A/9observações/READY/B/journal12 pelo código aceito. No preflight, imagem e
   inventário global admitidos; antes do create, baseline de volumes recente e
   nova listagem igual. Um create, perfil antes de start, uma sonda DEVNULL.
5. Sem initdb/servidor/SQL/conexão de banco, rede, porta, senha ou seed. A sonda
   mede só ferramentas/versões/UID/GID e tmpfs; não testa worker/ingresso.
6. Cleanup/owner/ticket/ausência/inventários e join antes de Desktoprestore.
   Não alterar teto, código ou política para obter sucesso. HELD mantém o
   mesmo processo/loop, sem segundo escritor/CLI de limpeza improvisada.
7. Somente após exit terminal e provas positivas, exportar uma vez com95f0,
   reported_exit real. Antes disso nenhum raw do Temp vai à conversa/Git.
   Publicar só summary/transport construídos pelo exportador. Fonte/root
   consumidos ficam congelados, mesmo em NOT_PASSED; não apagar evidência.
8. Revisão factual do resultado. Não confundir relatório público saudável com
   B1/B2/D090/C1, SQL, worker, serviço ou produção. Gateway segue indisponível.

Qualquer precondição divergente aborta sem nova rodada automática. A verificação
de pins/estado/bytes é própria deste plano e não substitui o ciclo fresco.
Sem job/quota/segundo escritor; nenhuma credencial antiga será usada.

## Revisão6483 antes de materializar (histórico)

Script inicial603/13969d61 recusado por não repetir as guardas de integridade
no instante da invocação. Preservado em invoke-rejected-v1.ps1 e
proposal-rejected-v1.json, jamais executado. V2 acrescenta34 pins, o Python
base e cfg da venv, estrutura fresh/reparse e SHA721f642f do estado antes do
Python. Estado/task/raiz/argv/escopo iguais; nenhum efeito nativo ocorreu.
