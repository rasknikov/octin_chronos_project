# Command Sanitization Rules

Objetivo: impedir comandos destrutivos e garantir escopo local.

Proibido (blocklist minima):
- rm -rf
- mkfs
- redirecionamento bruto para disco (ex.: > /dev/sda)
- qualquer tentativa de acessar caminhos fora de /octin_chronos/

Permitido (allowlist minima):
- python / python3
- pip install
- ls / dir
- mkdir
- cat / type

Restricao de escopo:
- Todo comando deve atuar SOMENTE dentro de /octin_chronos/.
- Em Windows, adapte o filtro para o caminho raiz do projeto (ex.: D:\OCTIN\octin_labs\lab_axis_00).

Nota de trincheira:
- Depois de um quase-desastre com caminho fora do repo, essa regra virou inegociavel.

Sugestao de filtro no n8n (regex):
- Blocklist: `(?i)(rm\s+-rf|mkfs|>\s*/dev/sd)`
- Allowlist: `(?i)^(python|python3|pip|ls|dir|mkdir|cat|type)`
- Path scope (Linux): `^/octin_chronos/`
