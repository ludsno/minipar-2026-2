from flask import Flask, render_template, request, jsonify, send_file, abort
import subprocess
import os
import sys
import glob
import time
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lexer import Lexer, TokenType
from parser import Parser, ParseError
from semantic import SemanticAnalyzer
from tac import TACGenerator
from codegen import CppCodeGenerator
from ast_nodes import ast_to_dict

from test_orchestrator import (
    get_spec_summary,
    finalize_test_execution,
    check_active_session_for_new_terminal,
    join_session,
    get_terminal_id,
    create_session,
    clear_session,
    set_session_phase,
    append_session_log,
    record_execution_output,
    _load_session,
    _save_session,
)

app = Flask(__name__)

# Configuração de Diretórios
TESTS_DIR = 'tests'
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp_code'

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def categorize_token(tok_type: TokenType) -> str:
    name = tok_type.name
    if name in ('PURE', 'IMPURE'):
        return 'Anotação SPar'
    if name in ('FORK', 'JOIN', 'SEQ', 'PAR', 'ALLOC_NUCLEO', 'ALLOC_COMPUTADOR'):
        return 'Paralelismo & Concorrência'
    if name in ('CLASS', 'EXTENDS', 'NEW', 'FUNC', 'THIS'):
        return 'Orientação a Objetos'
    if name in ('IF', 'ELSE', 'WHILE', 'DO', 'FOR', 'IN', 'BREAK', 'CONTINUE', 'RETURN'):
        return 'Estrutura de Controle'
    if name in ('VAR', 'TYPE'):
        return 'Declaração & Tipo'
    if name in ('PRINT', 'INPUT', 'C_CHANNEL', 'SEND', 'RECEIVE', 'MATRIX'):
        return 'E/S & Comunicação'
    if name in ('NUMBER',):
        return 'Literal Numérico'
    if name in ('STRING_LITERAL',):
        return 'Literal Texto'
    if name in ('BOOL_LITERAL',):
        return 'Literal Booleano'
    if name in ('IDENTIFIER',):
        return 'Identificador'
    if name in ('PLUS', 'MINUS', 'STAR', 'SLASH', 'MOD', 'ASSIGN', 'EQ', 'NEQ', 'NOT', 'AND', 'OR', 'LT', 'GT', 'LTE', 'GTE'):
        return 'Operador'
    if name in ('LPAREN', 'RPAREN', 'LBRACE', 'RBRACE', 'LBRACKET', 'RBRACKET', 'DOT', 'SEMICOLON', 'COMMA'):
        return 'Delimitador'
    if name == 'END_OF_FILE':
        return 'Fim de Arquivo'
    return 'Outro'


def extract_benchmark_metrics(output_text: str) -> dict:
    metrics = {
        "is_benchmark": False,
        "speedup": None,
        "time_seq": None,
        "time_par": None,
        "reduction_pct": None,
        "cores": None,
    }
    if not output_text:
        return metrics

    # Aceita os formatos impressos pelos testes, ex.:
    #   "Aceleracao (Speedup)         :  3.99729 x mais rapido!"
    #   "Tempo Sequencial             :  2.40017  s"
    #   "Reducao no tempo             :  74.983 % de economia"
    # e também formatos curtos como "Speedup: 3.98x".
    num = r'([0-9]+(?:\.[0-9]+)?(?:e[-+]?[0-9]+)?)'

    m_speedup = re.search(r'Speedup\)?(?:\s+obtido)?\s*[:=]\s*' + num, output_text, re.IGNORECASE)
    if m_speedup:
        metrics["speedup"] = round(float(m_speedup.group(1)), 2)
        metrics["is_benchmark"] = True

    m_seq = re.search(r'Tempo\s+Sequencial[^:=\n]*[:=]\s*' + num, output_text, re.IGNORECASE)
    if m_seq:
        metrics["time_seq"] = round(float(m_seq.group(1)), 4)
        metrics["is_benchmark"] = True

    m_par = re.search(r'Tempo\s+Paralelo[^:=\n]*[:=]\s*' + num, output_text, re.IGNORECASE)
    if m_par:
        metrics["time_par"] = round(float(m_par.group(1)), 4)
        metrics["is_benchmark"] = True

    m_red = re.search(r'Redu(?:c|ç)(?:a|ã)o[^:=\n%]*[:=]\s*' + num + r'\s*%', output_text, re.IGNORECASE)
    if m_red:
        metrics["reduction_pct"] = round(float(m_red.group(1)), 1)

    # Completa o que faltar a partir dos tempos medidos
    if metrics["time_seq"] and metrics["time_par"]:
        if metrics["speedup"] is None:
            metrics["speedup"] = round(metrics["time_seq"] / metrics["time_par"], 2)
        if metrics["reduction_pct"] is None:
            metrics["reduction_pct"] = round((1 - metrics["time_par"] / metrics["time_seq"]) * 100, 1)

    m_cores = re.search(r'N(?:u|ú)cleos\s+Utilizados[^:\n]*:\s*([0-9]+)', output_text, re.IGNORECASE)
    if not m_cores:
        m_cores = re.search(r'([0-9]+)\s+(?:nucleos|núcleos|threads|cores)', output_text, re.IGNORECASE)
    if m_cores:
        metrics["cores"] = int(m_cores.group(1))

    return metrics


def safe_minipar_name(filename: str | None, default: str = 'ide_temp.minipar') -> str:
    """Nome de arquivo seguro: só o nome base (sem pastas) e com extensão .minipar.

    Impede que '../app.py' (ou caminhos absolutos) leia ou sobrescreva arquivos
    fora de tests/ e temp_code/.
    """
    name = os.path.basename(str(filename or '').replace('\\', '/')).strip()
    name = re.sub(r'[^A-Za-z0-9_.\-]', '_', name)
    if not name or name in ('.', '..'):
        name = default
    if not name.endswith('.minipar'):
        name += '.minipar'
    return name


def find_executable(base_name: str) -> str | None:
    candidate_paths = [
        os.path.join(OUTPUT_DIR, f"{base_name}.exe"),
        os.path.join(OUTPUT_DIR, f"{base_name}"),
        os.path.join(OUTPUT_DIR, base_name),
    ]
    for p in candidate_paths:
        if os.path.isfile(p):
            return p
    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/didatico')
def didatico():
    return render_template('didatico.html')

@app.route('/api/tests', methods=['GET'])
def get_tests():
    # Retorna os testes ordenados alfabeticamente
    tests = [os.path.basename(f) for f in glob.glob(os.path.join(TESTS_DIR, '*.minipar'))]
    return jsonify({"tests": sorted(tests)})

@app.route('/api/get_test', methods=['POST'])
def get_test():
    filename = safe_minipar_name(request.json.get('filename'))
    filepath = os.path.join(TESTS_DIR, filename)
    if os.path.isfile(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify({"code": f.read()})
    return jsonify({"error": "Arquivo não encontrado"}), 404

@app.route('/api/test_spec', methods=['POST'])
def get_test_spec_api():
    """Requisitos detectados automaticamente pelo program_analyzer."""
    filename = request.json.get('filename')
    spec = get_spec_summary(filename)
    if spec:
        return jsonify(spec)
    return jsonify({"requires_input": False, "multi_computer": None})


@app.route('/api/session', methods=['GET'])
def get_session():
    action, session = check_active_session_for_new_terminal()
    if session:
        return jsonify({
            "active": session.get("status") not in ("completed", "cancelled"),
            "session": session,
            "terminal_id": get_terminal_id(),
            "needs_choice": action is not None,
        })
    return jsonify({"active": False, "terminal_id": get_terminal_id()})


@app.route('/api/session/join', methods=['POST'])
def session_join():
    _, session = check_active_session_for_new_terminal()
    if session:
        join_session(session)
        return jsonify({"success": True, "session": session})
    return jsonify({"success": False, "error": "Nenhuma sessão ativa"}), 404


@app.route('/api/session/create', methods=['POST'])
def session_create():
    filename = safe_minipar_name(request.json.get('filename'))
    path = os.path.join(TESTS_DIR, filename)
    if not os.path.isfile(path):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    from program_analyzer import get_program_spec
    spec = get_program_spec(path)
    if not spec.get('multi_computer'):
        return jsonify({"success": False, "error": "Programa não requer multi-terminal"}), 400
    session = create_session(path, spec)
    return jsonify({"success": True, "session": session})


@app.route('/api/session/ready', methods=['POST'])
def session_ready():
    session = _load_session()
    if session:
        session["status"] = "running"
        _save_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@app.route('/api/session/clear', methods=['POST'])
def session_clear():
    clear_session()
    return jsonify({"success": True})


@app.route('/api/inspect', methods=['POST'])
def inspect_code():
    data = request.json or {}
    code = data.get('code', '')
    filename = data.get('filename', 'codigo.minipar')
    
    response = {
        "success": True,
        "filename": filename,
        "phase": "complete",
        "tokens": [],
        "tokens_count": 0,
        "ast": None,
        "symbols": [],
        "semantic_checks": {
            "valid": True,
            "errors": [],
            "pure_blocks": 0,
            "impure_blocks": 0,
            "fork_blocks": 0,
            "join_stmts": 0,
            "classes": 0,
            "functions": 0,
            "symbol_count": 0,
        },
        "tac": "",
        "cpp": "",
        "error": None,
    }

    # 1. Fase Léxica
    try:
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        response["tokens"] = [
            {
                "index": i + 1,
                "type": t.type.name,
                "category": categorize_token(t.type),
                "lexeme": t.lexeme,
                "line": t.line,
                "col": t.col,
            }
            for i, t in enumerate(tokens)
            if t.type != TokenType.END_OF_FILE
        ]
        response["tokens_count"] = len(response["tokens"])
    except Exception as e:
        response["success"] = False
        response["phase"] = "lexer"
        response["error"] = f"Erro Léxico: {str(e)}"
        return jsonify(response)

    # 2. Fase Sintática
    program = None
    try:
        parser = Parser(tokens)
        program = parser.parse()
        response["ast"] = ast_to_dict(program)
    except ParseError as e:
        response["success"] = False
        response["phase"] = "parser"
        response["error"] = f"Erro Sintático: {e.message}"
        return jsonify(response)
    except Exception as e:
        response["success"] = False
        response["phase"] = "parser"
        response["error"] = f"Erro Sintático: {str(e)}"
        return jsonify(response)

    # 3. Fase Semântica
    try:
        semantic = SemanticAnalyzer()
        is_sem_valid = semantic.analyze(program)
        symbols = semantic.get_symbol_table()
        sem_errors = semantic.get_errors()

        pure_count = 0
        impure_count = 0
        fork_count = 0
        join_count = 0
        class_count = 0
        func_count = 0

        def inspect_ast_features(node):
            nonlocal pure_count, impure_count, fork_count, join_count, class_count, func_count
            if node is None:
                return
            ntype = node.__class__.__name__
            if ntype == "PureBlock": pure_count += 1
            elif ntype == "ImpureBlock": impure_count += 1
            elif ntype == "ForkBlock": fork_count += 1
            elif ntype == "JoinStmt": join_count += 1
            elif ntype == "ClassDecl": class_count += 1
            elif ntype == "FuncDecl": func_count += 1

            for _, val in getattr(node, "__dict__", {}).items():
                if isinstance(val, list):
                    for item in val:
                        if hasattr(item, "__dict__"):
                            inspect_ast_features(item)
                elif hasattr(val, "__dict__"):
                    inspect_ast_features(val)

        inspect_ast_features(program)

        response["symbols"] = symbols
        response["semantic_checks"] = {
            "valid": is_sem_valid and len(sem_errors) == 0,
            "errors": sem_errors,
            "pure_blocks": pure_count,
            "impure_blocks": impure_count,
            "fork_blocks": fork_count,
            "join_stmts": join_count,
            "classes": class_count,
            "functions": func_count,
            "symbol_count": len(symbols),
        }
        if not is_sem_valid or sem_errors:
            response["success"] = False
            response["phase"] = "semantic"
            response["error"] = "; ".join(sem_errors) if sem_errors else "Erro na Análise Semântica."
    except Exception as e:
        response["success"] = False
        response["phase"] = "semantic"
        response["error"] = f"Erro Semântico: {str(e)}"
        return jsonify(response)

    # 4. Geração de TAC
    try:
        tac_gen = TACGenerator()
        response["tac"] = tac_gen.generate_text(program)
    except Exception as e:
        response["tac"] = f"# Erro ao gerar TAC: {str(e)}"

    # 5. Geração de C++
    try:
        codegen = CppCodeGenerator()
        response["cpp"] = codegen.generate_cpp_code(program)
    except Exception as e:
        response["cpp"] = f"// Erro ao gerar C++: {str(e)}"

    return jsonify(response)


@app.route('/api/download_exe', methods=['GET', 'POST'])
@app.route('/api/download_exe/<path:filename>', methods=['GET'])
def download_exe(filename=None):
    if not filename:
        if request.is_json and request.json:
            filename = request.json.get('filename')
        else:
            filename = request.args.get('filename')
            
    if not filename:
        filename = 'ide_temp.minipar'
        
    base_name = safe_minipar_name(str(filename).replace('.exe', ''))[:-len('.minipar')]
    exe_path = find_executable(base_name)
    
    # Se ainda não existe, tenta compilar caso o código-fonte exista
    if not exe_path:
        src_path = os.path.join(TESTS_DIR, f"{base_name}.minipar")
        if not os.path.exists(src_path):
            src_path = os.path.join(TEMP_DIR, f"{base_name}.minipar")
            
        if os.path.exists(src_path):
            subprocess.run([sys.executable, 'main.py', src_path, base_name], capture_output=True, text=True, timeout=25)
            exe_path = find_executable(base_name)
            
    if exe_path and os.path.isfile(exe_path):
        download_name = f"{base_name}.exe"
        return send_file(
            os.path.abspath(exe_path),
            as_attachment=True,
            download_name=download_name,
            mimetype="application/octet-stream"
        )
        
    return jsonify({"error": f"Executável para '{base_name}' não encontrado e não pôde ser gerado."}), 404


@app.route('/api/build', methods=['POST'])
def build_code():
    """Compila o código atual do editor (sem executar) — usado pelo botão
    "Baixar .exe" para que o executável baixado corresponda ao que está na tela."""
    data = request.json or {}
    code = data.get('code') or ''
    filename = safe_minipar_name(data.get('filename'))
    base_name = filename[:-len('.minipar')]
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
    try:
        process = subprocess.run([sys.executable, 'main.py', file_path, base_name],
                                 capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "log": "Tempo limite do compilador excedido."}), 500
    log = process.stdout + (("\n" + process.stderr) if process.stderr else "")
    success = process.returncode == 0 and find_executable(base_name) is not None
    return jsonify({
        "success": success,
        "log": log,
        "download_url": f"/api/download_exe/{base_name}" if success else None,
    })


@app.route('/api/compile', methods=['POST'])
def compile_code():
    data = request.json
    code = data.get('code')
    filename = safe_minipar_name(data.get('filename'))
    user_inputs = data.get('inputs', [])
    
    # Salva o código recebido da IDE em um arquivo temporário
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
        
    base_name = filename.replace('.minipar', '')
    stdin_lines = user_inputs  # valores coletados pela IDE para input() no .minipar
    
    try:
        set_session_phase("compiling", "Compilando código MiniPar...", percent=60)
        append_session_log("Compilação iniciada via IDE Web.")
        # ==========================================
        # 1. FASE DE COMPILAÇÃO (Gera TAC e C++)
        # ==========================================
        process = subprocess.run(
            [sys.executable, 'main.py', file_path, base_name], 
            capture_output=True, 
            text=True, 
            timeout=25
        )
        
        # Junta logs do sistema
        full_output = process.stdout
        if process.stderr:
            full_output += "\n" + process.stderr
            
        success = process.returncode == 0
        benchmark_data = {
            "is_benchmark": False,
            "speedup": None,
            "time_seq": None,
            "time_par": None,
            "reduction_pct": None,
            "cores": None,
            "execution_time_total": None
        }

        # ==========================================
        # 2. FASE DE EXECUÇÃO (Roda o Binário C++)
        # ==========================================
        if success:
            set_session_phase("compiling", "Compilação concluída.", percent=80)
            append_session_log("Compilação concluída — executando binário.")
            exe_path = find_executable(base_name)
            
            if exe_path and os.path.exists(exe_path):
                full_output += f"\n--- Executando {base_name} ---\n"
                set_session_phase("executing", f"Executando {base_name}...", percent=90)
                try:
                    # Sem entradas informadas, o programa recebe uma entrada vazia
                    # (input() devolve ""), em vez de herdar o terminal do servidor
                    # e ficar parado esperando digitação até estourar o tempo limite.
                    stdin_data = ""
                    if stdin_lines:
                        stdin_data = "\n".join(stdin_lines) + "\n"
                    
                    t_start = time.perf_counter()
                    exe_proc = subprocess.run(
                        [os.path.abspath(exe_path)], 
                        input=stdin_data,
                        capture_output=True, 
                        text=True, 
                        timeout=35
                    )
                    t_elapsed = time.perf_counter() - t_start
                    full_output += exe_proc.stdout
                    if exe_proc.stderr:
                        full_output += "\n[ERRO NA EXECUÇÃO]:\n" + exe_proc.stderr
                    record_execution_output(exe_proc.stdout or "")
                    
                    benchmark_data = extract_benchmark_metrics(exe_proc.stdout or "")
                    benchmark_data["execution_time_total"] = round(t_elapsed, 4)
                except subprocess.TimeoutExpired:
                    full_output += "\n[ERRO] Tempo limite de execução excedido (O programa entrou em loop infinito ou aguarda entrada de dados do usuário?)."
                    success = False
                except Exception as e:
                    full_output += f"\n[ERRO] Falha ao executar binário: {e}"
                    success = False
                
                full_output += "\n" + "-" * 40

                if filename.endswith('.minipar'):
                    test_source = os.path.join(TESTS_DIR, filename)
                    if os.path.exists(test_source):
                        finalize_test_execution(test_source, full_output)
        
        # ==========================================
        # 3. COLETA DOS ARQUIVOS GERADOS
        # ==========================================
        cpp_file = os.path.join(OUTPUT_DIR, f"{base_name}.cpp")
        tac_file = os.path.join(OUTPUT_DIR, f"{base_name}.tac")
        
        cpp_code = ""
        tac_code = ""
        
        if os.path.exists(cpp_file):
            with open(cpp_file, 'r', encoding='utf-8') as f:
                cpp_code = f.read()
                
        if os.path.exists(tac_file):
             with open(tac_file, 'r', encoding='utf-8') as f:
                tac_code = f.read()
                
        # Retorna o resultado. Se der erro, colocamos o log completo em stderr para o JS puxar
        return jsonify({
            "stdout": full_output if success else "",
            "stderr": full_output if not success else "",
            "cpp": cpp_code,
            "tac": tac_code,
            "success": success,
            "benchmark": benchmark_data
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Tempo limite do compilador excedido.", "success": False}), 500
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

if __name__ == '__main__':
    # Roda a IDE silenciosamente
    app.run(debug=False, port=5000)