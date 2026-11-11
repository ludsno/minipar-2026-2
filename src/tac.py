"""
Componente Gerador de Código Intermediário de Três Endereços (C_TAC).

Percorre a AST e emite instruções TAC com no máximo um operador por linha
(ex.: t0 = a + b), usando temporários (t0, t1, ...) e rótulos (WHILE_0, ENDIF_1, ...)
com desvios "goto", "if x goto L" e "ifFalse x goto L".

Diretivas do MiniPar 2026.2:
  BEGIN_PURE_MAP / END_PURE_MAP         laço 'pure' (padrão Map)
  ACQUIRE_LOCK / RELEASE_LOCK           região 'impure' (mutex)
  FORK_TASK t [@nucleo(n) | @computador(ip, porta)]: ... ENDFORK t
  JOIN_TASKS t1, t2 | ALL               barreira 'join'
"""
from __future__ import annotations
import os
from typing import Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr,
    PureBlock, ImpureBlock, ForkBlock, JoinStmt,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)
from componentes import ITAC




class TACGenerator(ITAC):
    """Implementação da interface ITAC."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.temp_count = 0
        self.label_count = 0
        self.break_stack: list[str] = []
        self.continue_stack: list[str] = []

    def _temp(self) -> str:
        name = f"t{self.temp_count}"
        self.temp_count += 1
        return name

    def _label(self, prefix: str) -> str:
        name = f"{prefix}_{self.label_count}"
        self.label_count += 1
        return name

    def _emit(self, line: str = "") -> None:
        self.lines.append(line)

    def _expr(self, node: Optional[ASTNode]) -> str:
        """Gera o TAC de uma expressão e retorna o endereço (variável, constante ou temporário) do resultado."""
        if node is None: return "0"
        if isinstance(node, NumberExpr): return node.value
        if isinstance(node, StringExpr): return f'"{node.value}"'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, UnaryExpr):
            value = self._expr(node.operand)
            tmp = self._temp()
            self._emit(f"{tmp} = {node.op}{value}")
            return tmp
        if isinstance(node, BinaryExpr):
            left = self._expr(node.left)
            right = self._expr(node.right)
            tmp = self._temp()
            self._emit(f"{tmp} = {left} {node.op} {right}")
            return tmp
        if isinstance(node, ListLiteral):
            tmp = self._temp()
            values = ", ".join(self._expr(e) for e in node.elements)
            self._emit(f"{tmp} = [{values}]")
            return tmp
        if isinstance(node, MatrixCreateExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = matrix({self._expr(node.rows)}, {self._expr(node.cols)}, {self._expr(node.init_value)})")
            return tmp
        if isinstance(node, IndexExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}[{self._expr(node.index)}]")
            return tmp
        if isinstance(node, PropertyAccess):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}.{node.property_name}")
            return tmp
        if isinstance(node, (FuncCallExpr, MethodCall)):
            args = node.arguments
            name = node.name if isinstance(node, FuncCallExpr) else f"{self._expr(node.object)}.{node.method_name}"
            for arg in args:
                self._emit(f"param {self._expr(arg)}")
            tmp = self._temp()
            self._emit(f"{tmp} = call {name}, {len(args)}")
            return tmp
        if isinstance(node, NewExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = new {node.class_name}")
            return tmp
        if isinstance(node, CChannelExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = c_channel({self._expr(node.ip)}, {self._expr(node.port)})")
            return tmp
        if isinstance(node, ReceiveExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = receive {self._expr(node.channel)}")
            return tmp
        if isinstance(node, InputExpr):
            tmp = self._temp()
            if node.prompt:
                self._emit(f"{tmp} = input({self._expr(node.prompt)})")
            else:
                self._emit(f"{tmp} = input()")
            return tmp
        return "?"

    def _stmt(self, node: Optional[ASTNode]) -> None:
        """Gera o TAC de um comando (laços e if viram rótulos + desvios condicionais)."""
        if node is None: return
        if isinstance(node, VarDecl):
            self._emit(f"{node.name} = {self._expr(node.init_value)}")
        elif isinstance(node, Assignment):
            self._emit(f"{node.name} = {self._expr(node.value)}")
        elif isinstance(node, PropertyAssign):
            self._emit(f"{self._expr(node.object)}.{node.property_name} = {self._expr(node.value)}")
        elif isinstance(node, IndexAssign):
            self._emit(f"{self._expr(node.target.object)}[{self._expr(node.target.index)}] = {self._expr(node.value)}")
        elif isinstance(node, PrintStmt):
            for arg in node.arguments:
                self._emit(f"print {self._expr(arg)}")
        elif isinstance(node, SendStmt):
            self._emit(f"send {self._expr(node.channel)}, {self._expr(node.message)}")
        elif isinstance(node, (SeqBlock, ParBlock)):
            for stmt in node.statements: self._stmt(stmt)
        elif isinstance(node, PureBlock):
            self._emit("BEGIN_PURE_MAP")
            self._stmt(node.body)
            self._emit("END_PURE_MAP")
        elif isinstance(node, ImpureBlock):
            self._emit("ACQUIRE_LOCK")
            for stmt in node.statements:
                self._stmt(stmt)
            self._emit("RELEASE_LOCK")
        elif isinstance(node, ForkBlock):
            task_id = node.task_name or "anonymous_task"
            alloc = ""
            if node.alloc_kind:
                # Argumentos da alocação são avaliados antes de disparar a subtarefa
                args = ", ".join(self._expr(a) for a in node.alloc_args)
                alloc = f" @{node.alloc_kind}({args})"
            self._emit(f"FORK_TASK {task_id}{alloc}:")
            self._stmt(node.body)
            self._emit(f"ENDFORK {task_id}")
        elif isinstance(node, JoinStmt):
            targets = ", ".join(node.target_tasks) if node.target_tasks else "ALL"
            self._emit(f"JOIN_TASKS {targets}")
        elif isinstance(node, IfStmt):
            end = self._label("ENDIF")
            else_label = self._label("ELSE") if node.else_branch else end
            self._emit(f"ifFalse {self._expr(node.condition)} goto {else_label}")
            self._stmt(node.then_branch)
            if node.else_branch:
                self._emit(f"goto {end}")
                self._emit(f"{else_label}:")
                self._stmt(node.else_branch)
            self._emit(f"{end}:")
        elif isinstance(node, WhileStmt):
            start, end = self._label("WHILE"), self._label("ENDWHILE")
            self.break_stack.append(end); self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, DoWhileStmt):
            start, end = self._label("DO"), self._label("ENDDO")
            self.break_stack.append(end); self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._stmt(node.body)
            self._emit(f"if {self._expr(node.condition)} goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, ForStmt):
            if node.iterator_name:
                # for (var x in colecao): percorre a coleção com um índice temporário
                colecao = self._expr(node.iterable)
                idx, tam, cond = self._temp(), self._temp(), self._temp()
                start, step, end = self._label("FORIN"), self._label("FORIN_STEP"), self._label("ENDFORIN")
                self._emit(f"{idx} = 0")
                self._emit(f"{tam} = len {colecao}")
                self.break_stack.append(end); self.continue_stack.append(step)
                self._emit(f"{start}:")
                self._emit(f"{cond} = {idx} < {tam}")
                self._emit(f"ifFalse {cond} goto {end}")
                self._emit(f"{node.iterator_name} = {colecao}[{idx}]")
                self._stmt(node.body)
                self._emit(f"{step}:")
                self._emit(f"{idx} = {idx} + 1")
                self._emit(f"goto {start}")
                self._emit(f"{end}:")
                self.break_stack.pop(); self.continue_stack.pop()
                return
            start, step, end = self._label("FOR"), self._label("FOR_STEP"), self._label("ENDFOR")
            self._stmt(node.initializer)
            self.break_stack.append(end); self.continue_stack.append(step)
            self._emit(f"{start}:")
            if node.condition:
                self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"{step}:")
            self._stmt(node.increment)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, BreakStmt):
            self._emit(f"goto {self.break_stack[-1] if self.break_stack else 'END'}")
        elif isinstance(node, ContinueStmt):
            self._emit(f"goto {self.continue_stack[-1] if self.continue_stack else 'CONTINUE'}")
        elif isinstance(node, ReturnStmt):
            self._emit(f"return {self._expr(node.value)}" if node.value else "return")
        elif isinstance(node, (FuncCallExpr, MethodCall)):
            self._expr(node)
        elif isinstance(node, ClassDecl):
            self._emit(f"# class {node.name}")
            for method in node.methods: self._stmt(method)
        elif isinstance(node, FuncDecl):
            self._emit(f"func {node.name}:")
            self._stmt(node.body)
            self._emit(f"endfunc {node.name}")

    def generate_text(self, program: Program) -> str:
        for stmt in program.statements:
            self._stmt(stmt)
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def generate(self, program: Program, output_name: str) -> str:
        os.makedirs("output", exist_ok=True)
        tac_path = os.path.join("output", f"{output_name}.tac")
        text = self.generate_text(program)
        with open(tac_path, "w", encoding="utf-8") as f:
            f.write(text)
        return tac_path
