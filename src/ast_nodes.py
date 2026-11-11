"""
Nós da Árvore Sintática Abstrata (AST) do MiniPar 2026.2.

Cada construção da linguagem é uma dataclass (ex.: IfStmt, ForStmt, PureBlock,
ForkBlock). O Analisador Sintático cria a árvore; o Semântico, o Gerador de TAC e
o Gerador de C++ a percorrem. `ast_to_dict` converte a árvore em JSON
hierárquico para o desenho gráfico (D3.js) da interface didática.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

class ASTNode:
    """Classe base de todos os nós; `line` é a linha do código-fonte (usada nas mensagens de erro)."""
    line: int = 1

@dataclass
class NumberExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class StringExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class BoolExpr(ASTNode):
    value: bool
    line: int = 1

@dataclass
class IdentifierExpr(ASTNode):
    name: str
    line: int = 1

@dataclass
class BinaryExpr(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode
    line: int = 1

@dataclass
class UnaryExpr(ASTNode):
    op: str
    operand: ASTNode
    line: int = 1

@dataclass
class VarDecl(ASTNode):
    name: str
    init_value: Optional[ASTNode] = None
    type: str = "var"
    line: int = 1

@dataclass
class Assignment(ASTNode):
    name: str
    value: ASTNode = None
    line: int = 1

@dataclass
class PrintStmt(ASTNode):
    arguments: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class SeqBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class ParBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class PureBlock(ASTNode):
    body: ASTNode
    line: int = 1

@dataclass
class ImpureBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class ForkBlock(ASTNode):
    """Subtarefa assíncrona: fork [nome] [@nucleo(n) | @computador(ip, porta)] comando.

    alloc_kind: None (thread comum), "nucleo" (thread fixada em um núcleo da CPU)
    ou "computador" (subtarefa executada por outro computador/processo).
    alloc_args: argumentos da alocação ([n] ou [ip, porta] ou [canal]).
    """
    body: ASTNode
    task_name: Optional[str] = None
    alloc_kind: Optional[str] = None
    alloc_args: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class JoinStmt(ASTNode):
    target_tasks: List[str] = field(default_factory=list)
    line: int = 1

@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None
    line: int = 1

@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode
    line: int = 1

@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode
    condition: ASTNode
    line: int = 1

@dataclass
class ForStmt(ASTNode):
    initializer: Optional[ASTNode]
    condition: Optional[ASTNode]
    increment: Optional[ASTNode]
    body: ASTNode
    iterator_name: Optional[str] = None
    iterable: Optional[ASTNode] = None
    line: int = 1

@dataclass
class BreakStmt(ASTNode):
    line: int = 1

@dataclass
class ContinueStmt(ASTNode):
    line: int = 1

@dataclass
class ClassDecl(ASTNode):
    name: str
    superclass: Optional[str]
    attributes: List[VarDecl]
    methods: List[FuncDecl]
    line: int = 1

@dataclass
class FuncDecl(ASTNode):
    name: str
    params: List[str]
    body: ASTNode
    line: int = 1

@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode]
    line: int = 1

@dataclass
class MethodCall(ASTNode):
    object: ASTNode
    method_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class FuncCallExpr(ASTNode):
    name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class PropertyAccess(ASTNode):
    object: ASTNode
    property_name: str
    line: int = 1

@dataclass
class PropertyAssign(ASTNode):
    object: ASTNode
    property_name: str
    value: ASTNode
    line: int = 1

@dataclass
class NewExpr(ASTNode):
    class_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class ThisExpr(ASTNode):
    line: int = 1

@dataclass
class CChannelExpr(ASTNode):
    ip: ASTNode
    port: ASTNode
    line: int = 1

@dataclass
class SendStmt(ASTNode):
    channel: ASTNode
    message: ASTNode
    line: int = 1

@dataclass
class ReceiveExpr(ASTNode):
    channel: ASTNode
    line: int = 1

@dataclass
class InputExpr(ASTNode):
    prompt: Optional[ASTNode] = None
    line: int = 1

@dataclass
class ListLiteral(ASTNode):
    elements: List[ASTNode]
    line: int = 1

@dataclass
class MatrixCreateExpr(ASTNode):
    rows: ASTNode
    cols: ASTNode
    init_value: ASTNode
    line: int = 1

@dataclass
class IndexExpr(ASTNode):
    object: ASTNode
    index: ASTNode
    line: int = 1

@dataclass
class IndexAssign(ASTNode):
    target: ASTNode
    value: ASTNode
    line: int = 1

@dataclass
class Program(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1


def ast_to_dict(node: Optional[ASTNode]) -> Optional[dict]:
    """Converte recursivamente a AST para um dicionário JSON hierárquico (padrão D3.js)."""
    if node is None:
        return None

    node_type = node.__class__.__name__
    details = ""
    if hasattr(node, "name") and isinstance(getattr(node, "name"), str):
        details = getattr(node, "name")
    elif hasattr(node, "task_name") and (getattr(node, "task_name") or getattr(node, "alloc_kind", None)):
        details = str(getattr(node, "task_name") or "")
        if getattr(node, "alloc_kind", None):
            details = f"{details} @{node.alloc_kind}".strip()
    elif hasattr(node, "op") and isinstance(getattr(node, "op"), str):
        details = getattr(node, "op")
    elif hasattr(node, "value") and not isinstance(getattr(node, "value"), ASTNode) and getattr(node, "value") is not None:
        details = str(getattr(node, "value"))
    elif hasattr(node, "method_name"):
        details = str(getattr(node, "method_name"))
    elif hasattr(node, "property_name"):
        details = str(getattr(node, "property_name"))
    elif hasattr(node, "class_name"):
        details = str(getattr(node, "class_name"))

    children = []
    for attr_name, attr_val in node.__dict__.items():
        if attr_name == "line":
            continue
        if isinstance(attr_val, ASTNode):
            child_dict = ast_to_dict(attr_val)
            if child_dict:
                children.append(child_dict)
        elif isinstance(attr_val, list):
            for item in attr_val:
                if isinstance(item, ASTNode):
                    child_dict = ast_to_dict(item)
                    if child_dict:
                        children.append(child_dict)

    category_map = {
        "PureBlock": "pure",
        "ImpureBlock": "impure",
        "ForkBlock": "fork",
        "JoinStmt": "join",
        "ParBlock": "parallel",
        "SeqBlock": "seq",
        "ClassDecl": "class",
        "FuncDecl": "func",
        "VarDecl": "var",
        "Assignment": "assign",
        "PropertyAssign": "assign",
        "IndexAssign": "assign",
        "IfStmt": "control",
        "WhileStmt": "control",
        "DoWhileStmt": "control",
        "ForStmt": "control",
        "BreakStmt": "control",
        "ContinueStmt": "control",
        "ReturnStmt": "control",
        "PrintStmt": "io",
        "InputExpr": "io",
        "BinaryExpr": "expr",
        "UnaryExpr": "expr",
        "NumberExpr": "literal",
        "StringExpr": "literal",
        "BoolExpr": "literal",
        "IdentifierExpr": "identifier",
        "MethodCall": "call",
        "FuncCallExpr": "call",
        "NewExpr": "class",
        "CChannelExpr": "channel",
        "SendStmt": "channel",
        "ReceiveExpr": "channel",
        "Program": "program",
    }

    return {
        "name": f"{node_type} ({details})" if details else node_type,
        "type": node_type,
        "category": category_map.get(node_type, "other"),
        "details": details,
        "line": getattr(node, "line", 1),
        "children": children,
    }
