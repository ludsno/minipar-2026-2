# Metodologia Ágil (Scrum) — MiniPar 2026.2

**Projeto:** MiniPar 2026.2 — Compilador Source-to-Source Orientado a Objetos e Paralelo  
**Equipe:** Ludson Almeida · Davi Melo · Iury Nogueira  
**Instituição:** Universidade Federal de Alagoas (UFAL) — Instituto de Computação (IC)  
**Disciplina:** Compiladores — Prof. Arturo Hernandez Dominguez  

---

## 1. Visão do Produto (Product Vision)

> *"Para estudantes de computação e pesquisadores que necessitam compreender a teoria e a prática da construção de compiladores para arquiteturas multi-core, o **MiniPar 2026.2** é um compilador educacional source-to-source que traduz código MiniPar para C++20 nativo de alto desempenho. Diferente de compiladores tradicionais que operam como 'caixas-pretas', o MiniPar oferece uma **2ª Interface Web Didática e Interativa (estilo IFSC)** com inspeção gráfica da Árvore Sintática (AST) em D3.js/SVG, além de primitivas modernas de paralelismo de dados (modelo **SPar Pure/Impure**) e concorrência (**Fork/Join**) com validação automática de condições de corrida e aceleração multi-core comprovada em fractais como o Conjunto de Mandelbrot."*

---

## 2. Product Backlog Priorizado

| ID | Épico | User Story (Como... Quero... Para...) | Critérios de Aceitação | Est. (SP) | Prioridade | Sprint |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **US01** | Core SPar | **Como** programador MiniPar, **quero** anotar laços com `pure` e regiões críticas com `impure`, **para que** o compilador paralelize dados com segurança. | O lexer reconhece `pure`/`impure` (e `@pure`/`@impure`); parser cria nós `PureBlock` e `ImpureBlock`. | 8 | Alta | Sprint 1 |
| **US02** | Core Concorrência | **Como** programador, **quero** disparar subtarefas assíncronas com `fork` e sincronizá-las com `join`, **para** paralelizar tarefas independentes na CPU. | Parser reconhece `fork [nome] { ... }` e `join;`, gerando nós `ForkBlock` e `JoinStmt` na AST. | 5 | Alta | Sprint 1 |
| **US03** | Semântico | **Como** professor/aluno, **quero** que o compilador bloqueie o uso de `impure` fora de um bloco `pure`, **para** garantir a correção do modelo SPar. | Emite erro semântico amigável caso `impure` seja usado fora de `pure`; exporta tabela de símbolos com escopos. | 5 | Alta | Sprint 1 |
| **US04** | TAC Paralelo | **Como** estudante, **quero** inspecionar o código intermediário gerado com diretivas de paralelismo, **para** entender como laços puros e locks são mapeados. | Emite `BEGIN_PURE_MAP`, `END_PURE_MAP`, `ACQUIRE_LOCK`, `RELEASE_LOCK`, `FORK_TASK` e `JOIN_TASKS`. | 5 | Média | Sprint 2 |
| **US05** | Codegen C++20 | **Como** desenvolvedor, **quero** transpolar o MiniPar para C++20 com `std::thread` e `std::mutex`, **para** gerar binários executáveis nativos com `-O3`. | Gera C++ válido que compila via `g++ -std=c++20 -O3 -pthread`; executa sem race conditions. | 8 | Alta | Sprint 2 |
| **US06** | Benchmarks | **Como** avaliador, **quero** rodar os Testes 8, 9 (Mandelbrot) e 10 medindo o tempo sequencial vs. paralelo, **para** comprovar o Speedup da linguagem. | Teste 8 (4 cores), Teste 9 (5 cores com Mandelbrot) e Teste 10 (6 cores) atingem Speedup $\approx 3.98\text{x}$. | 8 | Alta | Sprint 2 |
| **US07** | Rota Didática | **Como** aluno, **quero** acessar uma 2ª interface web limpa no navegador (`/didatico`), **para** inspecionar o pipeline educacional sem perder a IDE original. | Nova rota `/didatico` no Flask; botão no topo de ambas as telas para alternar de modo. | 5 | Média | Sprint 3 |
| **US08** | API Inspect | **Como** frontend web, **quero** receber em um único JSON todos os dados do compilador, **para** alimentar as abas do pipeline dinamicamente. | Rota `POST /api/inspect` retorna tokens, AST em dict, tabela de símbolos, TAC e C++. | 5 | Alta | Sprint 3 |
| **US09** | AST Gráfica D3 | **Como** professor/aluno, **quero** ver a AST desenhada com caixas e setas em SVG interativo, **para** visualizar a hierarquia sintática de forma clara. | Renderização SVG/D3.js com zoom, pan, centralização, busca de nós, subárvores colapsáveis e cores para SPar/Fork. | 13 | Alta | Sprint 3 |
| **US10** | Download .exe | **Como** usuário, **quero** baixar diretamente o binário `.exe` compilado pelo navegador, **para** rodá-lo localmente na minha máquina. | Rota `GET /api/download_exe/<nome>` retorna o executável como attachment binário. | 3 | Média | Sprint 3 |
| **US11** | Alternância Temas | **Como** usuário, **quero** alternar entre tema claro e tema escuro em ambas as interfaces, **para** ter conforto visual e consistência de uso. | Botão de alternância com persistência em `localStorage`; adapta CodeMirror e canvas da AST. | 3 | Baixa | Sprint 3 |
| **US12** | Gramática BNF | **Como** aluno/professor, **quero** consultar a BNF formal atualizada com as novas produções, **para** verificar a gramática exata da linguagem. | Arquivo `BNF-grammar.md` atualizado com todas as regras de `pure`, `impure`, `fork`, `join` e C++. | 5 | Alta | Sprint 4 |
| **US13** | Modelagem UML | **Como** engenheiro de software, **quero** a arquitetura do compilador modelada em componentes UML com interfaces `I...`, **para** cumprir a exigência do edital. | Diagramas de Componentes, Classes, Casos de Uso e Sequência em padrão Mermaid. | 8 | Alta | Sprint 4 |
| **US14** | Relatório Final | **Como** equipe, **quero** consolidar o relatório técnico de 17 seções, **para** entregar a avaliação final da disciplina ao professor Arturo. | Documento final com pseudocódigos, prints das telas, tabelas de benchmark e UML. | 13 | Alta | Sprint 4 |
| **US15** | Fork Distribuído | **Como** programador, **quero** alocar cada subtarefa do `fork` em um núcleo da CPU (`@nucleo(n)`) ou em outro computador (`@computador(ip, porta)`), **para** cumprir o requisito de alocação do enunciado. | Gramática com `<alocacao>`; thread fixada no núcleo; subtarefa executada por outro processo/computador com dados só por `c_channel`; semântico bloqueia variáveis externas em `@computador`. | 8 | Alta | Sprint 4 |
| **US16** | Testes de Integração | **Como** equipe, **quero** testes automatizados dos componentes e dos 17 programas, **para** garantir a não-regressão e documentar a Seção 13 do relatório. | `python3 -m unittest discover -s tests -v` executa 32 testes (componentes, integração entre fases, programas de teste e interface web). | 5 | Alta | Sprint 4 |

---

## 3. Planejamento e Execução das Sprints

```
CRONOGRAMA ÁGIL DE EXECUÇÃO:
+--------------------+--------------------+--------------------+--------------------+
|     SPRINT 1       |     SPRINT 2       |     SPRINT 3       |     SPRINT 4       |
|  (22/10 a 27/10)   |  (28/10 a 02/11)   |  (03/11 a 07/11)   |  (08/11 a 11/11)   |
+--------------------+--------------------+--------------------+--------------------+
| - Lexer tokens     | - Geração TAC      | - Rotas Flask      | - Atualização BNF  |
| - Parser produções | - Codegen C++20    | - Tela didatico    | - Modelagem UML    |
| - Nós AST JSON     | - Testes 8, 9, 10  | - AST D3.js / SVG  | - Backlog Scrum    |
| - Semântico SPar   | - Mandelbrot Speed | - Download .exe    | - Relatório Final  |
+--------------------+--------------------+--------------------+--------------------+
```

### Sprint 1: Núcleo Sintático e Semântico (SPar & Concorrência)
- **Objetivo da Sprint:** Estender o frontend do compilador para reconhecer as novas anotações da linguagem e aplicar a validação semântica do artigo SPar.
- **Itens Entregues:** US01, US02, US03.
- **Resultados:** `src/lexer.py` atualizado com novos tokens; `src/ast_nodes.py` com `PureBlock`, `ImpureBlock`, `ForkBlock`, `JoinStmt` e função `ast_to_dict()`; `src/semantic.py` bloqueando `impure` sem `pure`.

### Sprint 2: Backend Paralelo e Benchmarks de Desempenho
- **Objetivo da Sprint:** Implementar a geração de TAC, a transpilação para threads/locks C++20 e validar os benchmarks multi-core obrigatórios.
- **Itens Entregues:** US04, US05, US06.
- **Resultados:** Instruções `BEGIN_PURE_MAP` e `ACQUIRE_LOCK` no `.tac`; código C++ compilado com `g++ -O3 -pthread`; **Teste 8 (4 núcleos)**, **Teste 9 (5 núcleos com Mandelbrot)** e **Teste 10 (6 núcleos)** com Speedup de **3.98x**.

### Sprint 3: 2ª Interface Web Didática e Visualizador Gráfico da AST
- **Objetivo da Sprint:** Construir a nova interface educacional (padrão IFSC), renderizar a árvore sintática interativa em SVG/D3.js e implementar download do `.exe`.
- **Itens Entregues:** US07, US08, US09, US10, US11.
- **Resultados:** Rota `/didatico` e `/api/inspect` funcionais; visualizador gráfico de nós em D3.js com zoom/pan e colapso de nós; tabela de tokens e símbolos; suporte a temas Claro/Escuro.

### Sprint 4: Engenharia de Software, BNF e Relatório Técnico
- **Objetivo da Sprint:** Formalizar a gramática da linguagem, gerar a modelagem UML baseada em componentes e consolidar a documentação final.
- **Itens Entregues:** US12, US13, US15, US16 e US14 (relatório em conclusão).
- **Resultados:** `BNF-grammar.md` atualizado; `docs/MODELAGEM_UML_COMPONENTES.md` com diagramas formais; `docs/METODOLOGIA_AGIL_SCRUM.md` formalizando o processo ágil.

---

## 4. Definição de Pronto (Definition of Done - DoD)

Para que uma funcionalidade seja considerada **Concluída (Done)**, ela deve atender aos seguintes critérios de qualidade:

1. **Compilação sem Erros:** O código-fonte em Python deve ser livre de erros de sintaxe e passar nos testes de integração dos componentes (`python3 -m unittest discover -s tests -v`).
2. **Execução de Binário C++20:** Todo código MiniPar deve compilar via `g++ -std=c++20 -O3` gerando binário executável funcional.
3. **Não-Regressão dos 17 Programas de Teste:** Todos os testes históricos (1 a 7) e novos (8, 9, 10 e adicionais) devem executar com a saída esperada (verificado em `T6_ProgramasDeTeste`).
4. **Inspeção na Interface Didática:** A árvore AST e a tabela de tokens devem renderizar corretamente sem quebras de layout.
5. **Código Versionado:** Branches semânticas criadas e mergeadas via Pull Request revisado no repositório.

---

## 5. Distribuição de Responsabilidades da Equipe (~33% cada)

| Integrante | Responsabilidade Principal | Entregas Técnicas |
| :--- | :--- | :--- |
| **Ludson Almeida** | **Core do Compilador & Benchmarks (Frente 1)** | Implementação do Lexer, Parser e Semântico de `pure`/`impure`/`fork`/`join`, TAC, Codegen C++20 e calibração dos Testes 8, 9 (Mandelbrot) e 10. |
| **Davi Melo** | **2ª Interface Web Didática & Árvore AST Visual (Frente 2)** | Desenvolvimento de `app.py` (`/didatico`, `/api/inspect`, `/api/download_exe`), `templates/didatico.html`, visualizador SVG/D3.js da AST e alternância de temas. |
| **Iury Nogueira** | **Engenharia de Software, BNF & Relatório (Frente 3)** | Atualização da Gramática Formal `BNF-grammar.md`, Diagramas UML de Componentes de Software, Casos de Uso, Classes, Metodologia Scrum e Relatório Técnico. |

