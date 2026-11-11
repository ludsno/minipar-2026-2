"""
Componentes Analisador Semântico (C_Semantic) e Tabela de Símbolos
(C_TabelaSimbolos) do compilador MiniPar 2026.2.

A análise é feita em duas passadas sobre a AST:
  1. _collect_declarations: registra funções e classes globais (permite chamar
     uma função antes da sua declaração e usar recursão);
  2. validate_node: percorre cada nó verificando as regras semânticas e
     preenchendo a Tabela de Símbolos.

Tratamento de erros: cada erro é mostrado como "[ERRO SEMANTICO] Linha N: ..."
e guardado em `errors`; a análise continua para reportar todos os erros de uma vez.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, IdentifierExpr, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, SeqBlock, ParBlock,
    PureBlock, ImpureBlock, ForkBlock, JoinStmt,
    IfStmt, WhileStmt, DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)

from componentes import ISemantico, ITabelaSimbolos


@dataclass
class Symbol:
    """Entrada da Tabela de Símbolos."""
    name: str
    type: str                                             # number, string, bool, list, matrix, c_channel, FUNC, CLASS, <Classe>...
    params: List[str] = field(default_factory=list)       # parâmetros (funções/métodos)
    attributes: Dict[str, str] = field(default_factory=dict)
    methods: Dict[str, List[str]] = field(default_factory=dict)


class TabelaSimbolos(ITabelaSimbolos):
    """Componente Tabela de Símbolos (C_TabelaSimbolos).

    - `escopos`: pilha de dicionários nome -> Symbol. O índice 0 é o escopo
      global; cada bloco, função, classe ou laço empilha um novo escopo.
    - `historico`: todos os símbolos já declarados (inclusive de escopos que já
      foram fechados), exibido na aba "Tabela de Símbolos" da interface didática.
    """

    def __init__(self) -> None:
        self.escopos: List[Dict[str, Symbol]] = [{}]
        self.historico: List[Dict[str, Any]] = []

    def entrar_escopo(self) -> None:
        self.escopos.append({})

    def sair_escopo(self) -> None:
        if len(self.escopos) > 1:
            self.escopos.pop()

    def declarar(self, nome: str, tipo: str, escopo: str, linha: int, params: Optional[List[str]] = None) -> bool:
        if nome in self.escopos[-1]:
            return False  # redeclaração no mesmo escopo
        self.escopos[-1][nome] = Symbol(name=nome, type=tipo, params=params or [])
        self.historico.append({"name": nome, "type": tipo, "scope": escopo, "line": linha, "params": params or []})
        return True

    def buscar(self, nome: str) -> Optional[Symbol]:
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
        return None

    def profundidade(self, nome: str) -> Optional[int]:
        """Índice do escopo onde o nome foi declarado (0 = global), ou None."""
        for indice in range(len(self.escopos) - 1, -1, -1):
            if nome in self.escopos[indice]:
                return indice
        return None

    def get_symbol_table(self) -> List[Dict[str, Any]]:
        return list(self.historico)


class SemanticAnalyzer(ISemantico):
    """Componente Analisador Semântico (C_Semantic).

    Percorre a AST verificando: declaração e uso de variáveis, redeclaração,
    compatibilidade de tipos, funções/métodos/atributos existentes e aridade,
    break/continue fora de laço, e as regras de paralelismo do MiniPar 2026.2:
      - impure só dentro de pure (modelo SPar);
      - dentro de pure, escrita em variável externa só dentro de impure;
      - fork @computador não acessa variáveis externas (só mensagens via c_channel).
    """

    def __init__(self) -> None:
        self.tabela = TabelaSimbolos()
        self._scopes = self.tabela.escopos            # mesma lista (atalho interno)
        self._symbol_history = self.tabela.historico  # mesma lista (atalho interno)
        self._has_errors = False
        self.errors: List[str] = []
        self._current_function: Optional[str] = None
        self._current_class: Optional[str] = None
        self._classes: Dict[str, Symbol] = {}
        self._functions: Dict[str, Symbol] = {}
        self._loop_depth = 0
        self._inside_pure = False
        self._inside_impure = False
        # Índice do primeiro escopo criado dentro do 'pure' atual: símbolos em
        # escopos anteriores são externos (compartilhados entre as threads).
        self._pure_scope_base: Optional[int] = None
        # Subtarefa 'fork @computador' em análise: roda em outro processo/computador,
        # então só pode usar variáveis declaradas dentro do próprio bloco.
        self._remote_scope_base: Optional[int] = None
        self._remote_task: Optional[str] = None

    def _enter_scope(self) -> None: self.tabela.entrar_escopo()
    def _exit_scope(self) -> None: self.tabela.sair_escopo()

    def _get_context(self) -> str:
        return f" (Funcao: {self._current_function})" if self._current_function else ""

    def _current_scope_label(self) -> str:
        if self._current_class and self._current_function:
            return f"{self._current_class}.{self._current_function}"
        if self._current_class:
            return f"Class:{self._current_class}"
        if self._current_function:
            return f"Func:{self._current_function}"
        if self._inside_pure:
            return "PureBlock"
        if len(self._scopes) > 1:
            return "Local"
        return "Global"

    def _define_symbol(self, name: str, type_: str, line: int, params: Optional[List[str]] = None) -> None:
        if not self.tabela.declarar(name, type_, self._current_scope_label(), line, params):
            self._report(line, f"Variavel '{name}' ja declarada.")

    def _lookup(self, name: str) -> Optional[Symbol]:
        return self.tabela.buscar(name)

    def _lookup_depth(self, name: str) -> Optional[int]:
        return self.tabela.profundidade(name)

    def _check_pure_write(self, name: str, line: int) -> None:
        """Regra SPar: dentro de 'pure', escrever em variável externa exige 'impure'."""
        if self._pure_scope_base is None or self._inside_impure:
            return
        depth = self._lookup_depth(name)
        if depth is not None and depth < self._pure_scope_base:
            self._report(line, f"Atribuicao a variavel externa '{name}' dentro de 'pure' sem regiao 'impure' (condicao de corrida).")

    def _check_remote_access(self, name: str, line: int) -> None:
        """Regra do fork @computador: sem memória compartilhada com o computador principal."""
        if self._remote_scope_base is None:
            return
        depth = self._lookup_depth(name)
        sym = self._lookup(name)
        if depth is not None and depth < self._remote_scope_base and sym and sym.type not in ("FUNC", "CLASS"):
            self._report(line, f"A subtarefa '{self._remote_task}' (fork @computador) nao pode usar a variavel externa '{name}': "
                               f"ela executa em outro computador; envie os dados por c_channel.")

    def _report(self, line: int, message: str) -> None:
        msg = f"Linha {line}{self._get_context()}: {message}"
        print(f"[ERRO SEMANTICO] {msg}", file=sys.stderr)
        self.errors.append(msg)
        self._has_errors = True

    def _infer_type(self, node: Optional[ASTNode]) -> str:
        """Inferência simples de tipos ("unknown" é compatível com qualquer tipo)."""
        if node is None: return "unknown"
        if isinstance(node, NumberExpr): return "number"
        if isinstance(node, StringExpr): return "string"
        if isinstance(node, BoolExpr): return "bool"
        if isinstance(node, InputExpr): return "string"
        if isinstance(node, CChannelExpr): return "c_channel"
        if isinstance(node, ReceiveExpr): return "string"
        if isinstance(node, ListLiteral): return "list"
        if isinstance(node, MatrixCreateExpr): return "matrix"
        if isinstance(node, NewExpr): return node.class_name
        if isinstance(node, ThisExpr): return self._current_class or "unknown"
        if isinstance(node, IdentifierExpr):
            sym = self._lookup(node.name)
            return sym.type if sym else "unknown"
        if isinstance(node, UnaryExpr):
            return "bool" if node.op == "!" else self._infer_type(node.operand)
        if isinstance(node, BinaryExpr):
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"): return "bool"
            if node.op == "+" and (lt == "string" or rt == "string"): return "string"
            if node.op == "+" and (lt == "list" or rt == "list"): return "list"
            return "number"
        if isinstance(node, PropertyAccess):
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name in cls.attributes: return cls.attributes[node.property_name]
            return "unknown"
        if isinstance(node, MethodCall):
            return "unknown"
        if isinstance(node, FuncCallExpr):
            if node.name in ("random", "exp", "obter_tempo", "nucleo_atual"): return "number"
            if node.name in ("range", "parse_ints"): return "list"
            if node.name == "str": return "string"
            return "unknown"
        if isinstance(node, IndexExpr): return "unknown"
        return "unknown"

    def _types_compatible(self, declared: str, actual: str) -> bool:
        if declared in ("var", "unknown") or actual == "unknown": return True
        if declared == "int" and actual == "number": return True
        if declared == "number" and actual == "int": return True
        return declared == actual

    def _collect_declarations(self, program: Program) -> None:
        """1ª passada: funções e classes globais (com parâmetros, atributos e métodos)."""
        for stmt in program.statements:
            if isinstance(stmt, FuncDecl):
                self._functions[stmt.name] = Symbol(stmt.name, "FUNC", params=stmt.params)
            elif isinstance(stmt, ClassDecl):
                attrs = {a.name: a.type for a in stmt.attributes}
                methods = {m.name: m.params for m in stmt.methods}
                self._classes[stmt.name] = Symbol(stmt.name, "CLASS", attributes=attrs, methods=methods)

    def validate_node(self, node: ASTNode) -> None:
        """2ª passada: valida o nó conforme o seu tipo e desce recursivamente nos filhos."""
        if node is None: return

        if isinstance(node, VarDecl):
            self.validate_node(node.init_value)
            actual_type = self._infer_type(node.init_value)
            declared_type = actual_type if node.type == "var" and actual_type != "unknown" else node.type
            if not self._types_compatible(declared_type, actual_type):
                self._report(node.line, f"Tipo incompativel em '{node.name}': esperado {declared_type}, recebido {actual_type}.")
            self._define_symbol(node.name, declared_type, node.line)
        elif isinstance(node, Assignment):
            sym = self._lookup(node.name)
            if sym is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
            else:
                self._check_pure_write(node.name, node.line)
                self._check_remote_access(node.name, node.line)
            self.validate_node(node.value)
            if sym and not self._types_compatible(sym.type, self._infer_type(node.value)):
                self._report(node.line, f"Tipo incompativel em atribuicao de '{node.name}'.")
        elif isinstance(node, PrintStmt):
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, SendStmt):
            self.validate_node(node.channel)
            self.validate_node(node.message)
        elif isinstance(node, CChannelExpr):
            self.validate_node(node.ip)
            self.validate_node(node.port)
        elif isinstance(node, ReceiveExpr):
            self.validate_node(node.channel)
        elif isinstance(node, ListLiteral):
            for e in node.elements: self.validate_node(e)
        elif isinstance(node, MatrixCreateExpr):
            self.validate_node(node.rows)
            self.validate_node(node.cols)
            self.validate_node(node.init_value)
        elif isinstance(node, IndexExpr):
            self.validate_node(node.object)
            self.validate_node(node.index)
        elif isinstance(node, IndexAssign):
            self.validate_node(node.target)
            self.validate_node(node.value)
        elif isinstance(node, IdentifierExpr):
            if self._lookup(node.name) is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
            else:
                self._check_remote_access(node.name, node.line)
        elif isinstance(node, BinaryExpr):
            self.validate_node(node.left)
            self.validate_node(node.right)
            if node.op in ("+", "-", "*", "/", "%"):
                lt, rt = self._infer_type(node.left), self._infer_type(node.right)
                if node.op != "+" and (lt not in ("number", "int", "var", "unknown") or rt not in ("number", "int", "var", "unknown")):
                    self._report(node.line, f"Operador '{node.op}' exige operandos numericos.")
        elif isinstance(node, UnaryExpr):
            self.validate_node(node.operand)
        elif isinstance(node, (SeqBlock, ParBlock)):
            self._enter_scope()
            for stmt in node.statements: self.validate_node(stmt)
            self._exit_scope()
        elif isinstance(node, IfStmt):
            self.validate_node(node.condition)
            self.validate_node(node.then_branch)
            if node.else_branch: self.validate_node(node.else_branch)
        elif isinstance(node, WhileStmt):
            self.validate_node(node.condition)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
        elif isinstance(node, DoWhileStmt):
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self.validate_node(node.condition)
        elif isinstance(node, ForStmt):
            self._enter_scope()
            if node.iterator_name:
                self.validate_node(node.iterable)
                self._define_symbol(node.iterator_name, "var", node.line)
            else:
                self.validate_node(node.initializer)
                self.validate_node(node.condition)
                self.validate_node(node.increment)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self._exit_scope()
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                self._report(node.line, f"'{node.__class__.__name__.replace('Stmt', '').lower()}' usado fora de laco.")
        elif isinstance(node, ClassDecl):
            if node.superclass and node.superclass not in self._classes:
                self._report(node.line, f"Superclasse '{node.superclass}' nao declarada.")
            self._define_symbol(node.name, "CLASS", node.line)
            self._enter_scope()
            old_class = self._current_class
            self._current_class = node.name
            for attr in node.attributes: self.validate_node(attr)
            for method in node.methods: self.validate_node(method)
            self._current_class = old_class
            self._exit_scope()
        elif isinstance(node, FuncDecl):
            self._define_symbol(node.name, "FUNC", node.line, node.params)
            self._enter_scope()
            old_function = self._current_function
            old_pure_base = self._pure_scope_base
            self._current_function = node.name
            self._pure_scope_base = None  # o corpo da função tem seu próprio contexto
            for p in node.params: self._define_symbol(p, "var", node.line)
            self.validate_node(node.body)
            self._current_function = old_function
            self._pure_scope_base = old_pure_base
            self._exit_scope()
        elif isinstance(node, ReturnStmt):
            if node.value: self.validate_node(node.value)
        elif isinstance(node, MethodCall):
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.method_name not in cls.methods:
                self._report(node.line, f"Metodo '{node.method_name}' nao declarado em '{obj_type}'.")
            elif cls and len(cls.methods[node.method_name]) != len(node.arguments):
                self._report(node.line, f"Metodo '{node.method_name}' espera {len(cls.methods[node.method_name])} argumento(s), recebeu {len(node.arguments)}.")
            self.validate_node(node.object)
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, FuncCallExpr):
            if node.name not in self._functions and node.name not in ("exp", "random", "range", "len", "to_number", "parse_ints", "obter_tempo", "simular_trabalho", "nucleo_atual", "str"):
                self._report(node.line, f"Funcao '{node.name}' nao declarada.")
            elif node.name in self._functions and len(self._functions[node.name].params) != len(node.arguments):
                self._report(node.line, f"Funcao '{node.name}' espera {len(self._functions[node.name].params)} argumento(s), recebeu {len(node.arguments)}.")
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, PropertyAccess):
            self.validate_node(node.object)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name not in cls.attributes:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
        elif isinstance(node, PropertyAssign):
            self.validate_node(node.object)
            self.validate_node(node.value)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name not in cls.attributes:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
        elif isinstance(node, NewExpr):
            if node.class_name not in self._classes:
                self._report(node.line, f"Classe '{node.class_name}' nao declarada.")
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, ThisExpr):
            if self._remote_scope_base is not None:
                self._report(node.line, f"A subtarefa '{self._remote_task}' (fork @computador) nao pode usar 'this': ela executa em outro computador.")
        elif isinstance(node, InputExpr):
            if node.prompt: self.validate_node(node.prompt)
        elif isinstance(node, PureBlock):
            old_pure, old_base = self._inside_pure, self._pure_scope_base
            self._inside_pure = True
            self._pure_scope_base = len(self._scopes)
            self.validate_node(node.body)
            self._inside_pure, self._pure_scope_base = old_pure, old_base
        elif isinstance(node, ImpureBlock):
            if not self._inside_pure:
                self._report(node.line, "A anotacao 'impure' so e permitida dentro de um bloco ou laco 'pure'.")
            old_impure = self._inside_impure
            self._inside_impure = True
            for stmt in node.statements:
                self.validate_node(stmt)
            self._inside_impure = old_impure
        elif isinstance(node, ForkBlock):
            # Argumentos da alocação são avaliados no computador principal
            for arg in node.alloc_args: self.validate_node(arg)
            if node.alloc_kind == "computador" and len(node.alloc_args) == 1:
                tipo = self._infer_type(node.alloc_args[0])
                if tipo not in ("c_channel", "unknown"):
                    self._report(node.line, "'@computador' com 1 argumento espera um c_channel (ou use @computador(ip, porta)).")
            if node.alloc_kind == "computador":
                old_base, old_task = self._remote_scope_base, self._remote_task
                self._remote_scope_base = len(self._scopes)
                self._remote_task = node.task_name or "anonima"
                self.validate_node(node.body)
                self._remote_scope_base, self._remote_task = old_base, old_task
            else:
                self.validate_node(node.body)
        elif isinstance(node, JoinStmt):
            pass

    def get_symbol_table(self) -> List[Dict[str, Any]]:
        return self.tabela.get_symbol_table()

    def get_errors(self) -> List[str]:
        return list(self.errors)

    def analyze(self, program: Program) -> bool:
        """Ponto de entrada (ISemantico): retorna True se não houve erro semântico."""
        self._collect_declarations(program)
        for stmt in program.statements: self.validate_node(stmt)
        return not self._has_errors
