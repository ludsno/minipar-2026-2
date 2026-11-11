# Modelagem UML de Componentes de Software e Arquitetura — MiniPar 2026.2

**Projeto:** MiniPar 2026.2 — Compilador Source-to-Source Orientado a Objetos e Paralelo  
**Equipe:** Ludson Almeida · Davi Melo · Iury Nogueira  
**Instituição:** Universidade Federal de Alagoas (UFAL) — Instituto de Computação (IC)  
**Disciplina:** Compiladores — Prof. Arturo Hernandez Dominguez  

---

## 1. Visão Geral da Arquitetura

O compilador **MiniPar 2026.2** adota o paradigma de **Engenharia de Software Baseada em Componentes (CBSE - Component-Based Software Engineering)**. A arquitetura divide o pipeline de compilação em componentes de software modulares, independentes e fracamente acoplados, conectados através de **Interfaces Fornecidas (Provided Interfaces)** e **Interfaces Requeridas (Required Interfaces)**.

```
+-------------------------------------------------------------------------------------------------+
|                                 ARQUITETURA DE COMPONENTES MINIPAR 2026.2                       |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   [Código .minipar]                                                                             |
|          |                                                                                      |
|          v                                                                                      |
|   +---------------+  ILexico   +---------------+  ISintatico  +---------------+                 |
|   |    C_Lexer    |----------->|   C_Parser    |------------->|  C_Semantic   |                 |
|   +---------------+ (Tokens)   +---------------+    (AST)     +---------------+                 |
|                                        |                             |                          |
|                                        | AST                         | AST Validada             |
|                                        v                             v                          |
|                                +---------------+             +---------------+                  |
|                                |     C_TAC     |             |   C_CodeGen   |                  |
|                                +---------------+             +---------------+                  |
|                                 (3-Endereços)                        | (C++20)                  |
|                                        |                             v                          |
|                                        |                      +---------------+                 |
|                                        |                      |  Compilador   |                 |
|                                        |                      |   g++ (-O3)   |                 |
|                                        |                      +---------------+                 |
|                                        v                             v                          |
|                                  [Arquivo .tac]               [Binário .exe]                    |
|                                                                                                 |
|   +-----------------------------------------------------------------------------------------+   |
|   |                            INTERFACES DE USUÁRIO (CAMADA DE APRESENTAÇÃO)               |   |
|   |                                                                                         |   |
|   |   +-------------------+    +--------------------+    +------------------------------+   |   |
|   |   |   C_CLI (Menu)    |    |   C_WebIDE (/)     |    |   C_DidacticWeb (/didatico)  |   |   |
|   |   |  Terminal ANSI    |    |  Tema Escuro 2026.1|    |   Árvore AST D3.js + Tokens  |   |   |
|   |   +-------------------+    +--------------------+    +------------------------------+   |   |
|   +-----------------------------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Diagrama de Componentes de Software (UML 2.5)

Abaixo está o diagrama formal de componentes segundo a notação UML (com portas, interfaces requeridas e fornecidas):

```mermaid
classDiagram
    direction LR

    class ILexico {
        <<interface>>
        +tokenize() List~Token~
    }

    class ISintatico {
        <<interface>>
        +parse() Program
    }

    class ISemantico {
        <<interface>>
        +analyze(program: Program) bool
        +get_symbol_table() List~Symbol~
        +get_errors() List~string~
    }

    class ITabelaSimbolos {
        <<interface>>
        +entrar_escopo()
        +sair_escopo()
        +declarar(nome, tipo, escopo, linha, params) bool
        +buscar(nome) Symbol
        +get_symbol_table() List~Map~
    }

    class ITAC {
        <<interface>>
        +generate_text(program: Program) string
        +generate(program: Program, output_name: string) string
    }

    class ICodeGen {
        <<interface>>
        +generate_cpp_code(program: Program) string
        +generate(program: Program, output_name: string) bool
    }

    class IInspectService {
        <<interface>>
        +inspect_code(code: string, filename: string) Map
        +download_executable(filename: string) File
    }

    class C_Lexer {
        <<component>>
        -source: string
        -pos: int
        -line: int
        -col: int
        +tokenize()
    }

    class C_Parser {
        <<component>>
        -tokens: List~Token~
        -pos: int
        +parse()
        -_parse_pure_block()
        -_parse_impure_block()
        -_parse_fork_block()
        -_parse_join_stmt()
    }

    class C_Semantic {
        <<component>>
        -tabela: C_TabelaSimbolos
        -inside_pure: bool
        -pure_scope_base: int
        -remote_scope_base: int
        +analyze()
        +get_symbol_table()
    }

    class C_TabelaSimbolos {
        <<component>>
        -escopos: List~Map~
        -historico: List~Map~
        +declarar()
        +buscar()
    }

    class C_TAC {
        <<component>>
        -lines: List~string~
        -temp_count: int
        -label_count: int
        +generate_text()
    }

    class C_CodeGen {
        <<component>>
        +generate_cpp_code()
        +generate()
    }

    class C_DidacticWeb {
        <<component>>
        +render_didatico()
        +render_ast_d3()
    }

    C_Lexer ..|> ILexico : Fornece
    C_Parser ..> ILexico : Requer
    C_Parser ..|> ISintatico : Fornece
    C_Semantic ..> ISintatico : Requer
    C_Semantic ..|> ISemantico : Fornece
    C_Semantic ..> ITabelaSimbolos : Requer
    C_TabelaSimbolos ..|> ITabelaSimbolos : Fornece
    C_TAC ..> ISintatico : Requer
    C_TAC ..> ISemantico : Requer
    C_TAC ..|> ITAC : Fornece
    C_CodeGen ..> ISintatico : Requer
    C_CodeGen ..> ISemantico : Requer
    C_CodeGen ..|> ICodeGen : Fornece
    C_DidacticWeb ..|> IInspectService : Fornece
    C_DidacticWeb ..> ILexico : Requer
    C_DidacticWeb ..> ISintatico : Requer
    C_DidacticWeb ..> ISemantico : Requer
    C_DidacticWeb ..> ITAC : Requer
    C_DidacticWeb ..> ICodeGen : Requer
```

### Correspondência no Código-Fonte

As interfaces estão implementadas como classes abstratas em `src/componentes.py` (mesmo padrão do exemplo `IRelogio` / `Relogio` do Anexo 2 do enunciado), e cada componente é a classe concreta que as implementa:

| Componente UML | Classe no código | Interface (classe abstrata) | Arquivo |
| :--- | :--- | :--- | :--- |
| `C_Lexer` | `Lexer` | `ILexico` | `src/lexer.py` |
| `C_Parser` | `Parser` | `ISintatico` | `src/parser.py` |
| `C_Semantic` | `SemanticAnalyzer` | `ISemantico` | `src/semantic.py` |
| `C_TabelaSimbolos` | `TabelaSimbolos` | `ITabelaSimbolos` | `src/semantic.py` |
| `C_TAC` | `TACGenerator` | `ITAC` | `src/tac.py` |
| `C_CodeGen` | `CppCodeGenerator` | `ICodeGen` | `src/codegen.py` |
| `C_DidacticWeb` | rotas Flask em `app.py` + `didatico.js` | `IInspectService` (`/api/inspect`, `/api/build`, `/api/download_exe`) | `app.py` |

A conformidade é verificada automaticamente em `tests/test_integracao_componentes.py` (classe `T1_InterfacesDosComponentes`).

### Especificação das Interfaces dos Componentes:

| Componente | Interface Fornecida | Interface Requerida | Papel no Pipeline |
| :--- | :--- | :--- | :--- |
| **`C_Lexer`** | `ILexico` | Nenhuma (Lê código bruto) | Converte o fluxo de caracteres em tokens (com suporte a `pure`, `impure`, `fork`, `join`). |
| **`C_Parser`** | `ISintatico` | `ILexico` | Constrói a Árvore Sintática Abstrata (AST) e a exporta para JSON hierárquico (`ast_to_dict`). |
| **`C_Semantic`** | `ISemantico` | `ISintatico`, `ITabelaSimbolos` | Valida escopos e tipos e impõe as regras de paralelismo (`impure` só dentro de `pure`; sem escrita externa em `pure` fora de `impure`; `fork @computador` sem variáveis externas). |
| **`C_TabelaSimbolos`** | `ITabelaSimbolos` | Nenhuma | Pilha de escopos e histórico de todos os símbolos (nome, tipo, escopo, linha, parâmetros). |
| **`C_TAC`** | `ITAC` | `ISintatico`, `ISemantico` | Gera Código de 3 Endereços com diretivas `BEGIN_PURE_MAP`, `ACQUIRE_LOCK`, `FORK_TASK`, `JOIN_TASKS`. |
| **`C_CodeGen`** | `ICodeGen` | `ISintatico`, `ISemantico` | Transpila a AST para C++20 multithread (`std::thread`, `std::mutex`, `std::lock_guard`) e invoca `g++`. |
| **`C_DidacticWeb`** | `IInspectService` | `ILexico`, `ISintatico`, `ISemantico`, `ITAC`, `ICodeGen` | Painel web educacional padrão IFSC com AST gráfica em SVG/D3.js, badges de tokens e download do `.exe`. |

---

## 3. Diagrama de Casos de Uso (UML Use Case)

Descreve todas as interações dos atores humanos (estudante e desenvolvedor) e externos (sistema operacional / compilador GCC) com o MiniPar 2026.2:

```mermaid
flowchart LR
    subgraph Atores
        Aluno["🎓 Aluno / Estudante"]
        Dev["💻 Desenvolvedor"]
        OS["⚙️ SO / Compilador g++"]
    end

    subgraph "Sistema Compilador MiniPar 2026.2"
        UC01["UC01: Editar / Selecionar Código MiniPar (Testes 1 a 10)"]
        UC02["UC02: Inspecionar Pipeline Didático"]
        UC02_1["UC02.1: Analisar Tabela de Tokens e Categorias"]
        UC02_2["UC02.2: Visualizar Árvore AST Gráfica (D3.js/SVG)"]
        UC02_3["UC02.3: Inspecionar Tabela de Símbolos & Escopos"]
        UC02_4["UC02.4: Validar Regras SPar (Impure dentro de Pure)"]
        UC02_5["UC02.5: Visualizar Código TAC (3 Endereços)"]
        UC02_6["UC02.6: Visualizar Código C++20 Multithread"]
        UC03["UC03: Compilar e Executar Binário Nativo"]
        UC04["UC04: Executar Benchmarks Multi-Core (4, 5 e 6 Núcleos)"]
        UC05["UC05: Baixar Executável (.exe) Compilado"]
        UC06["UC06: Alternar entre Modo Didático e Desenvolvedor"]
        UC07["UC07: Alternar Tema (Claro / Escuro)"]
    end

    Aluno --> UC01
    Aluno --> UC02
    Aluno --> UC03
    Aluno --> UC04
    Aluno --> UC05
    Aluno --> UC06
    Aluno --> UC07

    Dev --> UC01
    Dev --> UC03
    Dev --> UC04

    UC02 -.->|<<include>>| UC02_1
    UC02 -.->|<<include>>| UC02_2
    UC02 -.->|<<include>>| UC02_3
    UC02 -.->|<<include>>| UC02_4
    UC02 -.->|<<include>>| UC02_5
    UC02 -.->|<<include>>| UC02_6

    UC03 --> OS
    UC04 --> OS
    UC05 --> OS
```

---

## 4. Diagrama de Classes UML (Nós da AST e Compilador)

### 4.1 Hierarquia dos Nós da AST (src/ast_nodes.py)

```mermaid
classDiagram
    direction TB

    class ASTNode {
        +int line
    }

    class Program {
        +List~ASTNode~ statements
    }

    class SeqBlock {
        +List~ASTNode~ statements
    }

    class ParBlock {
        +List~ASTNode~ statements
    }

    class PureBlock {
        +ASTNode body
    }

    class ImpureBlock {
        +List~ASTNode~ statements
    }

    class ForkBlock {
        +ASTNode body
        +string task_name
        +string alloc_kind
        +List~ASTNode~ alloc_args
    }

    class JoinStmt {
        +List~string~ target_tasks
    }

    class ClassDecl {
        +string name
        +string superclass
        +List~VarDecl~ attributes
        +List~FuncDecl~ methods
    }

    class FuncDecl {
        +string name
        +List~string~ params
        +ASTNode body
    }

    class ForStmt {
        +ASTNode initializer
        +ASTNode condition
        +ASTNode increment
        +ASTNode body
    }

    class IfStmt {
        +ASTNode condition
        +ASTNode then_branch
        +ASTNode else_branch
    }

    class WhileStmt {
        +ASTNode condition
        +ASTNode body
    }

    class VarDecl {
        +string name
        +ASTNode init_value
        +string type
    }

    class BinaryExpr {
        +string op
        +ASTNode left
        +ASTNode right
    }

    class IdentifierExpr {
        +string name
    }

    class NumberExpr {
        +string value
    }

    ASTNode <|-- Program
    ASTNode <|-- SeqBlock
    ASTNode <|-- ParBlock
    ASTNode <|-- PureBlock
    ASTNode <|-- ImpureBlock
    ASTNode <|-- ForkBlock
    ASTNode <|-- JoinStmt
    ASTNode <|-- ClassDecl
    ASTNode <|-- FuncDecl
    ASTNode <|-- ForStmt
    ASTNode <|-- IfStmt
    ASTNode <|-- WhileStmt
    ASTNode <|-- VarDecl
    ASTNode <|-- BinaryExpr
    ASTNode <|-- IdentifierExpr
    ASTNode <|-- NumberExpr
```

---

## 5. Diagrama de Sequência UML (Fluxo de Inspeção Didática)

Demonstra como as requisições disparadas pelo usuário na Interface Didática (`POST /api/inspect`) percorrem sequencialmente todos os componentes do compilador:

```mermaid
sequenceDiagram
    autonumber
    actor Aluno as Estudante / Navegador
    participant UI as C_DidacticWeb (Frontend JS)
    participant Flask as app.py (Controller)
    participant Lex as C_Lexer
    participant Parse as C_Parser
    participant Sem as C_Semantic
    participant TAC as C_TAC
    participant Cpp as C_CodeGen

    Aluno->>UI: Clica em "Inspecionar Pipeline"
    UI->>Flask: POST /api/inspect { code, filename }
    activate Flask

    Flask->>Lex: tokenize(code)
    activate Lex
    Lex-->>Flask: Retorna tokens com categoria, linha e coluna
    deactivate Lex

    Flask->>Parse: parse(tokens)
    activate Parse
    Parse-->>Flask: Retorna objeto Program (AST)
    deactivate Parse

    Flask->>Parse: ast_to_dict(program)
    activate Parse
    Parse-->>Flask: Retorna JSON hierárquico da AST
    deactivate Parse

    Flask->>Sem: analyze(program)
    activate Sem
    Sem-->>Flask: Retorna validação (bool), Tabela de Símbolos e Erros
    deactivate Sem

    Flask->>TAC: generate_text(program)
    activate TAC
    TAC-->>Flask: Retorna código TAC (3 endereços)
    deactivate TAC

    Flask->>Cpp: generate_cpp_code(program)
    activate Cpp
    Cpp-->>Flask: Retorna código C++20 multithread
    deactivate Cpp

    Flask-->>UI: Resposta JSON { success, tokens, ast, symbols, tac, cpp }
    deactivate Flask

    UI->>UI: Renderiza Tabela de Tokens com Badges
    UI->>UI: Renderiza Árvore AST Visual em SVG via D3.js
    UI->>UI: Renderiza Tabela de Símbolos & Checklist Semântico
    UI->>UI: Exibe TAC e C++ formatados
    UI-->>Aluno: Exibição interativa completa na tela!
```

---

## 6. Diagrama de Sequência UML (Compilação, Execução e Benchmark)

Demonstra o fluxo ao clicar em **"Executar"** com medição de **Speedup**:

```mermaid
sequenceDiagram
    autonumber
    actor Aluno as Estudante / Navegador
    participant UI as C_DidacticWeb (Frontend JS)
    participant Flask as app.py (Controller)
    participant Compiler as main.py (Compilador)
    participant GCC as g++ (-std=c++20 -O3)
    participant EXE as Binário Nativo (.exe)

    Aluno->>UI: Clica em "Executar"
    UI->>Flask: POST /api/compile { code, filename, inputs }
    activate Flask

    Flask->>Compiler: Executa main.py via subprocess
    activate Compiler
    Compiler->>GCC: Invoca g++ com -std=c++20 -O3 -pthread
    activate GCC
    GCC-->>Compiler: Gera executável output/<nome>.exe
    deactivate GCC
    Compiler-->>Flask: Compilação concluída com sucesso (code 0)
    deactivate Compiler

    Flask->>EXE: Executa binário nativo (inicia cronômetro)
    activate EXE
    EXE-->>Flask: Execução finalizada (retorna stdout com Speedup e tempos)
    deactivate EXE

    Flask->>Flask: Extrai métricas (Speedup, T_seq, T_par, % redução)
    Flask-->>UI: Retorna JSON { success: true, stdout, benchmark }
    deactivate Flask

    UI->>UI: Atualiza Terminal com a saída do programa
    UI->>UI: Atualiza Cards de KPI (Speedup ex: 3.98x, T_seq, T_par)
    UI-->>Aluno: Exibe resultado e métricas de aceleração
```

---

## 7. Diagrama de Sequência UML (Fork com Alocação em Outro Computador)

Demonstra `fork t @computador(ip, porta) { ... }`: o mesmo executável roda nos dois computadores; o computador trabalhador foi iniciado com `MINIPAR_TRABALHADOR=<porta>` (em `localhost`, o próprio programa o inicia). Não há memória compartilhada: os dados trafegam por `c_channel`.

```mermaid
sequenceDiagram
    autonumber
    participant Main as Computador 1 (programa principal)
    participant Fork as Thread do fork t
    participant Worker as Computador 2 (MINIPAR_TRABALHADOR=porta)

    Main->>Fork: fork t @computador(ip, porta)
    activate Fork
    Fork->>Worker: conecta em ip:porta e envia "EXEC t#0"
    activate Worker
    Main->>Worker: send(canal_dados, n)  (c_channel)
    Worker->>Worker: executa o corpo da subtarefa t
    Worker->>Main: send(canal_resultado, resultado)  (c_channel)
    Worker-->>Fork: "FIM"
    deactivate Worker
    Fork-->>Main: thread do fork termina
    deactivate Fork
    Main->>Main: join (barreira)
    Main->>Worker: "SAIR" (fim do programa, __minipar_finalizar)
```
