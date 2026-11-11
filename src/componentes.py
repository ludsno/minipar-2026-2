"""
Interfaces dos Componentes de Software do compilador MiniPar 2026.2.

O enunciado pede que os analisadores (Léxico, Sintático, Semântico), a Tabela de
Símbolos e os geradores (TAC e C++) sejam componentes de software. Cada interface
abaixo é a "interface fornecida" de um componente no diagrama UML
(docs/MODELAGEM_UML_COMPONENTES.md), e cada classe concreta a implementa — mesmo
padrão do exemplo IRelogio / RelogioAbstrato / Relogio do Anexo 2:

    Interface (fornecida)  Componente (implementação)        Arquivo
    ---------------------  --------------------------------  ----------------
    ILexico                C_Lexer      -> Lexer             src/lexer.py
    ISintatico             C_Parser     -> Parser            src/parser.py
    ISemantico             C_Semantic   -> SemanticAnalyzer  src/semantic.py
    ITabelaSimbolos        C_TabelaSimb -> TabelaSimbolos    src/semantic.py
    ITAC                   C_TAC        -> TACGenerator      src/tac.py
    ICodeGen               C_CodeGen    -> CppCodeGenerator  src/codegen.py

As interfaces requeridas são as que cada componente consome: o Parser requer a
lista de tokens do ILexico; o Semântico, o TAC e o CodeGen requerem a AST
(Program) produzida pelo ISintatico; o Semântico requer a ITabelaSimbolos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ILexico(ABC):
    """Analisador Léxico: converte o código-fonte em uma lista de tokens."""

    @abstractmethod
    def tokenize(self) -> List[Any]:
        """Retorna a lista de tokens (tipo, lexema, linha, coluna), terminando em END_OF_FILE."""


class ISintatico(ABC):
    """Analisador Sintático: converte a lista de tokens na Árvore Sintática Abstrata (AST)."""

    @abstractmethod
    def parse(self) -> Any:
        """Retorna o nó raiz Program. Lança ParseError em caso de erro sintático."""


class ITabelaSimbolos(ABC):
    """Tabela de Símbolos: escopos aninhados e histórico de todos os símbolos declarados."""

    @abstractmethod
    def entrar_escopo(self) -> None: ...

    @abstractmethod
    def sair_escopo(self) -> None: ...

    @abstractmethod
    def declarar(self, nome: str, tipo: str, escopo: str, linha: int, params: Optional[List[str]] = None) -> bool:
        """Declara o símbolo no escopo atual. Retorna False se já existir nesse escopo."""

    @abstractmethod
    def buscar(self, nome: str) -> Optional[Any]:
        """Procura o símbolo do escopo mais interno para o mais externo."""

    @abstractmethod
    def get_symbol_table(self) -> List[Dict[str, Any]]:
        """Histórico de todos os símbolos declarados (nome, tipo, escopo, linha, params)."""


class ISemantico(ABC):
    """Analisador Semântico: valida a AST (escopos, tipos, regras SPar e fork/join)."""

    @abstractmethod
    def analyze(self, program: Any) -> bool:
        """Retorna True se o programa é semanticamente válido."""

    @abstractmethod
    def get_errors(self) -> List[str]:
        """Mensagens de erro semântico encontradas."""

    @abstractmethod
    def get_symbol_table(self) -> List[Dict[str, Any]]:
        """Tabela de Símbolos montada durante a análise."""


class ITAC(ABC):
    """Gerador de Código Intermediário de Três Endereços (TAC)."""

    @abstractmethod
    def generate_text(self, program: Any) -> str:
        """Retorna o TAC como texto."""

    @abstractmethod
    def generate(self, program: Any, output_name: str) -> str:
        """Grava output/<nome>.tac e retorna o caminho."""


class ICodeGen(ABC):
    """Gerador de Código C++20 (e compilação com g++)."""

    @abstractmethod
    def generate_cpp_code(self, program: Any) -> str:
        """Retorna o código C++ completo (runtime + programa traduzido)."""

    @abstractmethod
    def generate(self, program: Any, output_name: str) -> bool:
        """Grava output/<nome>.cpp, compila com g++ -O3 e retorna True se gerou o .exe."""
