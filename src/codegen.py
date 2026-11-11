"""
Componente Gerador de Código C++ (C_CodeGen) do compilador MiniPar 2026.2.

Traduz a AST para C++20 (source-to-source), insere o runtime de
src/cpp_template.py e compila com: g++ -std=c++20 -O3 -pthread.

Principais traduções:
  var x = e;            -> auto x = e;
  class / new / obj.m() -> class C { public: ... }; std::make_shared<C>(...); obj->m(...)
  par { a; b; }         -> uma std::thread por comando + join
  pure for (...)        -> __minipar_pure_map: iterações divididas entre threads (padrão Map)
  impure { ... }        -> std::lock_guard<std::mutex> no mutex global
  fork t { ... }        -> std::thread no pool __active_fork_threads
  fork t @nucleo(n)     -> thread fixada (afinidade) no núcleo n
  fork t @computador(.) -> subtarefa enviada a outro computador (processo trabalhador)
  join;                 -> join() de todas as threads do pool
  c_channel/send/receive-> MiniParChannel (sockets TCP)
"""
from __future__ import annotations
import os
import subprocess
import sys
from typing import Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr, 
    PureBlock, ImpureBlock, ForkBlock, JoinStmt,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)
from cpp_template import _CPP_HEADER
from componentes import ICodeGen

class CppCodeGenerator(ICodeGen):
    """Implementação da interface ICodeGen."""

    def __init__(self) -> None:
        self._pure_counter = 0  # sufixo único para variáveis auxiliares de cada laço pure
        self._fork_counter = 0  # sufixo único para forks alocados em núcleo
        self._remote_tasks: list = []   # [(id_da_tarefa, ForkBlock)] dos forks @computador
        self._remote_ids: dict = {}     # id(ForkBlock) -> id_da_tarefa

    def _collect_remote_forks(self, node: Optional[ASTNode]) -> None:
        """Percorre a AST e numera os forks @computador (id usado no protocolo de rede)."""
        if node is None: return
        if isinstance(node, ForkBlock) and node.alloc_kind == "computador":
            task_id = f"{node.task_name or 'anonima'}#{len(self._remote_tasks)}"
            self._remote_ids[id(node)] = task_id
            self._remote_tasks.append((task_id, node))
        for value in vars(node).values():
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, ASTNode): self._collect_remote_forks(item)

    @staticmethod
    def _escape_string(value: str) -> str:
        res = []
        for ch in value:
            if ch == "\n": res.append("\\n")
            elif ch == "\t": res.append("\\t")
            elif ch == '"': res.append('\\"')
            elif ch == "\\": res.append("\\\\")
            else: res.append(ch)
        return "".join(res)

    def _translate_expression(self, node: Optional[ASTNode]) -> str:
        """Traduz uma expressão MiniPar para uma expressão C++ (entre parênteses quando binária)."""
        if node is None: return "0"
        if isinstance(node, NumberExpr):
            # Inteiros do MiniPar são de 64 bits (long long), mais próximos do int do
            # Python que o int de 32 bits do C++: ex. o LCG 1103515245 * x não estoura.
            return node.value if "." in node.value else f"{node.value}LL"
        if isinstance(node, StringExpr): return f'std::string("{self._escape_string(node.value)}")'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, UnaryExpr): return f"({node.op}{self._translate_expression(node.operand)})"
        if isinstance(node, BinaryExpr):
            return f"({self._translate_expression(node.left)} {node.op} {self._translate_expression(node.right)})"
        
        if isinstance(node, NewExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            return f"std::make_shared<{node.class_name}>({args})"
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, PropertyAccess):
            if node.property_name == "size": return f"{self._translate_expression(node.object)}.size()"
            return f"{self._translate_expression(node.object)}->{node.property_name}"
        
        if isinstance(node, MethodCall):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            m_name = node.method_name
            if m_name in ("append", "push_back"): return f"{self._translate_expression(node.object)}.push_back({args})"
            if m_name == "pop": return f"__array_pop({self._translate_expression(node.object)})"
            if m_name == "size": return f"{self._translate_expression(node.object)}.size()"
            return f"{self._translate_expression(node.object)}->{m_name}({args})"
        
        if isinstance(node, FuncCallExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            if node.name == "exp":
                return f"std::exp({args})"
            if node.name == "random":
                return "random_val()"
            if node.name == "len":
                return f"{self._translate_expression(node.arguments[0])}.size()"
            if node.name == "range":
                return f"__minipar_range({args})"
            if node.name == "to_number":
                return f"__minipar_to_number({args})"   # texto invalido -> aviso e 0 (nao derruba o programa)
            if node.name == "parse_ints":
                return f"__parse_ints({args})"
            if node.name == "str":
                return f"__to_string({args})"   # str(x): número/valor -> texto, como no Python
            return f"{node.name}({args})"

        if isinstance(node, CChannelExpr):
            ip = self._translate_expression(node.ip)
            port = self._translate_expression(node.port)
            return f"std::make_shared<MiniParChannel>({ip}, {port})"
        if isinstance(node, ReceiveExpr):
            return f"{self._translate_expression(node.channel)}->receiveData()"
        if isinstance(node, InputExpr):
            if node.prompt:
                return f"input({self._translate_expression(node.prompt)})"
            return "input()"

        if isinstance(node, ListLiteral):
            elems = ", ".join(self._translate_expression(e) for e in node.elements)
            return f"std::vector<double>{{{elems}}}"
        if isinstance(node, MatrixCreateExpr):
            r = self._translate_expression(node.rows)
            c = self._translate_expression(node.cols)
            v = self._translate_expression(node.init_value)
            return f"__make_matrix({r}, {c}, {v})"
        if isinstance(node, IndexExpr):
            obj = self._translate_expression(node.object)
            idx = self._translate_expression(node.index)
            return f"{obj}[{idx}]"

        return "0"

    def _has_value_return(self, node: Optional[ASTNode]) -> bool:
        if node is None: return False
        if isinstance(node, ReturnStmt): return node.value is not None
        if isinstance(node, (SeqBlock, ParBlock, ImpureBlock)):
            return any(self._has_value_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._has_value_return(node.then_branch) or self._has_value_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt, PureBlock, ForkBlock)):
            return self._has_value_return(node.body)
        return False

    def _uses_float_return(self, node: Optional[ASTNode]) -> bool:
        """Detecta aritmética de ponto flutuante no corpo da função."""
        if node is None:
            return False
        if isinstance(node, BinaryExpr):
            if node.op == "/":
                return True
            return self._uses_float_return(node.left) or self._uses_float_return(node.right)
        if isinstance(node, NumberExpr):
            return "." in node.value
        if isinstance(node, (SeqBlock, ParBlock, ImpureBlock)):
            return any(self._uses_float_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._uses_float_return(node.then_branch) or self._uses_float_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt, PureBlock, ForkBlock)):
            return self._uses_float_return(node.body)
        if isinstance(node, ReturnStmt):
            return self._uses_float_return(node.value)
        return False

    def _return_type(self, body: Optional[ASTNode]) -> str:
        """Tipo de retorno C++ da função: void (sem return com valor), double (aritmética real) ou auto."""
        if not self._has_value_return(body):
            return "void"
        # auto falha no g++ quando há return double e return 0 (int) na mesma função
        if self._uses_float_return(body):
            return "double"
        return "auto"

    def _translate_statement(self, node: Optional[ASTNode], indent: str = "") -> str:
        """Traduz um comando MiniPar para C++ com a indentação indicada."""
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            return f"{indent}auto {node.name} = {expr};\n"
        if isinstance(node, Assignment):
            return f"{indent}{node.name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, PropertyAssign):
            obj = self._translate_expression(node.object)
            return f"{indent}{obj}->{node.property_name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, IndexAssign):
            tgt = self._translate_expression(node.target)
            return f"{indent}{tgt} = {self._translate_expression(node.value)};\n"
        
        if isinstance(node, (MethodCall, FuncCallExpr)):
            return f"{indent}{self._translate_expression(node)};\n"
        if isinstance(node, ReturnStmt):
            val = self._translate_expression(node.value) if node.value else ""
            return f"{indent}return {val};\n"
        if isinstance(node, BreakStmt):
            return f"{indent}break;\n"
        if isinstance(node, ContinueStmt):
            return f"{indent}continue;\n"
        
        if isinstance(node, SendStmt):
            chan = self._translate_expression(node.channel)
            msg = self._translate_expression(node.message)
            return f"{indent}{chan}->sendData(__to_string({msg}));\n"

        if isinstance(node, PrintStmt):
            # __minipar_print escreve a linha inteira de uma vez (seguro entre threads)
            args = ", ".join(self._translate_expression(arg) for arg in node.arguments)
            return f"{indent}__minipar_print({args});\n"
        
        if isinstance(node, SeqBlock):
            lines = [f"{indent}{{\n"]
            for stmt in node.statements: lines.append(self._translate_statement(stmt, indent + "    "))
            lines.append(f"{indent}}}\n")
            return "".join(lines)
        if isinstance(node, ParBlock):
            lines = [f"{indent}{{\n", f"{indent}    std::vector<std::thread> __m_thr;\n"]
            for stmt in node.statements:
                lines.append(f"{indent}    __m_thr.emplace_back([&]() {{\n{self._translate_statement(stmt, indent + '        ')}{indent}    }});\n")
            lines.append(f"{indent}    for (auto& t : __m_thr) t.join();\n{indent}}}\n")
            return "".join(lines)
        if isinstance(node, PureBlock):
            if isinstance(node.body, ForStmt):
                parallel = self._translate_pure_for(node.body, indent)
                if parallel is not None:
                    return parallel
                # Laço não canônico (ou com break/return): mantém a semântica sequencial
                lines = [
                    f"{indent}{{\n",
                    f"{indent}    // SPar Pure: laco nao canonico (ou com break/return) -> executado sequencialmente\n",
                    self._translate_statement(node.body, indent + "    "),
                    f"{indent}}}\n",
                ]
                return "".join(lines)
            lines = [f"{indent}{{\n", f"{indent}    // SPar Pure Block (regiao sem efeitos colaterais externos)\n"]
            lines.append(self._translate_statement(node.body, indent + "    "))
            lines.append(f"{indent}}}\n")
            return "".join(lines)
        if isinstance(node, ImpureBlock):
            lines = [
                f"{indent}{{\n",
                f"{indent}    // SPar Impure Critical Section (Protected by Mutex)\n",
                f"{indent}    std::lock_guard<std::mutex> __impure_guard(__minipar_impure_mtx);\n"
            ]
            for stmt in node.statements:
                lines.append(self._translate_statement(stmt, indent + "    "))
            lines.append(f"{indent}}}\n")
            return "".join(lines)
        if isinstance(node, ForkBlock) and node.alloc_kind == "computador":
            # Subtarefa em outro computador: a thread do fork só envia o pedido e
            # espera o fim; o corpo é executado pelo computador trabalhador (ver main).
            name = node.task_name or "anonima"
            task_id = self._remote_ids[id(node)]
            if len(node.alloc_args) == 2:
                ip = self._translate_expression(node.alloc_args[0])
                porta = self._translate_expression(node.alloc_args[1])
                capture = f"__ip = __to_string({ip}), __porta = static_cast<int>({porta})"
                call = f'__minipar_executar_remoto("{task_id}", "{name}", __ip, __porta);'
            else:
                canal = self._translate_expression(node.alloc_args[0])
                capture = f"__canal = {canal}"
                call = f'__minipar_executar_remoto("{task_id}", "{name}", __canal->ip, __canal->port);'
            return "".join([
                f"{indent}// Fork Task /* {name} */ -> alocada em outro computador (processo independente; dados so por c_channel)\n",
                f"{indent}__active_fork_threads.emplace_back([{capture}]() {{\n",
                f"{indent}    {call}\n",
                f"{indent}}});\n",
            ])
        if isinstance(node, ForkBlock) and node.alloc_kind == "nucleo":
            # Subtarefa em um núcleo específico: thread fixada (afinidade) no núcleo n
            name = node.task_name or "anonima"
            var = f"__fork_nucleo{self._fork_counter}"
            self._fork_counter += 1
            return "".join([
                f"{indent}// Fork Task /* {name} */ -> alocada em um nucleo da CPU\n",
                f"{indent}{{\n",
                f"{indent}    const long long {var} = static_cast<long long>({self._translate_expression(node.alloc_args[0])});\n",
                f"{indent}    __active_fork_threads.emplace_back([&, {var}]() {{\n",
                f"{indent}        __minipar_fixar_nucleo({var});\n",
                self._translate_statement(node.body, indent + "        "),
                f"{indent}    }});\n",
                f"{indent}}}\n",
            ])
        if isinstance(node, ForkBlock):
            task_label = f"/* {node.task_name} */" if node.task_name else ""
            lines = [
                f"{indent}// Fork Task {task_label}\n",
                f"{indent}__active_fork_threads.emplace_back([&]() {{\n",
                self._translate_statement(node.body, indent + "    "),
                f"{indent}}});\n"
            ]
            return "".join(lines)
        if isinstance(node, JoinStmt):
            lines = [
                f"{indent}// Join Tasks\n",
                f"{indent}for (auto& __t : __active_fork_threads) {{\n",
                f"{indent}    if (__t.joinable()) __t.join();\n",
                f"{indent}}}\n",
                f"{indent}__active_fork_threads.clear();\n"
            ]
            return "".join(lines)
        if isinstance(node, WhileStmt):
            res = f"{indent}while ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, DoWhileStmt):
            res = f"{indent}do\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ").rstrip()
            res += f"\n{indent}while ({self._translate_expression(node.condition)});\n"
            return res
        if isinstance(node, ForStmt):
            if node.iterator_name and node.iterable:
                res = f"{indent}for (auto {node.iterator_name} : {self._translate_expression(node.iterable)})\n"
                res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
                return res
            init = self._translate_for_part(node.initializer)
            cond = self._translate_expression(node.condition) if node.condition else "true"
            inc = self._translate_for_part(node.increment)
            res = f"{indent}for ({init}; {cond}; {inc})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, IfStmt):
            res = f"{indent}if ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.then_branch, indent if isinstance(node.then_branch, (SeqBlock, ParBlock)) else indent + "    ")
            if node.else_branch:
                res = res.rstrip() + f"\n{indent}else\n"
                if isinstance(node.else_branch, IfStmt):
                    res = res.rstrip() + " " + self._translate_statement(node.else_branch, indent).lstrip()
                else:
                    res += self._translate_statement(node.else_branch, indent if isinstance(node.else_branch, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        return ""

    # ------------------------------------------------------------------
    # SPar Pure: laço 'pure for' traduzido para o padrão Map (parallel for)
    # ------------------------------------------------------------------
    def _pure_escapes(self, node: Optional[ASTNode], nested_loop: bool = False) -> bool:
        """True se o corpo tem 'return' ou um 'break' que sairia do próprio laço pure.

        Esses comandos não podem ser divididos entre threads, então o laço
        continua sequencial.
        """
        if node is None: return False
        if isinstance(node, ReturnStmt): return True
        if isinstance(node, BreakStmt): return not nested_loop
        if isinstance(node, (FuncDecl, ClassDecl)): return False
        inner = nested_loop or isinstance(node, (WhileStmt, DoWhileStmt, ForStmt))
        for value in vars(node).values():
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, ASTNode) and self._pure_escapes(item, inner):
                    return True
        return False

    def _pure_loop_shape(self, f: ForStmt):
        """Reconhece o laço canônico 'for (var v = ini; v OP lim; v = v +/- passo)'.

        Retorna (variavel, ini, lim, passo, crescente, inclusivo) ou None.
        """
        init, cond, inc = f.initializer, f.condition, f.increment
        if not (isinstance(init, VarDecl) and init.init_value is not None):
            return None
        var = init.name
        if not (isinstance(cond, BinaryExpr) and cond.op in ("<", "<=", ">", ">=")
                and isinstance(cond.left, IdentifierExpr) and cond.left.name == var):
            return None
        if not (isinstance(inc, Assignment) and inc.name == var and isinstance(inc.value, BinaryExpr)):
            return None
        op, left, right = inc.value.op, inc.value.left, inc.value.right
        is_var = lambda n: isinstance(n, IdentifierExpr) and n.name == var
        if op == "+" and is_var(left) and isinstance(right, NumberExpr): step = right.value
        elif op == "+" and is_var(right) and isinstance(left, NumberExpr): step = left.value
        elif op == "-" and is_var(left) and isinstance(right, NumberExpr): step = right.value
        else: return None
        if float(step) <= 0:
            return None
        ascending = op == "+"
        if ascending != (cond.op in ("<", "<=")):
            return None
        return var, init.init_value, cond.right, step, ascending, cond.op in ("<=", ">=")

    def _translate_pure_for(self, f: ForStmt, indent: str) -> Optional[str]:
        """Gera o laço 'pure' dividindo as iterações entre threads (__minipar_pure_map).

        Retorna None quando o laço não pode ser paralelizado com segurança.
        """
        if self._pure_escapes(f.body):
            return None
        uid = self._pure_counter
        self._pure_counter += 1
        i1, i2, i3 = indent + "    ", indent + "        ", indent + "            "
        a, b, it, n = f"__pure_a{uid}", f"__pure_b{uid}", f"__pure_it{uid}", f"__pure_n{uid}"

        if f.iterator_name and f.iterable is not None:
            col = f"__pure_col{uid}"
            header = [
                f"{i1}// SPar Pure (Map): elementos de '{f.iterator_name}' divididos entre os nucleos\n",
                f"{i1}const auto {col} = {self._translate_expression(f.iterable)};\n",
                f"{i1}const long long {n} = static_cast<long long>({col}.size());\n",
            ]
            var_line = f"{i3}auto {f.iterator_name} = {col}[{it}];\n"
        else:
            shape = self._pure_loop_shape(f)
            if shape is None:
                return None
            var, start, limit, step, ascending, inclusive = shape
            ini, lim = f"__pure_ini{uid}", f"__pure_lim{uid}"
            count_args = f"{ini}, {lim}" if ascending else f"{lim}, {ini}"
            sign = "+" if ascending else "-"
            header = [
                f"{i1}// SPar Pure (Map): iteracoes de '{var}' divididas entre os nucleos (parallel for)\n",
                f"{i1}const auto {ini} = {self._translate_expression(start)};\n",
                f"{i1}const auto {lim} = {self._translate_expression(limit)};\n",
                f"{i1}const long long {n} = __minipar_pure_count({count_args}, {step}, {'true' if inclusive else 'false'});\n",
            ]
            var_line = f"{i3}auto {var} = static_cast<decltype({ini})>({ini} {sign} {it} * {step});\n"

        body_indent = i3 if isinstance(f.body, (SeqBlock, ParBlock)) else i3 + "    "
        lines = [f"{indent}{{\n", *header,
                 f"{i1}__minipar_pure_map({n}, [&](long long {a}, long long {b}) {{\n",
                 f"{i2}for (long long {it} = {a}; {it} < {b}; ++{it}) {{\n",
                 var_line,
                 self._translate_statement(f.body, body_indent),
                 f"{i2}}}\n",
                 f"{i1}}});\n",
                 f"{indent}}}\n"]
        return "".join(lines)

    def _translate_for_part(self, node: Optional[ASTNode]) -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            return f"auto {node.name} = {expr}"
        if isinstance(node, Assignment):
            return f"{node.name} = {self._translate_expression(node.value)}"
        if isinstance(node, PropertyAssign):
            return f"{self._translate_expression(node.object)}->{node.property_name} = {self._translate_expression(node.value)}"
        if isinstance(node, IndexAssign):
            return f"{self._translate_expression(node.target)} = {self._translate_expression(node.value)}"
        return self._translate_expression(node)

    def generate_cpp_code(self, program: Program) -> str:
        """Monta o .cpp: runtime + classes + funções + main() (com o modo computador trabalhador, se houver fork @computador)."""
        cpp_code = _CPP_HEADER
        self._remote_tasks, self._remote_ids = [], {}
        self._collect_remote_forks(program)

        for node in program.statements:
            if isinstance(node, ClassDecl):
                cpp_code += f"class {node.name}" + (f" : public {node.superclass}" if node.superclass else "") + " {\npublic:\n"
                for attr in node.attributes:
                    if attr.init_value:
                        init = self._translate_expression(attr.init_value)
                        cpp_code += f"    decltype({init}) {attr.name} = {init};\n"
                    else:
                        cpp_code += f"    double {attr.name} = 0;\n"
                for method in node.methods:
                    params = ", ".join(f"auto {p}" for p in method.params)
                    ret = self._return_type(method.body)
                    cpp_code += f"    {ret} {method.name}({params}) {{\n"
                    if isinstance(method.body, SeqBlock):
                        for stmt in method.body.statements: cpp_code += self._translate_statement(stmt, "        ")
                    else: cpp_code += self._translate_statement(method.body, "        ")
                    cpp_code += "    }\n"
                cpp_code += "};\n\n"
            elif isinstance(node, FuncDecl):
                params = ", ".join(f"auto {p}" for p in node.params)
                ret = self._return_type(node.body)
                cpp_code += f"{ret} {node.name}({params}) {{\n"
                if isinstance(node.body, SeqBlock):
                    for stmt in node.body.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node.body, "    ")
                cpp_code += "}\n\n"

        cpp_code += "int main(int argc, char** argv) {\n    #ifdef _WIN32\n        WSADATA wsa;\n        WSAStartup(MAKEWORD(2,2), &wsa);\n    #endif\n"
        cpp_code += "    __minipar_iniciar(argc, argv);\n\n"
        if self._remote_tasks:
            # Modo "computador trabalhador" (MINIPAR_TRABALHADOR=<porta>): o mesmo
            # executável roda em outro computador e executa só as subtarefas
            # fork @computador que receber pela rede.
            cpp_code += "    if (__minipar_modo_trabalhador()) {\n"
            cpp_code += "        __minipar_servir_tarefas([](const std::string& __tarefa) -> bool {\n"
            for task_id, fork in self._remote_tasks:
                cpp_code += f'            if (__tarefa == "{task_id}") {{\n'
                cpp_code += self._translate_statement(fork.body, "                ")
                cpp_code += "                return true;\n            }\n"
            cpp_code += "            return false;\n        });\n        return 0;\n    }\n\n"
        for node in program.statements:
            if not isinstance(node, (ClassDecl, FuncDecl)):
                if isinstance(node, SeqBlock):
                    for stmt in node.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node, "    ")
        cpp_code += "\n    __minipar_finalizar();  // barreira final + encerra computadores trabalhadores\n    return 0;\n}\n"
        return cpp_code

    def generate(self, program: Program, output_name: str) -> bool:
        """Grava output/<nome>.cpp e compila com g++ (gera output/<nome>.exe)."""
        cpp_code = self.generate_cpp_code(program)
        os.makedirs("output", exist_ok=True)
        cpp_path = os.path.join("output", f"{output_name}.cpp")
        exe_path = os.path.join("output", f"{output_name}.exe")

        with open(cpp_path, "w", encoding="utf-8") as f: f.write(cpp_code)
        
        print("[CODEGEN] Compilando via g++ com -std=c++20 e -O3...")
        cmd = ["g++", "-std=c++20", "-O3", cpp_path, "-o", exe_path, "-pthread"]
        if sys.platform == "win32":
            cmd.append("-lws2_32")
            # .exe autossuficiente (sem depender das DLLs do MinGW/MSYS2), para poder
            # ser copiado/baixado e executado em outro computador Windows.
            result = subprocess.run(cmd + ["-static"])
            if result.returncode != 0:
                print("[CODEGEN] Link estatico indisponivel; compilando sem -static...")
                result = subprocess.run(cmd)
        else:
            result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"[SUCESSO] Executavel: {exe_path}")
            return True
        print("[ERRO] Falha na compilacao.", file=sys.stderr)
        return False
