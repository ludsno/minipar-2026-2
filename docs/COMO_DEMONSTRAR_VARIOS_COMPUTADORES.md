# Guia da Apresentação — `fork` em vários computadores

Programa: [`tests/demo_varios_computadores.minipar`](../tests/demo_varios_computadores.minipar). **Não precisa editar nada**: ele pergunta os IPs quando roda.

**A ideia em uma frase:** o mesmo programa roda em 3 "computadores". O **computador 1** (principal) divide o trabalho em 2 subtarefas com `fork ... @computador(ip, porta)`; o **computador 2** calcula uma soma e o **computador 3** calcula um fatorial. Eles não compartilham memória: os dados vão e voltam por mensagens (`c_channel`, `send`, `receive`), e o `join` espera os dois terminarem.

Há 3 formas de mostrar, da mais simples para a mais completa:

| Forma | Precisa de | Quando usar |
|---|---|---|
| **A. 1 terminal** (ou botão Executar da interface web) | Nada | Plano B, ou se o tempo for curto |
| **B. 3 terminais no mesmo computador** | 3 janelas de terminal | **Recomendada**: cada "computador" aparece na sua própria tela |
| **C. Computadores de verdade** | 2 ou 3 PCs na mesma rede | Se decidirem mostrar com notebooks diferentes |

---

## Checklist na véspera

- [ ] Compilar uma vez (só precisa repetir se mudar o código):
  ```bash
  cd ~/ufal/compiladores/minipar-2026-2
  python3 main.py tests/demo_varios_computadores.minipar
  ```
  Deve terminar com `[SUCESSO] Executavel: output/demo_varios_computadores.exe`.
- [ ] Ensaiar a **Forma B** uma vez, do começo ao fim.
- [ ] Se for usar a **Forma C**, ensaiar com os computadores e a rede que estarão na sala.

---

## Forma A — 1 terminal (o programa abre os outros computadores sozinho)

```bash
cd ~/ufal/compiladores/minipar-2026-2
./output/demo_varios_computadores.exe
```
Aperte **ENTER nas 3 perguntas**. Como ninguém está esperando nas portas 6201 e 6202, o programa **abre sozinho** os computadores 2 e 3 como processos separados nesta máquina. Por isso as mensagens deles (`[computador :6201] ...`, `[computador :6202] ...`) aparecem misturadas na mesma tela.

**Pela interface web:** em `/didatico`, escolha **"🌐 Demo: Fork em Vários Computadores"**, deixe a caixa de entradas **vazia** e clique em **Executar**. O resultado é o mesmo da Forma A.

---

## Forma B — 3 terminais no mesmo computador (recomendada)

**Abra 3 terminais.** No VS Code: menu *Terminal → Novo Terminal*, três vezes. Se algum mostrar `PS C:\...` (PowerShell), digite `wsl` e Enter nele.

**A ordem importa: primeiro os computadores 2 e 3, por último o computador 1.**

**Terminal 2 — "Computador 2"**
```bash
cd ~/ufal/compiladores/minipar-2026-2
MINIPAR_TRABALHADOR=6201 ./output/demo_varios_computadores.exe
```

**Terminal 3 — "Computador 3"**
```bash
cd ~/ufal/compiladores/minipar-2026-2
MINIPAR_TRABALHADOR=6202 ./output/demo_varios_computadores.exe
```

Os dois devem mostrar `trabalhador pronto, aguardando subtarefas...` e **ficar parados**. Isso é o certo: estão esperando.

**Terminal 1 — "Computador 1" (principal)**
```bash
cd ~/ufal/compiladores/minipar-2026-2
./output/demo_varios_computadores.exe
```
Aperte **ENTER nas 3 perguntas**.

### Como saber se deu certo

| Terminal | O que deve aparecer |
|---|---|
| 1 (principal) | `[fork subtarefa_soma] subtarefa enviada ao computador 127.0.0.1:6201`<br>`[fork subtarefa_fatorial] subtarefa enviada ao computador 127.0.0.1:6202`<br>`... concluida ...` (duas vezes)<br>`Soma de 1 a 10000 calculada no computador 127.0.0.1 = 50005000`<br>`Fatorial de 12 calculado no computador 127.0.0.1 = 479001600` |
| 2 | `[computador :6201] executando subtarefa subtarefa_soma`<br>`Recebi n = 10000 do computador 127.0.0.1 - calculando a soma de 1 a n...` |
| 3 | `[computador :6202] executando subtarefa subtarefa_fatorial`<br>`Recebi n = 12 do computador 127.0.0.1 - calculando o fatorial de n...` |

No fim, os terminais 2 e 3 **fecham o programa sozinhos** e voltam para o prompt.

> **Apareceu `[computador :6202] ...` (ou `:6201`) no terminal 1?** Esse computador não estava aberto quando você rodou o principal (ou já tinha fechado no ensaio anterior). O programa abriu ele sozinho e **o resultado continua certo**, mas a mensagem sai no terminal 1. Para cada um aparecer na sua tela, abra os terminais 2 e 3 **antes** do 1.

### Para repetir

Os computadores 2 e 3 encerram no fim de cada execução. Para rodar de novo, repita a ordem: **terminal 2, terminal 3 e depois terminal 1**. Dica: em cada terminal, a **seta ↑** traz de volta o último comando.

### O que falar enquanto roda

1. "Cada terminal é um computador independente: um processo separado, **sem memória compartilhada**."
2. Mostre no código o `fork subtarefa_soma @computador(ip_pc2, 6201) { ... }`: a gramática do MiniPar 2026.2 permite alocar a subtarefa **em um núcleo** (`@nucleo(n)`) **ou em outro computador** (`@computador(ip, porta)`), como pede a página 3 do enunciado.
3. "Os dados vão por mensagem": o computador 1 faz `send` do número e o computador 2 faz `receive`, calcula e devolve com `send`.
4. "O `join` faz o computador 1 esperar as duas subtarefas terminarem."
5. Para trocar para computadores de verdade, basta digitar os IPs reais nas perguntas, sem recompilar.

---

## Forma C — Computadores de verdade

**Preparação (em cada PC):**
1. Compile o programa (comando do Checklist; no Windows: `python main.py tests\demo_varios_computadores.minipar`).
2. Todos na **mesma rede** (mesmo Wi-Fi ou cabo). Anote os IPs: Windows `ipconfig` (linha "Endereço IPv4"); Linux `hostname -I`. Teste com `ping <IP do outro>`.
3. **Firewall do Windows:** na primeira execução, clique em "Permitir acesso". Ou rode uma vez no PowerShell **como administrador**:
   `New-NetFirewallRule -DisplayName MiniPar -Direction Inbound -Protocol TCP -LocalPort 5100-5102,6201-6214 -Action Allow`
4. **WSL2 não recebe conexões de outros computadores** por padrão. Nos PCs que vão receber conexões (todos, nesta demo), rode no **Windows nativo** (g++ do MSYS2) ou num Linux de verdade. No Windows 11 também dá para ativar o modo espelhado: crie `C:\Users\<você>\.wslconfig` com as linhas `[wsl2]` e `networkingMode=mirrored`, e depois rode `wsl --shutdown`.

**Na hora (primeiro PC2 e PC3, depois PC1):**

| PC | Linux / WSL | Windows — PowerShell |
|---|---|---|
| PC2 | `MINIPAR_TRABALHADOR=6201 ./output/demo_varios_computadores.exe` | `$env:MINIPAR_TRABALHADOR="6201"; .\output\demo_varios_computadores.exe` |
| PC3 | `MINIPAR_TRABALHADOR=6202 ./output/demo_varios_computadores.exe` | `$env:MINIPAR_TRABALHADOR="6202"; .\output\demo_varios_computadores.exe` |
| PC1 | `./output/demo_varios_computadores.exe` | `.\output\demo_varios_computadores.exe` |

No PC1, responda: **IP do PC1**, **IP do PC2** e **IP do PC3**.

- **Com só 2 computadores:** no PC2 abra **dois** terminais (6201 e 6202) e, no PC1, digite o IP do PC2 nas perguntas 2 e 3.
- **No Prompt (cmd) do Windows:** `set MINIPAR_TRABALHADOR=6201` e depois `output\demo_varios_computadores.exe`.
- **Depois da demo, no Windows:** a variável continua valendo naquela janela. Feche a janela ou rode `Remove-Item Env:MINIPAR_TRABALHADOR`.
- No Windows o compilador tenta gerar um `.exe` autossuficiente (`-static`), que normalmente pode ser copiado para outro PC Windows. Se ele reclamar de DLL faltando, compile também nesse PC.

---

## Teste 1 (calculadora cliente/servidor) em 1 ou 2 computadores

O Teste 1 usa o mesmo mecanismo: o **servidor** é uma subtarefa `fork servidor @computador(...)`. Depois das 3 entradas da calculadora, o programa pergunta o IP do servidor.

**Em 1 computador** (sem computador extra): aperte **ENTER** na pergunta do IP. Pela interface web, preencha só as 3 entradas (ex.: `*`, `7`, `6`). Aparece o aviso:
```
[fork servidor] Nenhum computador extra aberto em 127.0.0.1:5100 -> a subtarefa vai rodar NESTE computador, em um processo separado.
```
e depois `Servidor recebeu: * 7 6` e `Resultado: 42`.

**Em 2 computadores** (ou 2 terminais):
1. **Computador 2 (servidor)**, aberto primeiro:
   ```bash
   MINIPAR_TRABALHADOR=5100 ./output/teste1_calculadora_cliente_servidor.exe
   ```
2. **Computador 1 (cliente):**
   ```bash
   ./output/teste1_calculadora_cliente_servidor.exe
   ```
   Digite a operação e os 2 operandos. Depois informe o **IP do computador 2** e o **IP do próprio computador 1**. Em 2 terminais do mesmo PC, use o IP mostrado por `hostname -I` nas duas perguntas.
3. `Servidor recebeu: ...` aparece **na tela do computador 2**, e `Resultado: ...` na do computador 1.

---

## Se der problema

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Terminal 2 ou 3 parado em `trabalhador pronto, aguardando subtarefas...` | Nada errado: está esperando o computador 1 | Rode o terminal 1 |
| `Nenhum computador extra aberto em 127.0.0.1:... -> a subtarefa vai rodar NESTE computador` | Aviso normal: não havia trabalhador aberto naquela porta | Nada, se a ideia era rodar em 1 computador. Para separar as telas, abra os trabalhadores antes |
| `Aguardando o computador <IP>:<porta> (ate 30 s). Nele deve estar aberto: ...` | O programa está esperando o outro computador | Abra nele o comando mostrado na mensagem (dentro de 30 s) |
| Mensagens `[computador :620x]` aparecem no terminal 1 | O computador 2 ou 3 não estava aberto; o programa abriu sozinho | Resultado certo. Para separar as telas, abra os terminais 2 e 3 **antes** |
| O programa abre dizendo `trabalhador pronto` em vez de perguntar os IPs | A variável `MINIPAR_TRABALHADOR` ficou definida nessa janela | Feche a janela e abra outra (ou `unset MINIPAR_TRABALHADOR` no Linux) |
| `nao foi possivel escutar a porta` | Um computador de uma tentativa anterior ainda está aberto nessa porta | Ctrl+C no terminal dele, ou `pkill -f demo_varios_computadores` (Linux/WSL), e recomece |
| PC1 mostra `ERRO: computador ... nao respondeu` (depois de ~30 s) | Computador 2/3 não aberto, IP errado ou firewall (Forma C) | Confira IP e firewall; abra os trabalhadores e repita |
| PC2/PC3 mostram `[c_channel] nao foi possivel conectar` | IP do PC1 digitado errado, ou firewall do PC1 bloqueando 6213/6214 | Ctrl+C em todos, confira e repita |
| Alguma tela ficou parada | Uma mensagem não chegou | **Ctrl+C em todos** e recomece na ordem: 2, 3 e depois 1 |

**Plano B:** se nada der certo na hora, use a **Forma A** (1 terminal, ENTER nas perguntas) ou o botão **Executar** da interface web. A demonstração continua valendo: os "computadores" são processos independentes que só conversam por mensagens, e o enunciado permite testar em localhost.
