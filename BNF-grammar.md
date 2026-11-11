# Gramática Formal BNF — Linguagem MiniPar 2026.2

**Projeto:** MiniPar 2026.2 — Compilador da Linguagem MiniPar com Paralelismo de Dados SPar (`pure`/`impure`), Concorrência (`fork`/`join`) e 2ª Interface Web Didática  
**Equipe:** Ludson Almeida · Davi Melo · Iury Nogueira  
**Instituição:** Universidade Federal de Alagoas — Instituto de Computação · Ciência da Computação  
**Disciplina:** Compiladores — Prof. Arturo Hernandez Dominguez  
**Base do Projeto:** Evolução do minipar-improvement  

---

> Esta gramática foi atualizada para a versão **MiniPar 2026.2**, derivada diretamente da
> implementação real do compilador (`src/lexer.py`, `src/parser.py`, `src/ast_nodes.py`,
> `src/semantic.py`, `src/tac.py` e `src/codegen.py`), incorporando o modelo de
> anotações do artigo SPar (SBLP'21) para paralelismo de dados e o modelo de tarefas
> concorrentes com fork e join para execução multi-core.
> Ela descreve **toda** a sintaxe aceita pelo compilador MiniPar 2026.2.

---

## Sumário

1. [Notação utilizada](#1-notação-utilizada)
2. [Tokens (Análise Léxica)](#2-tokens-análise-léxica)
3. [Programa](#3-programa)
4. [Declarações](#4-declarações)
5. [Comandos](#5-comandos)
6. [Blocos Sequencial e Paralelo](#6-blocos-sequencial-e-paralelo)
7. [Estruturas de Controle](#7-estruturas-de-controle)
8. [Orientação a Objetos](#8-orientação-a-objetos)
9. [Funções](#9-funções)
10. [Expressões](#10-expressões)
11. [Comunicação por Canais](#11-comunicação-por-canais)
12. [Coleções](#12-coleções)
13. [Entrada e Saída](#13-entrada-e-saída)
14. [Tipos e Literais](#14-tipos-e-literais)
15. [Biblioteca Nativa](#15-biblioteca-nativa)
16. [Comentários](#16-comentários)
17. [Gramática Consolidada (BNF Completa)](#17-gramática-consolidada-bnf-completa)

---

## 1. Notação utilizada

| Símbolo | Significado |
|---------|-------------|
| `::=` | Definição de produção |
| `\|` | Alternativa (ou) |
| `{ x }` | Zero ou mais repetições de `x` |
| `[ x ]` | Opcional (zero ou uma ocorrência de `x`) |
| `( x )` | Agrupamento |
| `"token"` | Terminal literal (palavra reservada ou símbolo) |
| `<não-terminal>` | Símbolo não-terminal |

---

## 2. Tokens (Análise Léxica)

O analisador léxico (`src/lexer.py`) produz os seguintes tokens a partir do código-fonte.  
Comentários iniciados por `#` são descartados pelo lexer antes da geração de tokens.

### 2.1 Palavras Reservadas

```
class  extends  new  func  var
if  else  while  do  for  in
break  continue  return
seq  par  pure  impure  fork  join  this
c_channel  send  receive  input  print  matrix
true  false
number  int  string  bool  void  list  dict
```

> **Nota 2026.2:** O compilador aceita tanto a sintaxe direta de palavra-chave (`pure`, `impure`)
> quanto a notação com arroba (`@pure`, `@impure`), inspirada nas anotações da linguagem SPar.
> As anotações de alocação do `fork` existem só com arroba: `@nucleo` e `@computador`
> (as palavras `nucleo` e `computador` sem `@` continuam livres para nomes de variáveis).

### 2.2 Literais

```bnf
<NUMBER>         ::= <digito> { <digito> } [ "." <digito> { <digito> } ]
<STRING_LITERAL> ::= '"' { <caractere> } '"'
<BOOL_LITERAL>   ::= "true" | "false"
<IDENTIFIER>     ::= ( <letra> | "_" ) { <letra> | <digito> | "_" }
```

### 2.3 Operadores

| Categoria | Tokens |
|-----------|--------|
| Aritméticos | `+`  `-`  `*`  `/`  `%` |
| Relacionais | `==`  `!=`  `<`  `>`  `<=`  `>=` |
| Lógicos | `&&`  `\|\|`  `!` |
| Atribuição | `=` |

### 2.4 Delimitadores

```
(  )  {  }  [  ]  .  ;  ,
```

### 2.5 Tipos declaráveis

```bnf
<tipo> ::= "number" | "int" | "string" | "bool" | "void" | "list" | "dict"
```

---

## 3. Programa

O programa MiniPar é uma sequência de zero ou mais declarações e comandos no nível global.

```bnf
<programa> ::= { <declaracao_global> | <comando> }

<declaracao_global> ::= <declaracao_classe>
                      | <declaracao_funcao>
                      | <declaracao_variavel>
```

---

## 4. Declarações

### 4.1 Declaração de Variável

```bnf
<declaracao_variavel> ::= "var" <IDENTIFIER> [ "=" <expressao> ] ";"
                        | <tipo> <IDENTIFIER> [ "=" <expressao> ] ";"
```

**Exemplos:**

```minipar
var x = 42;
var nome = "MiniPar";
number total = 0;
bool ativo = true;
```

### 4.2 Declaração de Função

```bnf
<declaracao_funcao> ::= "func" <IDENTIFIER> "(" [ <lista_parametros> ] ")" <bloco_seq>

<lista_parametros> ::= <parametro> { "," <parametro> }

<parametro> ::= [ <tipo> ] <IDENTIFIER>
```

**Exemplos:**

```minipar
func somar(a, b) {
    return a + b;
}

func calcular(number x, number y) {
    return x * y;
}
```

### 4.3 Declaração de Classe

```bnf
<declaracao_classe> ::= "class" <IDENTIFIER> [ "extends" <IDENTIFIER> ] "{"
                            { <membro_classe> }
                        "}"

<membro_classe> ::= "var" <declaracao_variavel>
                  | "func" <declaracao_funcao>
```

**Exemplos:**

```minipar
class Animal {
    var nome = "Animal";
    func falar() {
        print("...");
    }
}

class Cachorro extends Animal {
    func falar() {
        print("Au!");
    }
}
```

---

## 5. Comandos

```bnf
<comando> ::= <declaracao_variavel>
            | <atribuicao>
            | <bloco_seq>
            | <bloco_par>
            | <bloco_pure>
            | <bloco_impure>
            | <bloco_fork>
            | <comando_join>
            | <comando_if>
            | <comando_while>
            | <comando_do_while>
            | <comando_for>
            | <comando_print>
            | <comando_send>
            | <comando_return>
            | <comando_break>
            | <comando_continue>
            | <chamada_funcao> ";"
            | <chamada_metodo> ";"
```

### 5.1 Atribuição

A atribuição suporta identificadores simples, propriedades de objetos e indexação de coleções:

```bnf
<atribuicao> ::= <alvo_atribuicao> "=" <expressao> ";"

<alvo_atribuicao> ::= <IDENTIFIER>
                    | <expressao_posfixo> "." <IDENTIFIER>
                    | <expressao_posfixo> "[" <expressao> "]"
```

**Exemplos:**

```minipar
x = 10;
objeto.campo = 42;
lista[0] = "primeiro";
```

### 5.2 Comando Print

```bnf
<comando_print> ::= "print" "(" [ <expressao> { "," <expressao> } ] ")" ";"
```

**Exemplos:**

```minipar
print("Olá, mundo!");
print("Valor:", x, "e", y);
```

### 5.3 Comando Return

```bnf
<comando_return> ::= "return" [ <expressao> ] ";"
```

### 5.4 Comandos Break e Continue

```bnf
<comando_break>    ::= "break" ";"
<comando_continue> ::= "continue" ";"
```

> `break` e `continue` são válidos somente dentro de laços (`while`, `do-while`, `for`).  
> O analisador semântico reporta erro se forem usados fora de laço.

---

## 6. Blocos e Primitivas de Concorrência e Paralelismo

O MiniPar 2026.2 suporta dois modelos de paralelismo:
1. **Paralelismo de Dados Anotado (Modelo SPar):** com as primitivas `pure` (para fatiamento de laços/cálculos independentes) e `impure` (para isolamento e proteção automática de regiões críticas com `std::mutex`).
2. **Paralelismo de Tarefas e Concorrência:** com blocos `par`, disparo assíncrono de subtarefas em segundo plano com `fork` e barreira de sincronização com `join`.

### 6.1 Bloco Sequencial (SEQ)

Executa os comandos internos em ordem, da mesma forma que um bloco tradicional.

```bnf
<bloco_seq> ::= "seq" "{" { <comando> } "}"
              | "{" { <comando> } "}"
```

O `seq` é opcional: blocos com chaves `{ }` são tratados como sequenciais por padrão.

### 6.2 Bloco Paralelo (PAR)

Cada comando interno é executado como uma `std::thread` independente em C++.  
As threads são sincronizadas por `join()` ao final do bloco.

```bnf
<bloco_par> ::= "par" "{" { <comando> } "}"
```

**Exemplo:**

```minipar
par {
    seq { print("Thread A"); }
    seq { print("Thread B"); }
    seq { print("Thread C"); }
}
```

### 6.3 Bloco e Laço Puro (PURE — Modelo SPar)

Inspirado no artigo *High-Level Stream and Data Parallelism in C++ for Multi-Cores* (SBLP'21), a anotação `pure` (ou `@pure`) marca que o laço ou bloco subsequente é **funcionalmente puro** (não possui efeitos colaterais em memória compartilhada externa, ou escreve em posições mutuamente exclusivas de arrays/matrizes).

O compilador transcreve o laço anotado como um padrão **Map / Parallel For**: as iterações são divididas entre as threads (uma por núcleo lógico da CPU, ou o valor de `MINIPAR_PURE_THREADS`), com escalonamento dinâmico de blocos, e há uma barreira implícita no fim do laço.

```bnf
<bloco_pure> ::= "pure" <comando>
               | "@pure" <comando>
```

**Quando o laço é paralelizado:**

| Forma do comando anotado | Geração de código |
|---|---|
| `for (var i = a; i < b; i = i + passo)` (também `<=`, e `>`/`>=` com `i = i - passo`; `passo` literal positivo) | Paralelo (Map) |
| `for (var x in colecao)` | Paralelo (Map) sobre os elementos |
| Laço com `break` (do próprio laço) ou `return` no corpo | Sequencial (não dá para dividir entre threads) |
| Outras formas de `for`, ou `pure { ... }` (bloco) | Sequencial (região marcada como pura) |

> **Regra semântica de pureza (MiniPar 2026.2):** dentro de `pure`, atribuir a uma variável declarada **fora** do laço só é permitido dentro de `impure`.
> *Erro reportado: `Atribuicao a variavel externa 'x' dentro de 'pure' sem regiao 'impure' (condicao de corrida).`*
> Escritas em posições distintas de listas/matrizes (`matriz[y][x] = v`) são permitidas, pois cada iteração escreve na sua própria posição.

**Exemplo:**

```minipar
pure for (var y = 0; y < altura; y = y + 1) {
    for (var x = 0; x < largura; x = x + 1) {
        var iter = calcular_mandelbrot(x, y);
        matriz[y][x] = iter;
    }
}
```

### 6.4 Região Crítica com Mutex Lock (IMPURE — Modelo SPar)

A anotação `impure` (ou `@impure`) delimita uma região com efeitos colaterais (ex: atualização de variável acumuladora compartilhada, operações de I/O na tela) que reside **dentro** de um contexto `pure`.

**Regra Semântica Fundamental:**  
> O analisador semântico reporta erro se `impure` for declarado fora de uma região `pure`.  
> *Erro reportado: `A anotação 'impure' só é permitida dentro de um bloco ou laço 'pure'.`*

Na geração de código C++20, o compilador "purifica" a região protegendo-a automaticamente com um lock seguro:
`std::lock_guard<std::mutex> __impure_guard(__minipar_impure_mtx);`, garantindo exclusão mútua entre as threads do laço `pure` (sem condições de corrida na região impura).

```bnf
<bloco_impure> ::= "impure" "{" { <comando> } "}"
                 | "@impure" "{" { <comando> } "}"
```

**Exemplo:**

```minipar
var total_geral = 0;

pure for (var i = 0; i < 1000; i = i + 1) {
    var item = calcular_dado(i);
    impure {
        total_geral = total_geral + item;
    }
}
```

### 6.5 Disparo Assíncrono de Subtarefas (FORK)

Dispara a execução de um bloco de código como uma subtarefa assíncrona, sem bloquear a tarefa principal. O nome da tarefa é opcional e serve para identificação didática.

Conforme o enunciado, **a alocação de uma subtarefa pode ser para um Núcleo da CPU ou para um Computador diferente**. Isso é expresso na gramática pela produção `<alocacao>`:

```bnf
<bloco_fork> ::= "fork" [ <IDENTIFIER> ] [ <alocacao> ] <comando>

<alocacao>   ::= "@nucleo" "(" <expressao> ")"                          (* núcleo da CPU *)
               | "@computador" "(" <expressao> "," <expressao> ")"      (* ip, porta *)
               | "@computador" "(" <expressao> ")"                      (* um c_channel *)
               | "(" <expressao> ")"                                    (* forma legada = @nucleo *)
```

| Alocação | Onde a subtarefa executa | Memória / comunicação | Código gerado |
|---|---|---|---|
| (nenhuma) | Thread no pool `__active_fork_threads` | Compartilhada com a tarefa principal | `__active_fork_threads.emplace_back([&]() { ... });` |
| `@nucleo(n)` | Thread **fixada no núcleo `n`** da CPU (afinidade; `n` é tomado módulo o nº de núcleos) | Compartilhada com a tarefa principal | `__minipar_fixar_nucleo(n);` no início da thread |
| `@computador(ip, porta)` | **Outro computador** (processo independente rodando o mesmo executável) | **Sem memória compartilhada**: dados só por mensagens `c_channel` | `__minipar_executar_remoto(...)` no computador principal e `__minipar_servir_tarefas(...)` no computador trabalhador |

**Como funciona o `@computador` (mesmo programa em vários computadores):**
- O computador principal executa o programa normalmente. Ao chegar no `fork ... @computador(ip, porta)`, envia o pedido da subtarefa para `ip:porta` e a thread do fork espera ela terminar; o `join` espera essas threads.
- Um **computador trabalhador** é o mesmo executável iniciado com a variável de ambiente `MINIPAR_TRABALHADOR=<porta>` (ex.: `MINIPAR_TRABALHADOR=6201 ./output/programa.exe`). Ele só executa as subtarefas que recebe pela rede e encerra quando o programa principal termina.
- Se o `ip` for local (`127.0.0.1`/`localhost`) e ninguém responder, o próprio programa inicia o processo trabalhador nesse computador — assim os testes podem ser feitos em localhost, como permite o enunciado, e depois em computadores diferentes trocando apenas o IP.
- **Regra semântica:** a subtarefa `@computador` não pode usar variáveis declaradas fora do seu bloco (nem `this`), porque executa em outro processo. Funções e classes podem ser usadas.
  *Erro: `A subtarefa 't' (fork @computador) nao pode usar a variavel externa 'x': ela executa em outro computador; envie os dados por c_channel.`*

> Como o nome da tarefa é opcional, o parser usa um *lookahead* para distinguir `fork f();` (chamada de função sem nome de tarefa) de `fork t1(4) { ... }` (nome + alocação legada): se depois do `)` vier `;` ou `.`, é uma chamada.

**Exemplo — a mesma tarefa principal dividida em 2 subtarefas, alocadas em núcleos ou em computadores** (programa completo em `tests/teste_fork_nucleos_computadores.minipar`):

```minipar
# Em 2 núcleos diferentes da CPU (memória compartilhada)
fork subtarefa_soma @nucleo(0) {
    resultado_soma = soma_ate(n_soma);
    print("[subtarefa_soma] executada no nucleo", nucleo_atual());
}
fork subtarefa_fatorial @nucleo(1) {
    resultado_fat = fatorial(n_fat);
}
join;

# Em 2 computadores diferentes (dados vão e voltam por c_channel)
fork subtarefa_soma_remota @computador("127.0.0.1", 6201) {
    var entrada = c_channel("127.0.0.1", 6211);
    var saida = c_channel("127.0.0.1", 6213);
    send(saida, soma_ate(to_number(receive(entrada))));
}
send(envio_soma, n_soma);
var soma_remota = receive(retorno_soma);
join;
```

**Exemplo (Teste 8 — fork sem alocação explícita):**

```minipar
fork nucleo_1 {
    avaliar_atividades(0, 40);
    print("Nucleo 1 concluiu!");
}

fork nucleo_2 {
    avaliar_atividades(40, 80);
    print("Nucleo 2 concluiu!");
}
```

### 6.6 Barreira de Sincronização (JOIN)

Atua como uma barreira de sincronização: bloqueia a thread chamadora até que todas as tarefas assíncronas disparadas previamente por blocos `fork` tenham finalizado completamente a sua execução.

Na geração de código, percorre as threads ativas chamando `.join()` em cada uma e liberando os recursos.

```bnf
<comando_join> ::= "join" [ <lista_identificadores> ] ";"

<lista_identificadores> ::= <IDENTIFIER> { "," <IDENTIFIER> }
```

**Exemplo:**

```minipar
fork tarefa_A { simular_trabalho(100); }
fork tarefa_B { simular_trabalho(100); }

join; # Bloqueia até que tarefa_A e tarefa_B terminem
print("Todas as tarefas filhas foram finalizadas!");
```

---

## 7. Estruturas de Controle

### 7.1 If / Else

```bnf
<comando_if> ::= "if" "(" <expressao> ")" <comando>
                 [ "else" <comando> ]
```

**Exemplos:**

```minipar
if (x > 0) {
    print("positivo");
}

if (x > 0) {
    print("positivo");
} else {
    print("negativo ou zero");
}

# Encadeamento if-else-if
if (x > 0) {
    print("positivo");
} else if (x < 0) {
    print("negativo");
} else {
    print("zero");
}
```

### 7.2 While

```bnf
<comando_while> ::= "while" "(" <expressao> ")" <comando>
```

**Exemplo:**

```minipar
while (i < 10) {
    i = i + 1;
}
```

### 7.3 Do-While

```bnf
<comando_do_while> ::= "do" <comando> "while" "(" <expressao> ")" [ ";" ]
```

**Exemplo:**

```minipar
do {
    tentativas = tentativas + 1;
} while (tentativas < 5);
```

### 7.4 For

O `for` suporta tanto o estilo clássico (inicializador; condição; incremento) quanto o estilo iterador (`for var x in colecao`):

```bnf
<comando_for> ::= "for" "(" <for_classico> | <for_iterador> ")" <comando>

<for_classico> ::= [ <inicializador_for> ] ";" [ <expressao> ] ";" [ <incremento_for> ]

<inicializador_for> ::= "var" <IDENTIFIER> [ "=" <expressao> ]
                      | <tipo> <IDENTIFIER> [ "=" <expressao> ]
                      | <alvo_atribuicao> "=" <expressao>
                      | <expressao>

<incremento_for>    ::= <alvo_atribuicao> "=" <expressao>
                      | <expressao>

<for_iterador>      ::= "var" <IDENTIFIER> "in" <expressao>
```

**Exemplos:**

```minipar
# For clássico
for (var i = 0; i < 10; i = i + 1) {
    print(i);
}

# For iterador
for (var item in lista) {
    print(item);
}

# For com range()
for (var i in range(5)) {
    print(i);
}
```

---

## 8. Orientação a Objetos

### 8.1 Instanciação com new

```bnf
<expressao_new> ::= "new" <IDENTIFIER> "(" [ <lista_argumentos> ] ")"
```

**Exemplo:**

```minipar
var obj = new MinhaClasse();
var rede = new RedeNeural(0.5);
```

### 8.2 Acesso a Propriedades

```bnf
<acesso_propriedade> ::= <expressao_posfixo> "." <IDENTIFIER>
```

**Exemplo:**

```minipar
print(neuronio.peso);
```

### 8.3 Chamada de Método

```bnf
<chamada_metodo> ::= <expressao_posfixo> "." <IDENTIFIER> "(" [ <lista_argumentos> ] ")"
```

**Exemplo:**

```minipar
neuronio.treinar();
algoritmo.ordenar();
rede.feedforward(x1, x2);
```

### 8.4 Atribuição de Propriedade

```bnf
<atrib_propriedade> ::= <expressao_posfixo> "." <IDENTIFIER> "=" <expressao> ";"
```

**Exemplo:**

```minipar
this.peso = this.peso + 0.01;
obj.nome = "novo";
```

### 8.5 Referência a this

Dentro de métodos de uma classe, `this` refere-se à instância corrente.

```bnf
<expressao_this> ::= "this"
```

### 8.6 Herança

```bnf
<declaracao_classe> ::= "class" <IDENTIFIER> "extends" <IDENTIFIER> "{"
                            { <membro_classe> }
                        "}"
```

**Exemplo:**

```minipar
class Cachorro extends Animal {
    func latir() {
        print("Au!");
    }
}
```

---

## 9. Funções

### 9.1 Chamada de Função

```bnf
<chamada_funcao> ::= <IDENTIFIER> "(" [ <lista_argumentos> ] ")"

<lista_argumentos> ::= <expressao> { "," <expressao> }
```

### 9.2 Recursão

Funções podem se chamar recursivamente sem nenhuma sintaxe especial:

```minipar
func fatorial(n) {
    if (n <= 1) {
        return 1;
    }
    return n * fatorial(n - 1);
}
```

---

## 10. Expressões

As expressões seguem a hierarquia de precedência implementada no parser (da menor para a maior precedência):

```bnf
<expressao> ::= <expressao_ou>

<expressao_ou>  ::= <expressao_e> { "||" <expressao_e> }

<expressao_e>   ::= <expressao_comp> { "&&" <expressao_comp> }

<expressao_comp> ::= <expressao_termo>
                     { ( "==" | "!=" | "<" | ">" | "<=" | ">=" ) <expressao_termo> }

<expressao_termo> ::= <expressao_fator> { ( "+" | "-" ) <expressao_fator> }

<expressao_fator> ::= <expressao_unaria> { ( "*" | "/" | "%" ) <expressao_unaria> }

<expressao_unaria> ::= ( "-" | "+" | "!" ) <expressao_unaria>
                     | <expressao_posfixo>

<expressao_posfixo> ::= <expressao_primaria>
                        { "." <IDENTIFIER> [ "(" [ <lista_argumentos> ] ")" ]
                        | "[" <expressao> "]"
                        }

<expressao_primaria> ::= <NUMBER>
                       | <STRING_LITERAL>
                       | <BOOL_LITERAL>
                       | <IDENTIFIER> [ "(" [ <lista_argumentos> ] ")" ]
                       | "this"
                       | <expressao_new>
                       | <expressao_c_channel>
                       | <expressao_receive>
                       | <expressao_input>
                       | <expressao_lista>
                       | <expressao_matrix>
                       | "(" <expressao> ")"
```

### Tabela de Precedência (maior nível = avaliado primeiro)

| Nível | Operadores | Associatividade |
|-------|-----------|-----------------|
| 7 (mais alta) | `()` `[]` `.` (posfixo) | esquerda |
| 6 | `!` `-` (unário) `+` (unário) | direita |
| 5 | `*` `/` `%` | esquerda |
| 4 | `+` `-` | esquerda |
| 3 | `==` `!=` `<` `>` `<=` `>=` | esquerda |
| 2 | `&&` | esquerda |
| 1 (mais baixa) | `\|\|` | esquerda |

---

## 11. Comunicação por Canais

A comunicação entre processos/computadores é feita via canais TCP implementados pela classe `MiniParChannel` no C++ gerado.

### 11.1 Criação de Canal

```bnf
<expressao_c_channel> ::= "c_channel" "(" <expressao> "," <expressao> ")"
```

O primeiro argumento é o endereço IP (string) e o segundo é a porta (número).

**Exemplo:**

```minipar
var canal = c_channel("127.0.0.1", 5000);
var canal_remoto = c_channel("192.168.1.10", 8080);
```

### 11.2 Envio de Mensagem (Send)

```bnf
<comando_send> ::= "send" "(" <expressao> "," <expressao> ")" ";"
```

O primeiro argumento é o canal e o segundo é a mensagem a enviar.

**Exemplo:**

```minipar
send(canal, "Hello Server");
send(canal, resultado);
```

### 11.3 Recebimento de Mensagem (Receive)

```bnf
<expressao_receive> ::= "receive" "(" <expressao> ")"
```

**Exemplo:**

```minipar
var mensagem = receive(canal);
var dado = receive(c_channel("127.0.0.1", 5000));
```

---

## 12. Coleções

### 12.1 Lista (Array)

```bnf
<expressao_lista> ::= "[" [ <expressao> { "," <expressao> } ] "]"
```

**Exemplos:**

```minipar
var vazio = [];
var numeros = [1, 2, 3, 4, 5];
var pesos = [0.5, 0.25, 1];
```

> Listas literais são numéricas (`std::vector<double>` no C++ gerado). Para guardar textos, use `matrix(linhas, colunas, "")`.

### 12.2 Indexação

```bnf
<expressao_indice> ::= <expressao_posfixo> "[" <expressao> "]"
```

**Exemplo:**

```minipar
var primeiro = lista[0];
var ultimo = lista[len(lista) - 1];
```

### 12.3 Atribuição por Índice

```bnf
<atrib_indice> ::= <expressao_posfixo> "[" <expressao> "]" "=" <expressao> ";"
```

**Exemplo:**

```minipar
lista[0] = 99;
matriz[i][j] = "#";
```

### 12.4 Matriz (Matrix)

Cria uma matriz bidimensional de `linhas × colunas` inicializada com um valor padrão.

```bnf
<expressao_matrix> ::= "matrix" "(" <expressao> "," <expressao> "," <expressao> ")"
```

**Exemplo:**

```minipar
var tela = matrix(9, 9, " ");       # matriz 9×9 de espaços
var zeros = matrix(3, 3, 0);        # matriz 3×3 de zeros
```

---

## 13. Entrada e Saída

### 13.1 Saída (Print)

```bnf
<comando_print> ::= "print" "(" [ <expressao> { "," <expressao> } ] ")" ";"
```

Múltiplos argumentos são impressos separados por espaço seguidos de `\n`.

### 13.2 Entrada (Input)

```bnf
<expressao_input> ::= "input" "(" [ <expressao> ] ")"
```

Lê uma linha da entrada padrão (stdin). O argumento opcional é exibido como prompt antes da leitura.

**Exemplos:**

```minipar
var nome = input("Seu nome: ");
var valor = input();
var numero = to_number(input("Digite um número: "));
```

---

## 14. Tipos e Literais

### 14.1 Número

```bnf
<literal_numero> ::= <digito> { <digito> } [ "." { <digito> } ]
```

Representa inteiros e ponto flutuante. No C++ gerado as variáveis são declaradas com `auto`: um literal sem ponto vira inteiro de **64 bits** (`long long`, ex.: `42LL`) e um literal com ponto vira `double`. Os inteiros de 64 bits aproximam o MiniPar do `int` do Python (o enunciado pede "Int — o mesmo do Python"): por exemplo, o gerador pseudoaleatório `(estado * 1103515245 + 12345) % 2147483648` dos Testes 8–10 não estoura. A divisão `/` entre dois inteiros é inteira (como `//` no Python), e o operador `%` só deve ser usado com valores inteiros.

**Exemplos:** `0`, `42`, `3.14`, `0.5`

### 14.2 String

```bnf
<literal_string> ::= '"' { <caractere_string> } '"'

<caractere_string> ::= <qualquer_caractere_exceto_aspas_e_barra>
                     | "\\" "n"    # newline
                     | "\\" "t"    # tab
                     | "\\" '"'    # aspas duplas
                     | "\\" "\\"   # barra invertida
```

### 14.3 Booleano

```bnf
<literal_bool> ::= "true" | "false"
```

### 14.4 Identificador

```bnf
<IDENTIFIER> ::= ( <letra> | "_" ) { <letra> | <digito> | "_" }

<letra>  ::= "A" | ... | "Z" | "a" | ... | "z"
<digito> ::= "0" | ... | "9"
```

---

## 15. Biblioteca Nativa

As seguintes funções são reconhecidas pelo analisador semântico e traduzidas diretamente pelo gerador de código C++:

| Função MiniPar | Assinatura | Descrição |
|---------------|------------|-----------|
| `print(...)` | `print(expr, ...)` | Imprime na saída padrão |
| `input([prompt])` | `input()` / `input(expr)` | Lê linha do stdin |
| `exp(x)` | `exp(number)` → `number` | Exponencial natural (eˣ) |
| `random()` | `random()` → `number` | Número aleatório entre 0 e 1 |
| `range(n)` / `range(a,b)` | `range(int)` → `list` | Gera sequência inteira |
| `len(col)` | `len(list\|string)` → `number` | Comprimento de coleção |
| `to_number(s)` | `to_number(string)` → `number` | Converte string para número (texto inválido: mostra `[ERRO] ... nao e um numero valido; usando 0.` e devolve 0, sem derrubar o programa) |
| `parse_ints(s)` | `parse_ints(string)` → `list` | Parseia inteiros de string separados por espaço |
| `obter_tempo()` | `obter_tempo()` → `number` | Instante atual em segundos (alta precisão), para medir tempos |
| `simular_trabalho(ms)` | `simular_trabalho(number)` | Ocupa a thread por `ms` milissegundos (espera ativa), para simular carga |
| `nucleo_atual()` | `nucleo_atual()` → `number` | Núcleo da CPU em que a thread atual está executando (-1 se indisponível) |
| `str(x)` | `str(any)` → `string` | Converte um valor em texto, como o `str()` do Python (ex.: `"Total: " + str(n)`) |

### Métodos de Lista (acesso via ponto)

| Método | Descrição |
|--------|-----------|
| `.append(v)` / `.push_back(v)` | Adiciona elemento ao final |
| `.pop()` | Remove e retorna o último elemento |
| `.size()` | Retorna o tamanho da lista |

---

## 16. Comentários

```bnf
<comentario> ::= "#" { <qualquer_caractere> } <fim_de_linha>
```

Comentários iniciam com `#` e vão até o final da linha. São descartados pelo lexer.

**Exemplos:**

```minipar
# Isso é um comentário de linha inteira
var x = 10; # Comentário ao final da linha
```

---

## 17. Gramática Consolidada (BNF Completa)

A seguir a gramática completa em formato BNF, em ordem de definição:

```bnf
(* ============================================================ *)
(*       GRAMÁTICA BNF — LINGUAGEM MINIPAR 2026.2               *)
(*       Equipe: Ludson Almeida, Davi Melo, Iury Nogueira       *)
(*       UFAL - Compiladores (Prof. Arturo Hernandez)           *)
(* ============================================================ *)


(* ─── ESTRUTURA GLOBAL ─── *)

<programa> ::= { <declaracao_global> | <comando> }

<declaracao_global> ::= <declaracao_classe>
                      | <declaracao_funcao>
                      | <declaracao_variavel>


(* ─── DECLARAÇÕES ─── *)

<declaracao_variavel> ::= "var" <IDENTIFIER> [ "=" <expressao> ] ";"
                        | <tipo> <IDENTIFIER> [ "=" <expressao> ] ";"

<declaracao_funcao>   ::= "func" <IDENTIFIER> "(" [ <lista_parametros> ] ")" <bloco_seq>

<lista_parametros>    ::= <parametro> { "," <parametro> }
<parametro>           ::= [ <tipo> ] <IDENTIFIER>

<declaracao_classe>   ::= "class" <IDENTIFIER> [ "extends" <IDENTIFIER> ]
                          "{" { <membro_classe> } "}"

<membro_classe>       ::= "var" <declaracao_variavel>
                        | "func" <declaracao_funcao>


(* ─── COMANDOS ─── *)

<comando> ::= <declaracao_variavel>
            | <atribuicao>
            | <bloco_seq>
            | <bloco_par>
            | <bloco_pure>
            | <bloco_impure>
            | <bloco_fork>
            | <comando_join>
            | <comando_if>
            | <comando_while>
            | <comando_do_while>
            | <comando_for>
            | <comando_print>
            | <comando_send>
            | <comando_return>
            | <comando_break>
            | <comando_continue>
            | <chamada_funcao> ";"
            | <chamada_metodo> ";"

<atribuicao>        ::= <alvo_atribuicao> "=" <expressao> ";"
<alvo_atribuicao>   ::= <IDENTIFIER>
                      | <expressao_posfixo> "." <IDENTIFIER>
                      | <expressao_posfixo> "[" <expressao> "]"

<comando_print>     ::= "print" "(" [ <expressao> { "," <expressao> } ] ")" ";"
<comando_send>      ::= "send"  "(" <expressao> "," <expressao> ")" ";"
<comando_return>    ::= "return" [ <expressao> ] ";"
<comando_break>     ::= "break" ";"
<comando_continue>  ::= "continue" ";"
<comando_join>      ::= "join" [ <lista_identificadores> ] ";"

<lista_identificadores> ::= <IDENTIFIER> { "," <IDENTIFIER> }


(* ─── BLOCOS E PARALELISMO ─── *)

<bloco_seq>    ::= "seq" "{" { <comando> } "}"
                 | "{" { <comando> } "}"

<bloco_par>    ::= "par" "{" { <comando> } "}"

<bloco_pure>   ::= ( "pure" | "@pure" ) <comando>

<bloco_impure> ::= ( "impure" | "@impure" ) "{" { <comando> } "}"

<bloco_fork>   ::= "fork" [ <IDENTIFIER> ] [ <alocacao> ] <comando>

<alocacao>     ::= "@nucleo" "(" <expressao> ")"
                 | "@computador" "(" <expressao> [ "," <expressao> ] ")"
                 | "(" <expressao> ")"


(* ─── ESTRUTURAS DE CONTROLE ─── *)

<comando_if>       ::= "if" "(" <expressao> ")" <comando> [ "else" <comando> ]

<comando_while>    ::= "while" "(" <expressao> ")" <comando>

<comando_do_while> ::= "do" <comando> "while" "(" <expressao> ")" [ ";" ]

<comando_for>      ::= "for" "(" <for_cabecalho> ")" <comando>

<for_cabecalho>    ::= <for_classico>
                     | <for_iterador>

<for_classico>     ::= [ <inicializador_for> ] ";" [ <expressao> ] ";" [ <incremento_for> ]

<inicializador_for> ::= "var"  <IDENTIFIER> [ "=" <expressao> ]
                      | <tipo> <IDENTIFIER> [ "=" <expressao> ]
                      | <alvo_atribuicao> "=" <expressao>
                      | <expressao>

<incremento_for>   ::= <alvo_atribuicao> "=" <expressao>
                     | <expressao>

<for_iterador>     ::= "var" <IDENTIFIER> "in" <expressao>


(* ─── ORIENTAÇÃO A OBJETOS ─── *)

<expressao_new>         ::= "new" <IDENTIFIER> "(" [ <lista_argumentos> ] ")"
<acesso_propriedade>    ::= <expressao_posfixo> "." <IDENTIFIER>
<chamada_metodo>        ::= <expressao_posfixo> "." <IDENTIFIER> "(" [ <lista_argumentos> ] ")"
<atrib_propriedade>     ::= <expressao_posfixo> "." <IDENTIFIER> "=" <expressao> ";"
<expressao_this>        ::= "this"


(* ─── COMUNICAÇÃO POR CANAIS ─── *)

<expressao_c_channel>   ::= "c_channel" "(" <expressao> "," <expressao> ")"
<expressao_receive>     ::= "receive" "(" <expressao> ")"
(* send já listado em <comando_send> *)


(* ─── COLEÇÕES ─── *)

<expressao_lista>   ::= "[" [ <expressao> { "," <expressao> } ] "]"
<expressao_indice>  ::= <expressao_posfixo> "[" <expressao> "]"
<atrib_indice>      ::= <expressao_posfixo> "[" <expressao> "]" "=" <expressao> ";"
<expressao_matrix>  ::= "matrix" "(" <expressao> "," <expressao> "," <expressao> ")"


(* ─── ENTRADA E SAÍDA ─── *)

<expressao_input>   ::= "input" "(" [ <expressao> ] ")"
(* print já listado em <comando_print> *)


(* ─── EXPRESSÕES (hierarquia de precedência) ─── *)

<expressao>          ::= <expressao_ou>

<expressao_ou>       ::= <expressao_e> { "||" <expressao_e> }

<expressao_e>        ::= <expressao_comp> { "&&" <expressao_comp> }

<expressao_comp>     ::= <expressao_termo>
                         { ( "==" | "!=" | "<" | ">" | "<=" | ">=" )
                           <expressao_termo> }

<expressao_termo>    ::= <expressao_fator> { ( "+" | "-" ) <expressao_fator> }

<expressao_fator>    ::= <expressao_unaria> { ( "*" | "/" | "%" ) <expressao_unaria> }

<expressao_unaria>   ::= ( "-" | "+" | "!" ) <expressao_unaria>
                       | <expressao_posfixo>

<expressao_posfixo>  ::= <expressao_primaria>
                         { "." <IDENTIFIER> [ "(" [ <lista_argumentos> ] ")" ]
                         | "[" <expressao> "]"
                         }

<expressao_primaria> ::= <NUMBER>
                       | <STRING_LITERAL>
                       | <BOOL_LITERAL>
                       | <IDENTIFIER> [ "(" [ <lista_argumentos> ] ")" ]
                       | "this"
                       | <expressao_new>
                       | <expressao_c_channel>
                       | <expressao_receive>
                       | <expressao_input>
                       | <expressao_lista>
                       | <expressao_matrix>
                       | "(" <expressao> ")"

<lista_argumentos>   ::= <expressao> { "," <expressao> }
<chamada_funcao>     ::= <IDENTIFIER> "(" [ <lista_argumentos> ] ")"


(* ─── TIPOS E LITERAIS ─── *)

<tipo>           ::= "number" | "int" | "string" | "bool" | "void" | "list" | "dict"

<NUMBER>         ::= <digito> { <digito> } [ "." { <digito> } ]
<STRING_LITERAL> ::= '"' { <caractere_string> } '"'
<BOOL_LITERAL>   ::= "true" | "false"
<IDENTIFIER>     ::= ( <letra> | "_" ) { <letra> | <digito> | "_" }

<caractere_string> ::= <qualquer_char_exceto_aspas_e_barra>
                     | "\n" | "\t" | '\"' | "\\"

<letra>  ::= "A" | ... | "Z" | "a" | ... | "z"
<digito> ::= "0" | ... | "9"


(* ─── COMENTÁRIOS ─── *)

<comentario> ::= "#" { <qualquer_char> } <nova_linha>
(* Descartados pelo lexer — não aparecem na AST *)
```

---

## Notas de Implementação

### Inferência de Tipos

O analisador semântico (`src/semantic.py`) usa inferência simples de tipos com as seguintes regras:

| Expressão | Tipo inferido |
|-----------|--------------|
| Literal numérico | `number` |
| Literal string | `string` |
| Literal booleano | `bool` |
| Lista literal `[...]` | `list` |
| `matrix(...)` | `matrix` |
| `c_channel(...)` | `c_channel` |
| `receive(...)` | `string` |
| `input(...)` | `string` |
| `new Classe(...)` | `Classe` |
| `this` | nome da classe atual |
| `op` relacional / lógico | `bool` |
| `"a" + "b"` (concatenação) | `string` |
| Operação aritmética | `number` |
| Identificador | tipo declarado na tabela de símbolos |
| Desconhecido | `unknown` (compatível com qualquer tipo) |

### Regras Semânticas Verificadas

| Regra | Erro reportado |
|-------|---------------|
| Redeclaração no mesmo escopo | `Variável 'x' já declarada.` |
| Uso antes de declaração | `Variável 'x' não declarada.` |
| Incompatibilidade de tipos | `Tipo incompatível em atribuição de 'x'.` |
| Função não declarada | `Função 'f' não declarada.` |
| Aridade errada (função) | `Função 'f' espera N argumento(s), recebeu M.` |
| Classe não declarada | `Classe 'C' não declarada.` |
| Superclasse não declarada | `Superclasse 'S' não declarada.` |
| Método inexistente | `Método 'm' não declarado em 'C'.` |
| Atributo inexistente | `Atributo 'a' não declarado em 'C'.` |
| `break`/`continue` fora de laço | `'break' usado fora de laço de repetição.` |
| **SPar:** `impure` fora de `pure` | `A anotação 'impure' só é permitida dentro de um bloco ou laço 'pure'.` |
| **SPar:** escrita em variável externa dentro de `pure` sem `impure` | `Atribuição a variável externa 'x' dentro de 'pure' sem região 'impure' (condição de corrida).` |
| **Fork:** subtarefa `@computador` usando variável externa ou `this` | `A subtarefa 't' (fork @computador) não pode usar a variável externa 'x': ela executa em outro computador; envie os dados por c_channel.` |

> As mensagens aparecem no console sem acentos (ex.: `Variavel 'x' ja declarada.`).

### Geração de Código Intermediário (TAC - 3 Endereços)

| Construto MiniPar | Diretivas / Instruções TAC geradas |
|-------------------|-----------------------------------|
| `pure for (...)` | `BEGIN_PURE_MAP` ... `END_PURE_MAP` |
| `impure { ... }` | `ACQUIRE_LOCK` ... `RELEASE_LOCK` |
| `fork task { ... }` | `FORK_TASK task:` ... `ENDFORK task` |
| `fork task @nucleo(n) { ... }` | `FORK_TASK task @nucleo(n):` ... `ENDFORK task` |
| `fork task @computador(ip, p) { ... }` | `FORK_TASK task @computador(ip, p):` ... `ENDFORK task` |
| `join;` | `JOIN_TASKS` |

### Geração de Código C++20

| Construto MiniPar | Código C++ gerado |
|-------------------|------------------|
| `class C { ... }` | `class C { public: ... };` |
| `new C(args)` | `std::make_shared<C>(args)` |
| `obj.metodo(args)` | `obj->metodo(args)` |
| `obj.campo` | `obj->campo` |
| `par { a; b; }` | `std::vector<std::thread>` + `emplace_back` + `join` |
| `pure for (...)` | `__minipar_pure_map(n, [&](inicio, fim) { for (...) corpo })` — iterações divididas entre `std::thread` (padrão Map) |
| `impure { ... }` | `std::lock_guard<std::mutex> __impure_guard(__minipar_impure_mtx);` |
| `fork task { ... }` | `__active_fork_threads.emplace_back([&]() { ... });` |
| `fork task @nucleo(n) { ... }` | Thread no pool que chama `__minipar_fixar_nucleo(n)` (afinidade de CPU) antes do corpo |
| `fork task @computador(ip, p) { ... }` | Thread que chama `__minipar_executar_remoto(...)`; o corpo vai para o `main()` do computador trabalhador (`__minipar_servir_tarefas`) |
| `join;` | Percorre `__active_fork_threads` chamando `.join()` em cada thread |
| `print(a, b)` | `__minipar_print(a, b)` — monta a linha e escreve de uma vez (sem misturar saída entre threads) |
| `obter_tempo()` | `duration_cast<duration<double>>(high_resolution_clock::now()...)` (segundos) |
| `simular_trabalho(ms)` | Espera ativa (laço consultando `high_resolution_clock`) por `ms` milissegundos |
| `c_channel(ip, porta)` | `std::make_shared<MiniParChannel>(ip, porta)` |
| `send(canal, msg)` | `canal->sendData(__to_string(msg))` |
| `receive(canal)` | `canal->receiveData()` |
| `42` (literal inteiro) | `42LL` (inteiro de 64 bits) |
| `[1, 2, 3]` | `std::vector<double>{1LL, 2LL, 3LL}` |
| `str(x)` | `__to_string(x)` |
| `matrix(l, c, v)` | `__make_matrix(l, c, v)` |
| `exp(x)` | `std::exp(x)` |
| `random()` | `random_val()` |
| `to_number(s)` | `__minipar_to_number(s)` (texto inválido: mostra aviso e usa 0) |
| `len(x)` | `x.size()` |
| `range(n)` | `__minipar_range(n)` |
| `input(p)` | `input(p)` (helper C++) |

---

*Gramática atualizada em Novembro de 2026 — MiniPar v2026.2 (UFAL / Compiladores)*
