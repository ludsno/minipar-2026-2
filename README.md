# Compilador MiniPar 2026.2

**Trabalho da Disciplina de Compiladores — Universidade Federal de Alagoas (UFAL)**  
**Professor:** Arturo Hernandez Dominguez  
**Equipe de Desenvolvimento (2026.2):**  
- **Ludson Almeida** — [ludsno](https://github.com/ludsno)  
- **Davi Melo** — [davimelo7](https://github.com/davimelo7)  
- **Iury Nogueira** — [IuryNogueira](https://github.com/IuryNogueira)  

*(Base herdada e evoluída a partir do `minipar-improvement` de 2026.1)*

---

## 🚀 O que há de novo no MiniPar 2026.2?

A versão 2026.2 expande o compilador source-to-source com quatro grandes entregas arquiteturais:

1. **Anotações `pure` e `impure` (Modelo SPar — SBLP'21):**
   - Suporte ao paralelismo de dados (padrão *Map* / *parallel for*) com `pure for`.
   - Proteção automática de regiões com efeitos colaterais (*race conditions*) via `impure { ... }` traduzida para `std::lock_guard<std::mutex>`.
   - Validação semântica estrita: o compilador bloqueia o uso de `impure` fora de uma região `pure`.

2. **Primitivas Concorrentes `fork` e `join`:**
   - Disparo assíncrono de subtarefas em threads/núcleos dedicados da CPU via `fork <nome> { ... }`.
   - Barreira de sincronização determinística via `join;`.

3. **Benchmarks de Alto Desempenho Multi-Core (Speedup $\approx$ 3.98x):**
   - **Teste 8:** Avaliação paralela de 160 atividades em 4 núcleos.
   - **Teste 9:** 4 núcleos avaliando atividades + 5º núcleo calculando o **Fractal de Mandelbrot em ASCII** com `pure` e `impure`.
   - **Teste 10:** 6 núcleos executando carga completa com Mandelbrot e o **Tapete de Sierpinski**.

4. **2ª Interface Web Didática (Padrão IFSC) & Árvore AST Visual (D3.js / SVG):**
   - Nova interface educacional na rota `/didatico` com visual limpo e não poluído (inspirada no compilador do IFSC).
   - **Renderização Gráfica Interativa da AST** em SVG/D3.js com zoom, pan, centralização, busca de nós, subárvores colapsáveis e cores destacadas para `PureBlock`, `ImpureBlock`, `ForkBlock` e `JoinStmt`.
   - Abas dedicadas para: **Tokens Léxicos** (com badges e filtros), **Tabela de Símbolos** (com escopos e validações SPar), **Código TAC (3 Endereços)**, **Código C++20 Multithread**, **Benchmarks & Speedup** e **Download do Executável (.exe)**.
   - Botão de alternância instantânea entre **Tema Claro** e **Tema Escuro** com persistência em `localStorage`.
   - Preservação integral da **IDE de Desenvolvedor** na rota `/`.

---

## 📁 Estrutura do Repositório

```text
minipar-2026-2/
├── src/
│   ├── ast_nodes.py          # Nós da AST, hierarquia e serializador ast_to_dict()
│   ├── lexer.py              # Analisador Léxico (suporte a pure, impure, fork, join)
│   ├── parser.py             # Analisador Sintático
│   ├── semantic.py           # Analisador Semântico, Tabela de Símbolos e regras SPar
│   ├── tac.py                # Gerador de Código Intermediário (TAC - 3 endereços)
│   ├── codegen.py            # Gerador de Código C++20 multithread (threads e mutexes)
│   └── cpp_template.py       # Runtime C++ nativo (obter_tempo, simular_trabalho)
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
├── tests/                    # 15 Programas de Teste (Testes 1 a 10 + fractais + sanidade)
├── docs/
│   ├── MODELAGEM_UML_COMPONENTES.md  # Diagramas de Componentes, Casos de Uso e Classes
│   └── METODOLOGIA_AGIL_SCRUM.md     # Product Backlog, Sprints e DoD
├── output/                   # Arquivos gerados (.cpp, .tac e binários .exe)
├── temp_code/                # Códigos executados temporariamente pela IDE
├── app.py                    # Servidor Flask com rotas /didatico, /api/inspect, /api/download_exe
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
```

---

## 📊 Benchmarks de Desempenho Multi-Core

| Teste | Descrição | Núcleos | Tempo Sequencial | Tempo Paralelo | Speedup Atingido | Redução de Tempo |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Teste 8** | Avaliação de 160 atividades | 4 núcleos | ~2.40s | ~0.60s | **3.98x** | **74.8%** |
| **Teste 9** | 160 atividades + Fractal de Mandelbrot | 5 núcleos | ~3.12s | ~0.78s | **3.98x** | **74.9%** |
| **Teste 10** | Mandelbrot + Tapete de Sierpinski | 6 núcleos | ~3.98s | ~1.00s | **3.99x** | **74.9%** |

---

## 📚 Documentação Técnica Adicional

- [Gramática Formal BNF Atualizada (BNF-grammar.md)](BNF-grammar.md)
- [Modelagem UML de Componentes de Software (docs/MODELAGEM_UML_COMPONENTES.md)](docs/MODELAGEM_UML_COMPONENTES.md)
- [Metodologia Ágil, Product Backlog e Sprints (docs/METODOLOGIA_AGIL_SCRUM.md)](docs/METODOLOGIA_AGIL_SCRUM.md)
