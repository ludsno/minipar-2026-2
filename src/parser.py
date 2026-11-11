"""
Componente Analisador Sintático (C_Parser) do compilador MiniPar 2026.2.

Parser descendente recursivo (um método por não-terminal da gramática BNF em
BNF-grammar.md). Consome a lista de tokens do Analisador Léxico e constrói a
Árvore Sintática Abstrata (AST, nós em ast_nodes.py). A precedência dos
operadores é garantida pela cadeia de métodos
_parse_or -> _parse_and -> _parse_comparison -> _parse_term -> _parse_factor
-> _parse_unary -> _parse_primary (do menor para o maior nível).

Tratamento de erros: ao encontrar um token inesperado, o parser mostra
"[ERRO SINTATICO] Linha N: ..." e lança ParseError.
"""
from __future__ import annotations
import sys
from typing import List
from lexer import Token, TokenType
from componentes import ISintatico
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock,
    PureBlock, ImpureBlock, ForkBlock, JoinStmt,
    BinaryExpr, UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)

class ParseError(SystemExit):
    """Erro sintático.

    Herda de SystemExit para manter o comportamento da CLI (mensagem no stderr e
    saída com código 1), mas pode ser capturado pela interface web
    (`except ParseError`) para exibir o erro ao aluno.
    """
    def __init__(self, message: str, line: int) -> None:
        super().__init__(1)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return self.message


class Parser(ISintatico):
    """Implementação da interface ISintatico."""

    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        """Token atual (sem consumir)."""
        if self._pos >= len(self._tokens): return self._tokens[-1]
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        """Consome e retorna o token atual."""
        token = self._tokens[self._pos]
        if self._pos < len(self._tokens): self._pos += 1
        return token

    def _match(self, token_type: TokenType) -> bool:
        """Se o token atual for do tipo esperado, consome e retorna True."""
        if self._peek().type == token_type:
            self._advance()
            return True
        return False

    def _fail(self, line: int, message: str, prefix: str = "[ERRO SINTATICO]") -> None:
        """Tratamento de erro sintático: mostra 'Linha N: mensagem' e lança ParseError."""
        full = f"Linha {line}: {message}"
        print(f"{prefix} {full}", file=sys.stderr)
        raise ParseError(full, line)

    def _consume(self, token_type: TokenType, err_msg: str) -> Token:
        """Exige um token do tipo indicado; senão, erro sintático com o token encontrado."""
        if self._peek().type == token_type: return self._advance()
        tok = self._peek()
        self._fail(tok.line, f"{err_msg} (Encontrado: {tok.lexeme!r})")

    def _parse_var_decl(self, declared_type: str = "var", require_semicolon: bool = True) -> ASTNode:
        """<declaracao_variavel> ::= ("var" | <tipo>) IDENT [ "=" <expressao> ] ";" """
        node = VarDecl(name="")
        node.line = self._peek().line
        node.type = declared_type
        node.name = self._consume(TokenType.IDENTIFIER, "Esperado nome da variavel").lexeme
        if self._match(TokenType.ASSIGN):
            node.init_value = self._parse_expression()
        if require_semicolon:
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos declaracao de variavel")
        return node

    def _parse_assignment_tail(self, target: ASTNode, require_semicolon: bool = True) -> ASTNode:
        """<atribuicao> ::= <alvo_atribuicao> "=" <expressao> ";"   (alvo: IDENT, obj.campo ou lista[i])"""
        val = self._parse_expression()
        if require_semicolon:
            self._consume(TokenType.SEMICOLON, "Esperado ';'")
        if isinstance(target, IdentifierExpr): return Assignment(name=target.name, value=val, line=target.line)
        if isinstance(target, PropertyAccess): return PropertyAssign(object=target.object, property_name=target.property_name, value=val, line=target.line)
        if isinstance(target, IndexExpr): return IndexAssign(target=target, value=val, line=target.line)
        self._fail(target.line, "Atribuicao invalida", prefix="[ERRO]")

    def _parse_print_stmt(self) -> ASTNode:
        """<comando_print> ::= "print" "(" [ <expressao> { "," <expressao> } ] ")" ";" """
        node = PrintStmt()
        node.line = self._peek().line
        self._consume(TokenType.LPAREN, "Esperado '(' apos print")
        if self._peek().type != TokenType.RPAREN:
            node.arguments.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                node.arguments.append(self._parse_expression())
        self._consume(TokenType.RPAREN, "Esperado ')' apos argumentos do print")
        self._consume(TokenType.SEMICOLON, "Esperado ';' apos print")
        return node

    def _parse_send_stmt(self) -> ASTNode:
        """<comando_send> ::= "send" "(" <expressao> "," <expressao> ")" ";" """
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos send")
        channel = self._parse_expression()
        self._consume(TokenType.COMMA, "Esperado ',' entre canal e mensagem")
        message = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')'")
        self._consume(TokenType.SEMICOLON, "Esperado ';'")
        return SendStmt(channel=channel, message=message, line=line)

    def _parse_seq_block(self) -> ASTNode:
        """<bloco_seq> ::= [ "seq" ] "{" { <comando> } "}" """
        node = SeqBlock()
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            node.statements.append(self._parse_statement())
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco")
        return node

    def _parse_par_block(self) -> ASTNode:
        """<bloco_par> ::= "par" "{" { <comando> } "}"   (cada comando vira uma thread)"""
        node = ParBlock()
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco PAR")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            node.statements.append(self._parse_statement())
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco PAR")
        return node

    def _parse_pure_block(self) -> ASTNode:
        """<bloco_pure> ::= ("pure" | "@pure") <comando>   (SPar: laço/bloco sem efeitos colaterais externos)"""
        line = self._tokens[self._pos - 1].line
        if self._peek().type == TokenType.FOR:
            self._advance()
            body = self._parse_for_stmt()
        elif self._peek().type == TokenType.LBRACE:
            body = self._parse_seq_block()
        else:
            body = self._parse_statement()
        return PureBlock(body=body, line=line)

    def _parse_impure_block(self) -> ASTNode:
        """<bloco_impure> ::= ("impure" | "@impure") "{" { <comando> } "}"   (região crítica protegida por mutex)"""
        line = self._tokens[self._pos - 1].line
        statements = []
        self._consume(TokenType.LBRACE, "Esperado '{' apos 'impure'")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            statements.append(self._parse_statement())
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco 'impure'")
        return ImpureBlock(statements=statements, line=line)

    def _is_call_statement_ahead(self) -> bool:
        """Lookahead: IDENT '(' ... ')' seguido de ';' ou '.' é uma chamada (ex.: fork f();)
        e não o nome da tarefa com alocação legada (ex.: fork t1(4) { ... })."""
        if self._peek().type != TokenType.IDENTIFIER:
            return False
        i = self._pos + 1
        if i >= len(self._tokens) or self._tokens[i].type != TokenType.LPAREN:
            return False
        depth = 0
        while i < len(self._tokens):
            t = self._tokens[i].type
            if t == TokenType.LPAREN: depth += 1
            elif t == TokenType.RPAREN:
                depth -= 1
                if depth == 0: break
            elif t == TokenType.END_OF_FILE: return False
            i += 1
        nxt = self._tokens[i + 1].type if i + 1 < len(self._tokens) else TokenType.END_OF_FILE
        return nxt in (TokenType.SEMICOLON, TokenType.DOT)

    def _parse_alloc_args(self, kind: str) -> list:
        """'(' expr [ ',' expr ] ')' da alocação @nucleo(n) / @computador(ip, porta)."""
        self._consume(TokenType.LPAREN, f"Esperado '(' apos '@{kind}'")
        args = [self._parse_expression()]
        while self._match(TokenType.COMMA):
            args.append(self._parse_expression())
        self._consume(TokenType.RPAREN, f"Esperado ')' apos argumentos de '@{kind}'")
        return args

    def _parse_fork_block(self) -> ASTNode:
        """<bloco_fork> ::= "fork" [ IDENT ] [ <alocacao> ] <comando>
        <alocacao>  ::= "@nucleo" "(" expr ")"
                      | "@computador" "(" expr "," expr ")" | "@computador" "(" expr ")"
                      | "(" expr ")"            (forma legada = @nucleo)
        """
        line = self._tokens[self._pos - 1].line
        task_name = None
        alloc_kind = None
        alloc_args: list = []
        if self._peek().type == TokenType.IDENTIFIER and not self._is_call_statement_ahead():
            task_name = self._advance().lexeme
        if self._match(TokenType.ALLOC_NUCLEO):
            alloc_kind, alloc_args = "nucleo", self._parse_alloc_args("nucleo")
        elif self._match(TokenType.ALLOC_COMPUTADOR):
            alloc_kind, alloc_args = "computador", self._parse_alloc_args("computador")
        elif task_name and self._match(TokenType.LPAREN):
            alloc_kind = "nucleo"
            alloc_args = [self._parse_expression()]
            self._consume(TokenType.RPAREN, "Esperado ')' apos alocacao de nucleo no fork")
        if alloc_kind == "nucleo" and len(alloc_args) != 1:
            self._fail(line, "'@nucleo' espera 1 argumento (numero do nucleo)")
        if alloc_kind == "computador" and len(alloc_args) not in (1, 2):
            self._fail(line, "'@computador' espera (ip, porta) ou (canal)")
        if self._peek().type == TokenType.LBRACE:
            body = self._parse_seq_block()
        else:
            body = self._parse_statement()
        return ForkBlock(body=body, task_name=task_name, alloc_kind=alloc_kind, alloc_args=alloc_args, line=line)

    def _parse_join_stmt(self) -> ASTNode:
        """<comando_join> ::= "join" [ IDENT { "," IDENT } ] ";"   (barreira: espera as subtarefas do fork)"""
        line = self._tokens[self._pos - 1].line
        target_tasks = []
        while self._peek().type == TokenType.IDENTIFIER:
            target_tasks.append(self._advance().lexeme)
            if not self._match(TokenType.COMMA):
                break
        self._match(TokenType.SEMICOLON)
        return JoinStmt(target_tasks=target_tasks, line=line)

    def _parse_if_stmt(self) -> ASTNode:
        """<comando_if> ::= "if" "(" <expressao> ")" <comando> [ "else" <comando> ]"""
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'if'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao do 'if'")
        then_branch = self._parse_statement()
        else_branch = self._parse_statement() if self._match(TokenType.ELSE) else None
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch, line=line)

    def _parse_while_stmt(self) -> ASTNode:
        """<comando_while> ::= "while" "(" <expressao> ")" <comando>"""
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        body = self._parse_statement()
        return WhileStmt(condition=condition, body=body, line=line)

    def _parse_do_while_stmt(self) -> ASTNode:
        """<comando_do_while> ::= "do" <comando> "while" "(" <expressao> ")" [ ";" ]"""
        line = self._tokens[self._pos - 1].line
        body = self._parse_statement()
        self._consume(TokenType.WHILE, "Esperado 'while' apos bloco do")
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        self._match(TokenType.SEMICOLON)
        return DoWhileStmt(body=body, condition=condition, line=line)

    def _parse_for_stmt(self) -> ASTNode:
        """<comando_for> ::= "for" "(" (<for_classico> | <for_iterador>) ")" <comando>
        <for_classico> ::= [ init ] ";" [ <expressao> ] ";" [ incremento ]
        <for_iterador> ::= "var" IDENT "in" <expressao>"""
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'for'")
        initializer = condition = increment = iterator_name = iterable = None

        if self._match(TokenType.VAR):
            name_tok = self._consume(TokenType.IDENTIFIER, "Esperado variavel do for")
            if self._match(TokenType.IN):
                iterator_name = name_tok.lexeme
                iterable = self._parse_expression()
                self._consume(TokenType.RPAREN, "Esperado ')' apos iteravel")
                body = self._parse_statement()
                return ForStmt(None, None, None, body, iterator_name, iterable, line)
            initializer = VarDecl(name=name_tok.lexeme, type="var", line=name_tok.line)
            if self._match(TokenType.ASSIGN):
                initializer.init_value = self._parse_expression()
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            initializer = self._parse_var_decl(type_tok.lexeme, require_semicolon=False)
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif not self._match(TokenType.SEMICOLON):
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                initializer = self._parse_assignment_tail(target, require_semicolon=False)
            else:
                initializer = target
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")

        if not self._match(TokenType.SEMICOLON):
            condition = self._parse_expression()
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos condicao do for")

        if self._peek().type != TokenType.RPAREN:
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                increment = self._parse_assignment_tail(target, require_semicolon=False)
            else:
                increment = target
        self._consume(TokenType.RPAREN, "Esperado ')' apos for")
        body = self._parse_statement()
        return ForStmt(initializer, condition, increment, body, line=line)

    def _parse_class_decl(self) -> ASTNode:
        """<declaracao_classe> ::= "class" IDENT [ "extends" IDENT ] "{" { "var" <decl_var> | "func" <decl_func> } "}" """
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe").lexeme
        superclass = self._consume(TokenType.IDENTIFIER, "Esperado nome da superclasse").lexeme if self._match(TokenType.EXTENDS) else None
        self._consume(TokenType.LBRACE, "Esperado '{' na classe")
        attrs, methods = [], []
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            if self._match(TokenType.VAR): attrs.append(self._parse_var_decl())
            elif self._match(TokenType.FUNC): methods.append(self._parse_func_decl())
            else: self._consume(TokenType.UNKNOWN, "Esperado 'var' ou 'func' na definicao da classe")
        self._consume(TokenType.RBRACE, "Esperado '}' no fim da classe")
        return ClassDecl(name=name, superclass=superclass, attributes=attrs, methods=methods, line=line)

    def _parse_func_decl(self) -> ASTNode:
        """<declaracao_funcao> ::= "func" IDENT "(" [ [<tipo>] IDENT { "," [<tipo>] IDENT } ] ")" <bloco_seq>"""
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da funcao").lexeme
        self._consume(TokenType.LPAREN, "Esperado '('")
        params = []
        if self._peek().type != TokenType.RPAREN:
            if self._peek().type == TokenType.TYPE:
                self._advance()
            params.append(self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme)
            while self._match(TokenType.COMMA):
                if self._peek().type == TokenType.TYPE:
                    self._advance()
                params.append(self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme)
        self._consume(TokenType.RPAREN, "Esperado ')'")
        body = self._parse_seq_block()
        return FuncDecl(name=name, params=params, body=body, line=line)

    def _parse_return_stmt(self) -> ASTNode:
        """<comando_return> ::= "return" [ <expressao> ] ";" """
        line = self._tokens[self._pos - 1].line
        value = None if self._peek().type == TokenType.SEMICOLON else self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return ReturnStmt(value=value, line=line)

    def _parse_statement(self) -> ASTNode:
        """<comando>: escolhe a produção pelo primeiro token (análise descendente recursiva LL(1)).

        Expressões que começam um comando só são aceitas como atribuição
        (alvo = expr;) ou como chamada de função/método (f(...); obj.m(...);)."""
        if self._match(TokenType.CLASS): return self._parse_class_decl()
        if self._match(TokenType.FUNC): return self._parse_func_decl()
        if self._match(TokenType.RETURN): return self._parse_return_stmt()
        if self._match(TokenType.BREAK):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return BreakStmt(line=line)
        if self._match(TokenType.CONTINUE):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return ContinueStmt(line=line)
        if self._match(TokenType.VAR): return self._parse_var_decl()
        if self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            return self._parse_var_decl(type_tok.lexeme)
        if self._match(TokenType.SEQ) or self._peek().type == TokenType.LBRACE: 
            if self._peek().type == TokenType.SEQ: self._advance()
            return self._parse_seq_block()
        if self._match(TokenType.PAR): return self._parse_par_block()
        if self._match(TokenType.PURE): return self._parse_pure_block()
        if self._match(TokenType.IMPURE): return self._parse_impure_block()
        if self._match(TokenType.FORK): return self._parse_fork_block()
        if self._match(TokenType.JOIN): return self._parse_join_stmt()
        if self._match(TokenType.PRINT): return self._parse_print_stmt()
        if self._match(TokenType.SEND): return self._parse_send_stmt()
        if self._match(TokenType.IF): return self._parse_if_stmt()
        if self._match(TokenType.WHILE): return self._parse_while_stmt()
        if self._match(TokenType.DO): return self._parse_do_while_stmt()
        if self._match(TokenType.FOR): return self._parse_for_stmt()

        if self._peek().type in (TokenType.IDENTIFIER, TokenType.THIS, TokenType.NEW, TokenType.RECEIVE, TokenType.INPUT, TokenType.C_CHANNEL, TokenType.MATRIX, TokenType.LBRACKET):
            expr = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                return self._parse_assignment_tail(expr)
            elif isinstance(expr, (MethodCall, FuncCallExpr)):
                self._consume(TokenType.SEMICOLON, "Esperado ';'")
                return expr
            self._fail(expr.line, "Instrucao ou expressao isolada invalida", prefix="[ERRO]")

        tok = self._peek()
        self._fail(tok.line, f"Instrucao nao reconhecida: {tok.lexeme!r}")

    def _parse_expression(self) -> ASTNode:
        """<expressao> ::= <expressao_ou>   (precedência: || < && < comparação < + - < * / % < unário < posfixo)"""
        return self._parse_or()

    def _parse_or(self) -> ASTNode:
        """<expressao_ou> ::= <expressao_e> { "||" <expressao_e> }"""
        expr = self._parse_and()
        while self._match(TokenType.OR):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_and(), line=op_tok.line)
        return expr

    def _parse_and(self) -> ASTNode:
        """<expressao_e> ::= <expressao_comp> { "&&" <expressao_comp> }"""
        expr = self._parse_comparison()
        while self._match(TokenType.AND):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_comparison(), line=op_tok.line)
        return expr

    def _parse_comparison(self) -> ASTNode:
        """<expressao_comp> ::= <expressao_termo> { ("=="|"!="|"<"|">"|"<="|">=") <expressao_termo> }"""
        expr = self._parse_term()
        while self._peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_term())
            node.line = op_tok.line
            expr = node
        return expr

    def _parse_term(self) -> ASTNode:
        """<expressao_termo> ::= <expressao_fator> { ("+"|"-") <expressao_fator> }"""
        expr = self._parse_factor()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_factor())
            node.line = op_tok.line
            expr = node
        return expr

    def _parse_factor(self) -> ASTNode:
        """<expressao_fator> ::= <expressao_unaria> { ("*"|"/"|"%") <expressao_unaria> }"""
        expr = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.MOD):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_unary())
            node.line = op_tok.line
            expr = node
        return expr

    def _parse_unary(self) -> ASTNode:
        """<expressao_unaria> ::= ("-"|"+"|"!") <expressao_unaria> | <expressao_posfixo>"""
        if self._peek().type in (TokenType.MINUS, TokenType.PLUS, TokenType.NOT):
            op_tok = self._advance()
            node = UnaryExpr(op=op_tok.lexeme, operand=self._parse_unary())
            node.line = op_tok.line
            return node
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        """<expressao_primaria> seguida de sufixos posfixos ('.campo', '.metodo(...)', '[indice]').

        Primárias: número, string, bool, IDENT ou chamada IDENT(...), this, new C(...),
        c_channel(ip, porta), receive(canal), input([prompt]), [lista], matrix(l, c, v), ( expr )."""
        tok = self._peek()
        node = None

        if self._match(TokenType.MATRIX):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos matrix")
            rows = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            cols = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            init_val = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = MatrixCreateExpr(rows=rows, cols=cols, init_value=init_val, line=line)
        elif self._match(TokenType.LBRACKET):
            line = tok.line
            elements = []
            if self._peek().type != TokenType.RBRACKET:
                elements.append(self._parse_expression())
                while self._match(TokenType.COMMA): elements.append(self._parse_expression())
            self._consume(TokenType.RBRACKET, "Esperado ']'")
            node = ListLiteral(elements=elements, line=line)
        elif self._match(TokenType.C_CHANNEL):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos c_channel")
            ip = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ',' entre ip e porta")
            port = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = CChannelExpr(ip=ip, port=port, line=line)
        elif self._match(TokenType.RECEIVE):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos receive")
            channel = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = ReceiveExpr(channel=channel, line=line)
        elif self._match(TokenType.INPUT):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos input")
            prompt = None if self._peek().type == TokenType.RPAREN else self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')' apos input")
            node = InputExpr(prompt=prompt, line=line)
        elif self._match(TokenType.NEW):
            line = tok.line
            class_name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe").lexeme
            self._consume(TokenType.LPAREN, "Esperado '('")
            args = []
            if self._peek().type != TokenType.RPAREN:
                args.append(self._parse_expression())
                while self._match(TokenType.COMMA): args.append(self._parse_expression())
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = NewExpr(class_name=class_name, arguments=args, line=line)
        elif self._match(TokenType.THIS):
            node = ThisExpr(line=tok.line)
        elif self._match(TokenType.NUMBER):
            node = NumberExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.STRING_LITERAL):
            node = StringExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.BOOL_LITERAL):
            node = BoolExpr(value=(tok.lexeme == "true"), line=tok.line)
        elif self._match(TokenType.IDENTIFIER):
            name = tok.lexeme
            if self._match(TokenType.LPAREN):
                args = []
                if self._peek().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA): args.append(self._parse_expression())
                self._consume(TokenType.RPAREN, "Esperado ')'")
                node = FuncCallExpr(name=name, arguments=args, line=tok.line)
            else:
                node = IdentifierExpr(name=name, line=tok.line)
        elif self._match(TokenType.LPAREN):
            node = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
        else:
            self._fail(tok.line, "Expressao esperada")

        while True:
            if self._match(TokenType.DOT):
                prop_tok = self._consume(TokenType.IDENTIFIER, "Esperado identificador apos '.'")
                if self._match(TokenType.LPAREN):
                    args = []
                    if self._peek().type != TokenType.RPAREN:
                        args.append(self._parse_expression())
                        while self._match(TokenType.COMMA): args.append(self._parse_expression())
                    self._consume(TokenType.RPAREN, "Esperado ')'")
                    node = MethodCall(object=node, method_name=prop_tok.lexeme, arguments=args, line=prop_tok.line)
                else:
                    node = PropertyAccess(object=node, property_name=prop_tok.lexeme, line=prop_tok.line)
            elif self._match(TokenType.LBRACKET):
                idx_tok = self._tokens[self._pos - 1]
                idx = self._parse_expression()
                self._consume(TokenType.RBRACKET, "Esperado ']'")
                node = IndexExpr(object=node, index=idx, line=idx_tok.line)
            else:
                break

        return node

    def parse(self) -> Program:
        """<programa> ::= { <declaracao_global> | <comando> }   — retorna o nó raiz Program da AST."""
        prog = Program()
        while self._peek().type != TokenType.END_OF_FILE:
            stmt = self._parse_statement()
            if stmt: prog.statements.append(stmt)
        return prog
