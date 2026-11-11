# MiniPar 2026.2 — O Que Já Foi Feito e O Que Falta Fazer (Guia para a Equipe)

**Equipe:** Ludson Almeida, Davi Melo e Iury Nogueira  
**Disciplina:** Compiladores (Prof. Arturo Hernandez Dominguez)  
**Prazo de Entrega Final:** 11 de Novembro de 2026  
**Repositório / Branch do PR:** `feat/core-e-benchmarks-2026-2` $\rightarrow$ `develop`

---

## 1. Contexto Rápido: O Que o Professor Pediu para 2026.2?

Nós partimos da base do compilador de 2026.1 (`minipar-improvement`), que traduz código **MiniPar** para **C++** (passando por Código de 3 Endereços — **TAC**) e compila um executável `.exe` via `g++`.

Cruzando o edital geral da turma com o pedido que o professor fez diretamente ao nosso grupo após apresentarmos o seminário do artigo **SPar (SBLP'21)**, temos **4 entregas principais**:

1. **Anotações `pure` e `impure` (Pedido específico ao nosso grupo pós-seminário):**
   - Adicionar `pure` e `impure` na linguagem (inspirados no artigo *High-Level Stream and Data Parallelism in C++ for Multi-Cores*), validar semanticamente que `impure` só pode ser usado dentro de `pure`, proteger regiões impuras com mutex no C++ e testar no **Fractal de Mandelbrot**.
2. **Primitivas `fork` e `join` + Benchmarks de Múltiplos Núcleos (Testes 8, 9 e 10):**
   - Adicionar `fork` (disparo assíncrono de tarefas em threads/núcleos) e `join` (barreira de sincronização) e implementar os Testes 8 (4 núcleos), 9 (5 núcleos com Mandelbrot) e 10 (6 núcleos com Mandelbrot + Tapete de Sierpinski), medindo o *Speedup* (Sequencial vs. Paralelo).
3. **2ª Interface Web Didática (Mantendo a CLI e a 1ª Web atuais):**
   - Criar uma segunda tela web com foco educacional (inspirada no compilador didático do IFSC), contendo botões para exibir: **Tokens (Lexer)**, **Árvore Sintática (AST) visual gráfica**, **Análise Semântica (Tabela de Símbolos)**, **TAC**, **Código C++**, **Compilar & Baixar `.exe`** e **Executar**.
4. **Engenharia de Software (UML de Componentes), Gramática BNF e Relatório Final:**
   - Atualizar o arquivo `BNF-grammar.md`, criar os diagramas UML (Componentes de Software, Classes e Casos de Uso) e montar o relatório final seguindo o roteiro do professor.

---

## 2. O Que Já Foi Feito (Pronto no Pull Request Atual)

Para adiantar a parte pesada do motor do compilador e destravar o restante do trabalho, **as Fases 1 (Core do Compilador) e 2 (Benchmarks 8, 9 e 10) já foram implementadas e testadas** na branch `feat/core-e-benchmarks-2026-2`.

### 2.1 Resumo Conceitual das Novas Primitivas Adicionadas
Antes (em 2026.1), o MiniPar só tinha `seq { ... }` e `par { ... }`. Agora ele suporta:

| Primitiva | Para que serve? | Como o Compilador traduz para C++? |
| :--- | :--- | :--- |
| **`pure`** (ou `@pure`) | Marca um laço `for` ou bloco como **Puro** (cálculo independente, sem efeito colateral livre). | Divide as iterações do laço entre os núcleos da CPU (padrão Map / *parallel for*, `std::thread`). O Semântico proíbe escrever em variável externa ao laço fora de `impure`. |
| **`impure`** (ou `@impure`) | Isola o trecho dentro de um bloco `pure` que altera uma variável compartilhada ou imprime na tela. | O Semântico exige que esteja dentro de `pure`. O Codegen C++ protege automaticamente o bloco com `std::lock_guard<std::mutex>` (zero *race condition*). |
| **`fork`** | Dispara uma subtarefa em background em outra thread/núcleo sem travar o programa principal. | Cria uma `std::thread` no pool `__active_fork_threads` executando o bloco paralelamente. |
| **`join`** | Barreira de sincronização: faz a thread principal esperar todas as tarefas do `fork` terminarem. | Percorre `__active_fork_threads` chamando `.join()` em cada thread ativa. |

#### Exemplo da Nova Sintaxe Funcionando no MiniPar:
```minipar
# 1. Exemplo de Pure e Impure (Modelo SPar)
var soma_compartilhada = 0;

pure for (var i = 0; i < 100; i = i + 1) {
    var calculo_isolado = i * 2;
    impure {
        soma_compartilhada = soma_compartilhada + calculo_isolado;
    }
}

# 2. Exemplo de Fork e Join
fork nucleo_1 {
    simular_trabalho(100);
    print("Nucleo 1 terminou!");
}
fork nucleo_2 {
    simular_trabalho(100);
    print("Nucleo 2 terminou!");
}
join; # Aguarda nucleo_1 e nucleo_2 terminarem antes de continuar
```

---

### 2.2 Arquivos do Compilador que Foram Modificados (`src/`)

1. **`src/lexer.py` (Analisador Léxico):**
   - Adicionados os tokens `TokenType.PURE`, `IMPURE`, `FORK` e `JOIN`.
   - Reconhece tanto `pure` / `impure` quanto a notação `@pure` / `@impure`.
2. **`src/ast_nodes.py` (Árvore Sintática - AST):**
   - Criados os nós `PureBlock`, `ImpureBlock`, `ForkBlock` (com nome da tarefa e alocação opcional) e `JoinStmt`.
   - **Pronto para a Fase 3:** Criada a função `ast_to_dict(node)` que converte qualquer árvore AST inteira para um dicionário JSON hierárquico (`name`, `type`, `details`, `line`, `children`), pronto para ser desenhado na 2ª Interface Web!
3. **`src/parser.py` (Analisador Sintático):**
   - Adicionados os métodos `_parse_pure_block()`, `_parse_impure_block()`, `_parse_fork_block()` e `_parse_join_stmt()`.
4. **`src/semantic.py` (Analisador Semântico e Tabela de Símbolos):**
   - Implementada a regra do artigo SPar: se alguém usar `impure` fora de um `pure`, o compilador bloqueia com erro semântico indicando a linha.
   - **Pronto para a Fase 3:** Criado o método `get_symbol_table()` que retorna o histórico completo de todos os símbolos do programa (`name`, `type`, `scope` — ex: `Global`, `Func:nome`, `Class:nome`, `PureBlock`, `Local` — e `line`).
5. **`src/tac.py` (Código Intermediário de 3 Endereços):**
   - Emite as instruções didáticas no `.tac`: `BEGIN_PURE_MAP`, `END_PURE_MAP`, `ACQUIRE_LOCK`, `RELEASE_LOCK`, `FORK_TASK <nome>` e `JOIN_TASKS`.
6. **`src/cpp_template.py` e `src/codegen.py` (Gerador C++ Multithread):**
   - Adicionado o mutex global `__minipar_impure_mtx`, o pool de threads `__active_fork_threads`, a função nativa de alta precisão `obter_tempo()` e `simular_trabalho(ms)`.
   - Tradução completa de `PureBlock`, `ImpureBlock`, `ForkBlock` e `JoinStmt` para C++20 compilado com `g++ -std=c++20 -O3 -pthread`.

---

### 2.3 Novos Programas de Teste Implementados (`tests/`)

Todos os **17 programas de teste** da pasta `tests/` (os antigos de 1 a 7 + os novos de 8 a 10 + extras) compilam e executam com a saída esperada — verificado automaticamente por `tests/test_integracao_componentes.py` (32 testes). Na revisão de 10/11 o teste 7 foi corrigido (a pilha `stack` precisava de espaço pré-alocado) e o teste 1 (sockets cliente/servidor) deixou de travar (o `c_channel` agora mantém o socket de escuta aberto). Destaques:

- **`tests/teste_sanidade_fase1.minipar`:** Teste rápido que valida `pure for`, `impure`, `fork` e `join` juntos.
- **`tests/teste8_avaliacao_4nucleos.minipar` (4 Núcleos):** Professor + 3 Monitores avaliando 160 atividades (40 cada) via `fork`/`join`. Atingiu **Speedup de 3.98x** (~2.40s no sequencial vs. ~0.60s no paralelo).
- **`tests/teste9_mandelbrot_5nucleos.minipar` (5 Núcleos):** 4 núcleos avaliando as 160 atividades + 5º núcleo calculando e desenhando o **Fractal de Mandelbrot em ASCII** usando `pure for` e `impure`. Atingiu **Speedup de 3.98x**.
- **`tests/teste10_6nucleos_2fractais.minipar` (6 Núcleos):** 4 núcleos nas 160 atividades + 5º núcleo no Mandelbrot + 6º núcleo calculando o **Tapete de Sierpinski**, ambos usando `pure for` e `impure`. Atingiu **Speedup de 3.99x**.
- **`tests/teste_fork_nucleos_computadores.minipar` (Fork com alocação):** a mesma tarefa dividida em 2 subtarefas, alocadas em 2 núcleos (`fork @nucleo(n)`) e depois em 2 computadores (`fork @computador(ip, porta)`, processos independentes que se comunicam só por `c_channel`), como pede a página 3 do enunciado.
- **`tests/teste_pure_speedup_mandelbrot.minipar` (Pure x Sequencial):** o mesmo Mandelbrot pesado com `for` comum e com `pure for`. Mede o ganho real do paralelismo de dados (~10x com 16 threads; ~1x se o processo ficar preso em 1 núcleo).

> **Atualização 10/11:** os Testes 8, 9 e 10 foram reescritos como tradução fiel dos programas Python do enunciado (`docs/referencia_python/`): mesmo gerador pseudoaleatório, mesma carga de CPU por atividade e mesmo fractal (idêntico ao do Python). Antes eles usavam `simular_trabalho(15)` (espera pelo relógio), que dava ~4x em qualquer máquina, inclusive com 1 núcleo só. Os números atuais e a comparação com o Python estão na tabela de benchmarks do README.

#### Como testar na máquina de vocês:
```bash
git fetch origin
git checkout feat/core-e-benchmarks-2026-2

# Compilar e rodar qualquer um dos testes novos:
python main.py tests/teste_sanidade_fase1.minipar
./output/teste_sanidade_fase1.exe

python main.py tests/teste9_mandelbrot_5nucleos.minipar
./output/teste9_mandelbrot_5nucleos.exe
```

---

## 3. O Que Falta Fazer (Fases 3 e 4)

> **Status em 10/11/2026:** a Etapa A (2ª Interface Web Didática — PR #2) e a parte de BNF/UML/Scrum da Etapa B (PR #3) já foram concluídas e mergeadas em `develop`. Na revisão geral de 10/11 também foram feitos: `pure for` paralelo de verdade (padrão Map), regra semântica contra condição de corrida em `pure`, `print` seguro entre threads, exibição de erro sintático na interface didática, preenchimento dos cards de Speedup, correção do menu do terminal no Linux e do teste 7. Também foram feitos: alocação de subtarefas do `fork` em núcleo da CPU ou em outro computador (gramática, semântico, TAC, C++ e teste), `c_channel` sem perda de mensagens (teste 1 estável), TAC do teste 7 gerado de verdade pelo compilador (antes era um texto fixo), botão "Baixar .exe" compilando o código do editor, interfaces dos componentes no código (`src/componentes.py`) com a Tabela de Símbolos como componente próprio, comentários explicativos no código-fonte e testes automatizados de integração (`python3 -m unittest discover -s tests -v`). **Falta apenas o Relatório Final.** O texto abaixo é o planejamento original, mantido como histórico.

Com o compilador e os testes prontos, o que falta para fecharmos 100% do projeto até **11 de Novembro** são duas frentes bem objetivas:

### Etapa A: Revisar o PR Atual + Criar a 2ª Interface Web Didática (Fase 3)
O professor pediu para **manter a interface web atual** (rota `/`, tema escuro de desenvolvedor) e **adicionar uma 2ª Interface Web Didática** (ex: rota `/didatico` no `app.py`), voltada para ensino de compiladores (inspirada em `http://pesquisa06.lages.ifsc.edu.br/`).

**O que precisa ser feito no código web (`app.py`, `templates/didatico.html`, `static/`):**
1. **No `app.py`:**
   - Criar a rota `@app.route('/didatico')` renderizando `didatico.html` (e colocar um botão no topo das duas interfaces para alternar entre "Modo Desenvolvedor 2026.1" e "Modo Didático 2026.2").
   - Criar uma rota `@app.route('/api/inspect', methods=['POST'])` que recebe o código MiniPar e retorna em JSON:
     - **Tokens:** lista gerada por `Lexer(code).tokenize()` (tipo, lexema, linha, coluna).
     - **Árvore AST:** dicionário gerado por `ast_to_dict(program)` (que já deixamos pronto em `src/ast_nodes.py`!).
     - **Tabela de Símbolos:** lista gerada por `semantic.get_symbol_table()` (que já deixamos pronta em `src/semantic.py`!).
     - **TAC e C++:** textos gerados por `TACGenerator` e `CppCodeGenerator`.
   - Criar uma rota `@app.route('/api/download_exe/<nome>')` usando `send_file` do Flask para baixar o arquivo `.exe` compilado em `output/`.
2. **No Frontend (`templates/didatico.html` + JS/CSS):**
   - Editor de código à esquerda + seletor de programas de teste (1 a 10).
   - Botões para alternar a visualização à direita:
     - **Tokens - Lexer** (tabela com os tokens).
     - **AST - Análise Sintática** (**Ponto que o professor mais destacou:** desenhar a árvore visualmente como nós e setas usando D3.js / SVG a partir do JSON do `ast_to_dict`, bem limpa e didática).
     - **Análise Semântica** (tabela de símbolos com nome, tipo, escopo e linha).
     - **TAC (3 Endereços)** e **Código C++ Gerado**.
     - **Compilar & Baixar `.exe`** e **Executar** (mostrando a saída e o benchmark).

---

### Etapa B: Atualizar BNF, Modelagem UML de Componentes e Relatório Final (Fase 4)
1. **Atualizar a Gramática BNF (`BNF-grammar.md`):**
   - Incluir no arquivo `BNF-grammar.md` as novas regras sintáticas implementadas (`pure`, `impure`, `fork`, `join`).
2. **Modelagem UML de Componentes de Software:**
   - O professor exige no relatório os diagramas UML representando cada módulo do compilador como um Componente de Software (Interfaces `ILexico`, `ISintatico`, `ISemantico`, `ITAC`, `ICodeGen` e classes `C_...`), além do Diagrama de Casos de Uso e Diagrama de Classes.
3. **Escrita do Relatório Final (Seguindo as 17 seções do documento do professor):**
   - Juntar a BNF atualizada, os pseudocódigos (Lexer, Parser, Semântico e Tabela de Símbolos), Product/Sprint Backlog (Scrum), Diagramas UML, prints da nova Interface Web Didática (mostrando a árvore AST gráfica) e os prints dos benchmarks dos Testes 8, 9 (Mandelbrot) e 10.

---

## 4. Sugestão de Organização entre Nós 3

Para que o trabalho fique bem dividido (~33% para cada um) e todo mundo tenha domínio de uma parte clara na apresentação e no relatório:

| Frente | Responsabilidade Principal | Entregáveis no Relatório Final |
| :--- | :--- | :--- |
| **Frente 1 (Core & Benchmarks - Já adiantada no PR)** | Frontend (`lexer`, `parser`, `ast_nodes`, `semantic`) + Backend (`tac`, `codegen`, `cpp_template`) + Testes 8, 9 (Mandelbrot) e 10. | Seções de Análise Léxica, Sintática, Semântica, Tabela de Símbolos, Geração TAC/C++ e Tabelas/Prints de Benchmark dos Testes 8, 9 e 10. |
| **Frente 2 (2ª Interface Web Didática & Árvore AST Visual)** | Novas rotas no `app.py` (`/didatico`, `/api/inspect`, `/api/download_exe`) + Tela `didatico.html` + Renderização gráfica da Árvore AST em D3.js/SVG. | Seção 7 (Interface Web Didática do Compilador) e Seção 15.b (Passo a passo das telas de execução e visualização da AST). |
| **Frente 3 (Gramática BNF, Modelagem UML de Componentes & Gestão Ágil)** | Atualização do `BNF-grammar.md` + Diagramas UML (Casos de Uso, Arquitetura de Componentes `I...`/`C_...`, Diagrama de Classes) + Revisão/Integração dos Testes 1 a 10. | Seções de Gramática BNF, Product Backlog, Sprints Backlog (Scrum), Diagramas UML (Seções 8 a 13) e Consolidação do Relatório Final. |
