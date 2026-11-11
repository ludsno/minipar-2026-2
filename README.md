# Compilador MiniPar 2026.2

**Trabalho da Disciplina de Compiladores — Universidade Federal de Alagoas (UFAL)**  
**Professor:** Arturo Hernandez Dominguez  
**Equipe de Desenvolvimento (2026.2):**  
- **Ludson Almeida** — [ludsno](https://github.com/ludsno)  
- **Davi Melo** — [davimelo7](https://github.com/DsML01)
- **Iury Nogueira** — [Iury Nogueira](https://github.com/IuryyNogueira)

*(Base herdada e evoluída a partir do `minipar-improvement` de 2026.1)*

---

## 🚀 O que há de novo no MiniPar 2026.2?

A versão 2026.2 expande o compilador source-to-source com quatro grandes entregas arquiteturais:

1. **Anotações `pure` e `impure` (Modelo SPar — SBLP'21):**
   - Paralelismo de dados (padrão *Map* / *parallel for*) com `pure for`: as iterações do laço são divididas entre os núcleos da CPU (`std::thread`, uma por núcleo lógico, com escalonamento dinâmico de blocos). A variável de ambiente `MINIPAR_PURE_THREADS=N` fixa o número de threads.
   - Proteção automática de regiões com efeitos colaterais (*race conditions*) via `impure { ... }` traduzida para `std::lock_guard<std::mutex>`.
   - Validação semântica estrita: o compilador bloqueia o uso de `impure` fora de uma região `pure` e também bloqueia, dentro de `pure`, a atribuição a variáveis externas ao laço fora de uma região `impure` (condição de corrida).
   - Laços `pure` com `break`/`return`, ou fora da forma canônica `for (var i = a; i < b; i = i + passo)` / `for (var x in colecao)`, são mantidos sequenciais por segurança.

2. **Primitivas Concorrentes `fork` e `join` com alocação em Núcleo ou Computador:**
   - Disparo assíncrono de subtarefas via `fork <nome> { ... }` e barreira de sincronização via `join;`.
   - **`fork t @nucleo(n) { ... }`**: a subtarefa roda numa thread fixada (afinidade) no núcleo `n` da CPU.
   - **`fork t @computador(ip, porta) { ... }`**: a subtarefa roda em **outro computador** (processo independente com o mesmo executável, iniciado com `MINIPAR_TRABALHADOR=<porta>`). Não há memória compartilhada: os dados vão e voltam por mensagens `c_channel`. Em `localhost` o programa inicia sozinho o processo trabalhador.
   - Canais `c_channel` com socket de escuta persistente (nenhuma mensagem se perde entre dois `receive`).

3. **Benchmarks Multi-Core:**
   - **Teste 8:** Avaliação paralela de 160 atividades em 4 núcleos (`fork @nucleo` / `join`) — tradução fiel do Python do enunciado.
   - **Teste 9:** 4 núcleos avaliando atividades + 5º núcleo calculando o **Fractal de Mandelbrot em ASCII** (idêntico ao do Python) com `pure` e `impure`.
   - **Teste 10:** 6 núcleos: avaliações + Mandelbrot + **Tapete de Sierpinski** (em ASCII; no Python era com Turtle).
   - **Teste Pure x Sequencial:** o mesmo Mandelbrot pesado (1600×1200) com `for` comum e com `pure for`, medindo o speedup real do paralelismo de dados.
   - **Teste Fork com Alocação:** a mesma tarefa dividida em 2 subtarefas, primeiro em 2 núcleos (`@nucleo`) e depois em 2 computadores (`@computador`).

4. **2ª Interface Web Didática (Padrão IFSC) & Árvore AST Visual (D3.js / SVG):**
   - Nova interface educacional na rota `/didatico` com visual limpo e não poluído (inspirada no compilador do IFSC).
   - **Renderização Gráfica Interativa da AST** em SVG/D3.js com zoom, pan, centralização, busca de nós, subárvores colapsáveis e cores destacadas para `PureBlock`, `ImpureBlock`, `ForkBlock` e `JoinStmt`.
   - Abas dedicadas para: **Tokens Léxicos** (com badges e filtros), **Tabela de Símbolos** (com escopos e validações SPar), **Código TAC (3 Endereços)**, **Código C++20 Multithread** e **Benchmarks & Speedup**, além do botão **Baixar .exe** (download do executável compilado).
   - Botão de alternância instantânea entre **Tema Claro** e **Tema Escuro** com persistência em `localStorage`.
   - Preservação integral da **IDE de Desenvolvedor** na rota `/`.

---

## 📁 Estrutura do Repositório

```text
minipar-2026-2/
├── src/
│   ├── componentes.py        # Interfaces dos componentes (ILexico, ISintatico, ISemantico, ITabelaSimbolos, ITAC, ICodeGen)
│   ├── ast_nodes.py          # Nós da AST, hierarquia e serializador ast_to_dict()
│   ├── lexer.py              # C_Lexer: Analisador Léxico (pure, impure, fork, join, @nucleo, @computador)
│   ├── parser.py             # C_Parser: Analisador Sintático descendente recursivo
│   ├── semantic.py           # C_Semantic + C_TabelaSimbolos: Analisador Semântico e Tabela de Símbolos
│   ├── tac.py                # C_TAC: Gerador de Código Intermediário (TAC - 3 endereços)
│   ├── codegen.py            # C_CodeGen: Gerador de Código C++20 multithread
│   └── cpp_template.py       # Runtime C++ (pure map, fork em núcleo/computador, c_channel, print atômico)
├── static/
│   ├── css/
│   │   ├── style.css         # Estilos da IDE de Desenvolvedor (Tema Claro e Escuro)
│   │   └── didatico.css      # Estilos da Interface Didática IFSC (Tema Claro e Escuro)
│   └── js/
│       ├── script.js         # Lógica da IDE do Desenvolvedor
│       └── didatico.js       # Visualizador D3.js v7 da AST, tabelas e inspeção
├── templates/
│   ├── index.html            # 1ª Interface Web: IDE do Desenvolvedor (Dracula/Neo)
│   └── didatico.html         # 2ª Interface Web: Ambiente Didático IFSC
├── tests/                    # 18 Programas de Teste (.minipar) + test_integracao_componentes.py (testes automatizados)
├── docs/
│   ├── MODELAGEM_UML_COMPONENTES.md  # Diagramas de Componentes, Casos de Uso e Classes
│   └── METODOLOGIA_AGIL_SCRUM.md     # Product Backlog, Sprints e DoD
├── output/                   # Arquivos gerados (.cpp, .tac e binários .exe)
├── temp_code/                # Códigos executados temporariamente pela IDE
├── app.py                    # Servidor Flask com rotas /didatico, /api/inspect, /api/build, /api/download_exe
├── main.py                   # Ponto de entrada unificado (CLI e Web)
├── menu.py                   # Menu interativo para terminal
├── BNF-grammar.md            # Gramática Formal BNF completa atualizada
├── requeriments.txt          # Dependências Python (Flask)
└── README.md
```

---

## ⚙️ Pré-requisitos e Instalação

- **Python 3.10+**
- **g++ com suporte a C++20** (`g++ -std=c++20`)
- **Flask**

Instale as dependências com:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requeriments.txt
```

---

## 🖥️ Como Executar

### 1. Iniciar a Interface Web (Recomendado)

Inicie o servidor Flask:

```bash
python3 app.py
```

Acesse no seu navegador:
- **Modo Didático (2026.2):** [http://127.0.0.1:5000/didatico](http://127.0.0.1:5000/didatico)
- **Modo Desenvolvedor (IDE):** [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

> *Você pode alternar entre as duas interfaces e trocar entre tema claro e escuro usando os botões na barra superior.*

### 2. Menu Interativo via Terminal

Execute sem argumentos:

```bash
python3 main.py
```

Escolha:
- `[1]` para o **Modo Terminal** (navegação textual pelos testes).
- `[2]` para iniciar o **Servidor Web**.

### 3. Compilação Direta via CLI

Para compilar e rodar qualquer programa `.minipar`:

```bash
# Teste de Sanidade das novas primitivas
python3 main.py tests/teste_sanidade_fase1.minipar
./output/teste_sanidade_fase1.exe

# Teste 9: Mandelbrot em 5 Núcleos com SPar
python3 main.py tests/teste9_mandelbrot_5nucleos.minipar
./output/teste9_mandelbrot_5nucleos.exe

# Teste 10: Carga Máxima em 6 Núcleos (Mandelbrot + Sierpinski)
python3 main.py tests/teste10_6nucleos_2fractais.minipar
./output/teste10_6nucleos_2fractais.exe

# Pure x Sequencial: speedup real do paralelismo de dados (pure for)
python3 main.py tests/teste_pure_speedup_mandelbrot.minipar
./output/teste_pure_speedup_mandelbrot.exe
MINIPAR_PURE_THREADS=4 ./output/teste_pure_speedup_mandelbrot.exe   # fixa 4 threads no pure

# Fork/Join com subtarefas alocadas em núcleos (@nucleo) e em computadores (@computador)
python3 main.py tests/teste_fork_nucleos_computadores.minipar
./output/teste_fork_nucleos_computadores.exe
```

### 4. Executando o `fork @computador` em computadores diferentes

Use o programa [`tests/demo_varios_computadores.minipar`](tests/demo_varios_computadores.minipar), que **não precisa ser editado** (ele pergunta os IPs ao rodar). Compile-o em cada computador e:

```bash
# PC2 e PC3 (trabalhadores) — abra primeiro
MINIPAR_TRABALHADOR=6201 ./output/demo_varios_computadores.exe    # no PC2
MINIPAR_TRABALHADOR=6202 ./output/demo_varios_computadores.exe    # no PC3
# PC1 (principal) — informe os IPs (ENTER = 127.0.0.1, tudo local)
./output/demo_varios_computadores.exe
```

Passo a passo completo (comandos para Windows, firewall, WSL2, ensaio com 3 terminais e o que fazer se algo travar): **[docs/COMO_DEMONSTRAR_VARIOS_COMPUTADORES.md](docs/COMO_DEMONSTRAR_VARIOS_COMPUTADORES.md)**.

### 5. Testes Automatizados de Integração dos Componentes

```bash
python3 -m unittest discover -s tests -v
```

São 32 testes: componentes isolados, integração Léxico → Sintático → Semântico → TAC/C++, os 18 programas de teste compilados e executados com conferência da saída, e a interface web (os testes web são pulados se o Flask não estiver instalado).

---

## 📊 Benchmarks de Desempenho Multi-Core

Os Testes 8, 9 e 10 são traduções fiéis dos programas Python fornecidos no enunciado (cópias em [`docs/referencia_python/`](docs/referencia_python/)): mesmo gerador pseudoaleatório (LCG, mesma semente), mesma carga de CPU por atividade (`int(segundos × 1.500.000)` iterações de soma) e o mesmo fractal de Mandelbrot (as 20 linhas são idênticas às do Python, conferido em `tests/test_integracao_componentes.py`). Os processos do Python viram subtarefas `fork ... @nucleo(n)`. Cada execução confere, no `join`, que o modo paralelo fez exatamente o mesmo trabalho que o sequencial.

Medições de 10/11/2026 na mesma máquina (Linux/WSL2, g++ 15.2 `-O3`, Python 3.14, CPU com 16 núcleos lógicos; mediana de 5 execuções):

| Teste | Descrição | Núcleos | MiniPar (C++) Seq. → Par. | Speedup MiniPar | Python (enunciado) Seq. → Par. | Speedup Python |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Teste 8** | Avaliação de 160 atividades | 4 | 12,1 ms → 3,8 ms | **~3,3x** | 370 ms → 140 ms | 2,6x |
| **Teste 9** | 160 atividades + Mandelbrot | 5 | 13,1 ms → 3,5 ms | **~3,9x** | 410 ms → 140 ms | 2,8x |
| **Teste 10** | 160 atividades + Mandelbrot + Sierpinski | 6 | 13,0 ms → 3,4 ms | **~3,8x** | — (precisa de tela gráfica/Turtle) | — |
| **Pure x Sequencial** | Mandelbrot 1600×1200, até 2000 iterações (`pure for`) | 16 threads | 1,86 s → 0,18 s | **~10x** | — | — |

> O mesmo trabalho roda cerca de **30x mais rápido** no MiniPar compilado (C++ `-O3`) do que no Python interpretado, e o paralelismo acelera mais (o Python gasta tempo criando processos). Como os tempos do MiniPar são de poucos milissegundos, o speedup dos Testes 8–10 varia um pouco entre execuções (~3,1x a ~4,0x); o limite teórico é ~4x, porque as 160 atividades são divididas entre 4 núcleos e os fractais levam menos de 1 ms. No enunciado, o professor obteve 1,18x / 1,02x / 0,52x com o Python em outra máquina.

Escalabilidade do `pure for` no teste Pure x Sequencial (variando `MINIPAR_PURE_THREADS`):

| Threads | 1 | 2 | 4 | 8 | 16 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Speedup** | 1.00x | 1.97x | 3.92x | 6.75x | ~10–12x |

---

## 📚 Documentação Técnica Adicional

- [Gramática Formal BNF Atualizada (BNF-grammar.md)](BNF-grammar.md)
- [Modelagem UML de Componentes de Software (docs/MODELAGEM_UML_COMPONENTES.md)](docs/MODELAGEM_UML_COMPONENTES.md)
- [Metodologia Ágil, Product Backlog e Sprints (docs/METODOLOGIA_AGIL_SCRUM.md)](docs/METODOLOGIA_AGIL_SCRUM.md)
