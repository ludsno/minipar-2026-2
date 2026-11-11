"""
Testes de Software de Integração dos Componentes do Compilador MiniPar 2026.2
(Seção 13 do relatório).

Organização (do componente isolado até o sistema completo):
  T1  Componentes implementam suas interfaces (ILexico, ISintatico, ...)
  T2  C_Lexer isolado
  T3  Integração C_Lexer -> C_Parser (tokens -> AST)
  T4  Integração C_Parser -> C_Semantic / C_TabelaSimbolos (AST -> validação)
  T5  Integração C_Semantic -> C_TAC / C_CodeGen (AST validada -> TAC e C++)
  T6  Programas de teste: .minipar -> TAC + C++ -> g++ -> .exe -> saída esperada
  T7  Interface Web didática (C_DidacticWeb) usando os componentes via Flask

Executar na raiz do projeto:
    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import contextlib
import glob
import io
import os
import shutil
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)  # o gerador de código grava em output/

from lexer import Lexer, TokenType                    # noqa: E402
from parser import Parser, ParseError                 # noqa: E402
from semantic import SemanticAnalyzer, TabelaSimbolos  # noqa: E402
from tac import TACGenerator                          # noqa: E402
from codegen import CppCodeGenerator                  # noqa: E402
from componentes import ILexico, ISintatico, ISemantico, ITabelaSimbolos, ITAC, ICodeGen  # noqa: E402
from ast_nodes import (                               # noqa: E402
    PureBlock, ImpureBlock, ForkBlock, JoinStmt, ForStmt, SeqBlock, VarDecl, BinaryExpr, FuncCallExpr,
)

TEM_GPP = shutil.which("g++") is not None
try:
    import flask  # noqa: F401
    TEM_FLASK = True
except ImportError:
    TEM_FLASK = False


def ler(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


def analisar(codigo: str):
    """Executa Léxico -> Sintático -> Semântico e retorna (tokens, programa, semantico, valido)."""
    with contextlib.redirect_stderr(io.StringIO()):
        tokens = Lexer(codigo).tokenize()
        programa = Parser(tokens).parse()
        semantico = SemanticAnalyzer()
        valido = semantico.analyze(programa)
    return tokens, programa, semantico, valido


# ---------------------------------------------------------------------------
class T1_InterfacesDosComponentes(unittest.TestCase):
    def test_cada_componente_implementa_sua_interface(self):
        self.assertIsInstance(Lexer(""), ILexico)
        self.assertIsInstance(Parser(Lexer("").tokenize()), ISintatico)
        self.assertIsInstance(SemanticAnalyzer(), ISemantico)
        self.assertIsInstance(TabelaSimbolos(), ITabelaSimbolos)
        self.assertIsInstance(TACGenerator(), ITAC)
        self.assertIsInstance(CppCodeGenerator(), ICodeGen)


# ---------------------------------------------------------------------------
class T2_Lexico(unittest.TestCase):
    def tipos(self, codigo):
        return [t.type for t in Lexer(codigo).tokenize()]

    def test_palavras_reservadas_e_anotacoes(self):
        tipos = self.tipos("pure @pure impure @impure fork join @nucleo @computador")
        self.assertEqual(tipos, [TokenType.PURE, TokenType.PURE, TokenType.IMPURE, TokenType.IMPURE,
                                 TokenType.FORK, TokenType.JOIN, TokenType.ALLOC_NUCLEO,
                                 TokenType.ALLOC_COMPUTADOR, TokenType.END_OF_FILE])

    def test_nucleo_sem_arroba_continua_identificador(self):
        self.assertEqual(self.tipos("nucleo")[0], TokenType.IDENTIFIER)

    def test_comentarios_sao_descartados(self):
        self.assertEqual(self.tipos("# comentario\nvar x = 1; # fim"),
                         [TokenType.VAR, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER,
                          TokenType.SEMICOLON, TokenType.END_OF_FILE])

    def test_string_com_escapes_e_operadores_duplos(self):
        tokens = Lexer('"a\\tb" <= >= == != && ||').tokenize()
        self.assertEqual(tokens[0].lexeme, "a\tb")
        self.assertEqual([t.lexeme for t in tokens[1:-1]], ["<=", ">=", "==", "!=", "&&", "||"])

    def test_linha_e_coluna(self):
        tokens = Lexer("var a = 1;\n  print(a);").tokenize()
        imprime = [t for t in tokens if t.type == TokenType.PRINT][0]
        self.assertEqual((imprime.line, imprime.col), (2, 3))


# ---------------------------------------------------------------------------
class T3_LexicoParaSintatico(unittest.TestCase):
    def test_pure_for_com_impure_vira_nos_da_ast(self):
        _, programa, _, _ = analisar("var s = 0;\npure for (var i = 0; i < 4; i = i + 1) { impure { s = s + i; } }")
        pure = programa.statements[1]
        self.assertIsInstance(pure, PureBlock)
        self.assertIsInstance(pure.body, ForStmt)
        self.assertIsInstance(pure.body.body, SeqBlock)
        self.assertIsInstance(pure.body.body.statements[0], ImpureBlock)

    def test_fork_com_alocacao_em_nucleo_e_computador(self):
        codigo = ('fork a @nucleo(1) { print(1); }\n'
                  'fork b @computador("127.0.0.1", 6000) { print(2); }\n'
                  'fork c(2) { print(3); }\njoin a, b;')
        _, programa, _, _ = analisar(codigo)
        a, b, c, j = programa.statements
        self.assertEqual((a.task_name, a.alloc_kind, len(a.alloc_args)), ("a", "nucleo", 1))
        self.assertEqual((b.task_name, b.alloc_kind, len(b.alloc_args)), ("b", "computador", 2))
        self.assertEqual((c.task_name, c.alloc_kind), ("c", "nucleo"))  # forma legada fork t(n)
        self.assertIsInstance(j, JoinStmt)
        self.assertEqual(j.target_tasks, ["a", "b"])

    def test_fork_de_chamada_sem_nome_nao_e_ambiguo(self):
        _, programa, _, _ = analisar("func g() { print(1); }\nfork g();\njoin;")
        fork = programa.statements[1]
        self.assertIsInstance(fork, ForkBlock)
        self.assertIsNone(fork.task_name)
        self.assertIsInstance(fork.body, FuncCallExpr)

    def test_precedencia_dos_operadores(self):
        _, programa, _, _ = analisar("var x = 1 + 2 * 3;")
        expr = programa.statements[0].init_value
        self.assertIsInstance(programa.statements[0], VarDecl)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.right, BinaryExpr)
        self.assertEqual(expr.right.op, "*")

    def test_erro_sintatico_lanca_parse_error_com_linha(self):
        with self.assertRaises(ParseError) as ctx:
            analisar("var a = 1;\nvar x = ;")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("Linha 2", ctx.exception.message)


# ---------------------------------------------------------------------------
class T4_SintaticoParaSemantico(unittest.TestCase):
    def erros(self, codigo):
        _, _, semantico, valido = analisar(codigo)
        return valido, " | ".join(semantico.get_errors())

    def test_programa_valido(self):
        self.assertEqual(self.erros("func f(a) { return a * 2; }\nvar x = f(3);\nprint(x);"), (True, ""))

    def test_impure_fora_de_pure(self):
        valido, erros = self.erros("var x = 0;\nimpure { x = 1; }")
        self.assertFalse(valido)
        self.assertIn("impure", erros)

    def test_condicao_de_corrida_em_pure(self):
        valido, erros = self.erros("var s = 0;\npure for (var i = 0; i < 3; i = i + 1) { s = s + i; }")
        self.assertFalse(valido)
        self.assertIn("condicao de corrida", erros)

    def test_escrita_em_posicao_propria_dentro_de_pure_e_permitida(self):
        codigo = "var m = matrix(3, 3, 0);\npure for (var i = 0; i < 3; i = i + 1) { m[i][0] = i; }"
        self.assertEqual(self.erros(codigo), (True, ""))

    def test_fork_remoto_nao_acessa_variavel_externa(self):
        valido, erros = self.erros('var x = 1;\nfork t @computador("127.0.0.1", 6000) { print(x); }\njoin;')
        self.assertFalse(valido)
        self.assertIn("outro computador", erros)

    def test_erros_classicos(self):
        casos = {
            "print(y);": "nao declarada",
            "var a = 1;\nvar a = 2;": "ja declarada",
            'number n = "texto";': "Tipo incompativel",
            "func f(a, b) { return a + b; }\nprint(f(1));": "espera 2 argumento",
            "break;": "fora de laco",
            "var o = new Nada();": "Classe 'Nada' nao declarada",
        }
        for codigo, trecho in casos.items():
            with self.subTest(codigo=codigo):
                valido, erros = self.erros(codigo)
                self.assertFalse(valido)
                self.assertIn(trecho, erros)

    def test_tabela_de_simbolos_registra_escopos(self):
        _, _, semantico, _ = analisar("var g = 1;\nfunc f(p) { var loc = p; return loc; }\n"
                                      "pure for (var i = 0; i < 2; i = i + 1) { var v = i; }")
        escopos = {(s["name"], s["scope"]) for s in semantico.get_symbol_table()}
        self.assertIn(("g", "Global"), escopos)
        self.assertIn(("loc", "Func:f"), escopos)
        self.assertIn(("v", "PureBlock"), escopos)


# ---------------------------------------------------------------------------
class T5_SemanticoParaGeradores(unittest.TestCase):
    CODIGO = ('var s = 0;\npure for (var i = 0; i < 4; i = i + 1) { impure { s = s + i; } }\n'
              'fork a @nucleo(1) { print(1); }\n'
              'fork b @computador("127.0.0.1", 6000) { print(2); }\njoin;')

    def setUp(self):
        _, self.programa, _, valido = analisar(self.CODIGO)
        self.assertTrue(valido)

    def test_tac_tem_as_diretivas_de_paralelismo(self):
        tac = TACGenerator().generate_text(self.programa)
        for diretiva in ("BEGIN_PURE_MAP", "END_PURE_MAP", "ACQUIRE_LOCK", "RELEASE_LOCK",
                         "FORK_TASK a @nucleo(1):", 'FORK_TASK b @computador("127.0.0.1", 6000):', "JOIN_TASKS ALL"):
            self.assertIn(diretiva, tac)

    def test_tac_do_teste7_e_gerado_pelo_compilador(self):
        codigo = ler("tests/teste7_quicksort_iterativo_tac.minipar")
        _, programa, _, _ = analisar(codigo)
        tac = TACGenerator().generate_text(programa)
        referencia = ler("tests/expected_results/teste7_quicksort_iterativo_tac.expected.tac")
        self.assertIn("func quicksort_iterativo:", tac)
        self.assertNotEqual(tac, referencia)  # sem atalho: o TAC vem da AST do programa

    def test_cpp_traduz_pure_impure_e_fork_com_alocacao(self):
        cpp = CppCodeGenerator().generate_cpp_code(self.programa)
        for trecho in ("__minipar_pure_map(", "std::lock_guard<std::mutex>", "__minipar_fixar_nucleo(",
                       "__minipar_executar_remoto(", "__minipar_servir_tarefas(", "__minipar_finalizar();"):
            self.assertIn(trecho, cpp)


# ---------------------------------------------------------------------------
@unittest.skipUnless(TEM_GPP, "g++ nao encontrado")
class T6_ProgramasDeTeste(unittest.TestCase):
    """Integração completa de todos os componentes com os programas de teste."""

    # (arquivo, entrada padrão, trechos que precisam aparecer na saída)
    CASOS = [
        # Sem informar o IP do servidor: roda em 1 computador e avisa
        ("teste1_calculadora_cliente_servidor", "*\n7\n6\n", ["Servidor recebeu: * 7 6", "Resultado: 42",
                                                               "Nenhum computador extra aberto em 127.0.0.1:5100"]),
        ("teste2_fatorial_fibonacci_par", "", ["Fatorial de 5: 120", "13"]),
        ("teste3_neuronio", "", ["Neuronio aprendeu", "Iteracoes totais: 51"]),
        ("teste4_rede_neural_xor", "", ["Input: [0, 0], Predicted Output:", "Input: [1, 1], Predicted Output:"]),
        # histórico do enunciado: Smartphone, Jeans, Micro-ondas e Ficção
        ("teste5_recomendacao", "1\n0\n0\n0\n0\n1\n0\n0\n0\n1\n0\n0\n1\n0\n0\n0\n",
         ["Laptop", "Tablet", "Fones de ouvido", "Camisa", "Jaqueta", "Sapatos", "Geladeira",
          "Maquina de lavar", "Ar condicionado", "Nao-ficcao", "Ficcao cientifica", "Fantasia"]),
        ("teste6_quicksort_classes", "10 -3 -40 80 70 -100\n", ["Vetor ordenado: [-100, -40, -3, 10, 70, 80]"]),
        ("teste7_quicksort_iterativo_tac", "", ["Array ordenado: [5, 12, 33, 61, 98]"]),
        ("teste8_avaliacao_4nucleos", "", ["Total de Atividades a Avaliar: 160 (40 alunos x 4 atividades)",
                                           "as 160 correcoes paralelas conferem com as sequenciais (OK)",
                                           "BENCHMARK DE DESEMPENHO", "Aceleracao       :"]),
        ("teste9_mandelbrot_5nucleos", "", ["conferem com o sequencial (OK)", "Nucleos Utilizados (Paralelo) : 5",
                                            "Iteracoes calculadas (acumuladas na regiao impure): 26553"]),
        ("teste10_6nucleos_2fractais", "", ["Celulas preenchidas (acumuladas na regiao impure): 512",
                                            "Tapete de Sierpinski renderizado com sucesso",
                                            "conferem com o sequencial (OK)", "Nucleos Utilizados (Paralelo) : 6"]),
        ("teste_adicional1_paralelismo_3_computadores", "", ["PC1 QuickSort", "PC2 Matrizes", "PC3 Fatorial: 5! = 120"]),
        ("teste_adicional2_tapete_sierpinski", "", ["[#,  , #, #,  , #, #,  , #]"]),
        ("teste_ascii_art_divertidapkrl", "", ["Calculo finalizado"]),
        ("teste_bnf_controles_input", "", ["Controle OK: 7 2"]),
        ("teste_sanidade_fase1", "", ["Resultado da soma apos Pure/Impure:  380", "Resultado Tarefa A:  150"]),
        ("teste_pure_speedup_mandelbrot", "", ["mesmo resultado nas duas versoes (OK)"]),
        ("teste_fork_nucleos_computadores", "", ["(calculada no computador 2) = 50005000",
                                                 "(calculado no computador 3) = 479001600"]),
        # ENTER nas 3 perguntas de IP -> 127.0.0.1 (trabalhadores iniciados automaticamente)
        ("demo_varios_computadores", "\n\n\n", ["calculada no computador 127.0.0.1 = 50005000",
                                                "calculado no computador 127.0.0.1 = 479001600"]),
    ]

    @classmethod
    def setUpClass(cls):
        cls.compilacao = {}
        for caminho in sorted(glob.glob("tests/*.minipar")):
            nome = os.path.basename(caminho)[:-len(".minipar")]
            r = subprocess.run([sys.executable, "main.py", caminho, nome], capture_output=True, text=True, timeout=120)
            cls.compilacao[nome] = (r.returncode, r.stdout + r.stderr)

    def executar(self, nome, entrada="", ambiente=None):
        env = dict(os.environ, **(ambiente or {}))
        r = subprocess.run([os.path.abspath(f"output/{nome}.exe")], input=entrada, capture_output=True,
                           text=True, timeout=90, env=env)
        return r.returncode, r.stdout

    def test_todos_os_programas_compilam(self):
        self.assertGreaterEqual(len(self.compilacao), 18)
        for nome, (rc, log) in self.compilacao.items():
            with self.subTest(programa=nome):
                self.assertEqual(rc, 0, log[-800:])

    def test_saidas_esperadas(self):
        for nome, entrada, trechos in self.CASOS:
            with self.subTest(programa=nome):
                rc, saida = self.executar(nome, entrada)
                self.assertEqual(rc, 0)
                for trecho in trechos:
                    self.assertIn(trecho, saida)

    def test_teste5_recomenda_os_12_produtos_do_enunciado(self):
        _, saida = self.executar("teste5_recomendacao", self.CASOS[4][1])
        self.assertEqual(sum("probabilidade" in linha for linha in saida.splitlines()), 12)

    def test_mandelbrot_igual_ao_do_programa_python_do_professor(self):
        """As 20 linhas do fractal (testes 9 e 10) são idênticas às do Python do enunciado."""
        esperado = ler("tests/expected_results/teste9_mandelbrot_professor.expected.txt").splitlines()
        for nome in ("teste9_mandelbrot_5nucleos", "teste10_6nucleos_2fractais"):
            with self.subTest(programa=nome):
                _, saida = self.executar(nome)
                desenho = saida.split("=== FRACTAL DE MANDELBROT (Gerado pelo Nucleo 5) ===\n")[1]
                self.assertEqual(desenho.splitlines()[:20], esperado)

    def test_pure_da_o_mesmo_resultado_com_1_ou_varias_threads(self):
        for threads in ("1", "4"):
            with self.subTest(threads=threads):
                _, saida = self.executar("teste_pure_speedup_mandelbrot", ambiente={"MINIPAR_PURE_THREADS": threads})
                self.assertIn("mesmo resultado nas duas versoes (OK)", saida)

    def test_entrada_invalida_nao_trava_o_teste1(self):
        """Sem entradas (caixa vazia na web), to_number recebe "": avisa e usa 0, sem travar."""
        rc, saida = self.executar("teste1_calculadora_cliente_servidor", "")
        self.assertEqual(rc, 0)
        self.assertIn("Resultado: 0", saida)

    def test_teste1_sockets_estavel(self):
        for _ in range(3):
            _, saida = self.executar("teste1_calculadora_cliente_servidor", "+\n2\n3\n")
            self.assertIn("Resultado: 5", saida)


# ---------------------------------------------------------------------------
@unittest.skipUnless(TEM_FLASK, "Flask nao instalado")
class T7_InterfaceWebDidatica(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app, extract_benchmark_metrics
        cls.cliente = app.test_client()
        cls.extrair = staticmethod(extract_benchmark_metrics)

    def test_inspect_retorna_todas_as_fases(self):
        codigo = ler("tests/teste_sanidade_fase1.minipar")
        dados = self.cliente.post("/api/inspect", json={"code": codigo}).get_json()
        self.assertTrue(dados["success"])
        self.assertGreater(dados["tokens_count"], 0)
        self.assertEqual(dados["ast"]["type"], "Program")
        self.assertGreater(len(dados["symbols"]), 0)
        self.assertIn("BEGIN_PURE_MAP", dados["tac"])
        self.assertIn("__minipar_pure_map", dados["cpp"])

    def test_inspect_mostra_erro_sintatico_e_semantico(self):
        sint = self.cliente.post("/api/inspect", json={"code": "var x = ;"}).get_json()
        self.assertEqual((sint["success"], sint["phase"]), (False, "parser"))
        self.assertIn("Linha 1", sint["error"])
        sem = self.cliente.post("/api/inspect", json={"code": "impure { print(1); }"}).get_json()
        self.assertEqual((sem["success"], sem["phase"]), (False, "semantic"))

    def test_metricas_de_benchmark(self):
        saida = ("Nucleos Utilizados (Paralelo) : 4\nTempo Sequencial             :  2.4 s\n"
                 "Tempo Paralelo               :  0.6 s\nAceleracao (Speedup)         :  4 x mais rapido!\n"
                 "Reducao de Tempo             :  75 %\n")
        m = self.extrair(saida)
        self.assertEqual((m["speedup"], m["time_seq"], m["time_par"], m["reduction_pct"], m["cores"]),
                         (4.0, 2.4, 0.6, 75.0, 4))

    def test_nome_de_arquivo_nao_sai_da_pasta_tests(self):
        r = self.cliente.post("/api/get_test", json={"filename": "../README.md"})
        self.assertEqual(r.status_code, 404)

    @unittest.skipUnless(TEM_GPP, "g++ nao encontrado")
    def test_compilar_e_baixar_executavel(self):
        dados = self.cliente.post("/api/build", json={"code": 'print("ok");', "filename": "teste_web_build.minipar"}).get_json()
        self.assertTrue(dados["success"], dados.get("log"))
        r = self.cliente.get(dados["download_url"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/octet-stream")
        r.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
