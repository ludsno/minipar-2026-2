"""
Runtime C++ do MiniPar 2026.2.

`_CPP_HEADER` é inserido no início de todo arquivo .cpp gerado pelo componente
de geração de código (C_CodeGen). Ele contém as funções de apoio que o código
traduzido usa:

- E/S (`input`, `__minipar_print`), coleções (`__minipar_range`, `__make_matrix`, ...);
- SPar `pure`/`impure`: `__minipar_pure_map` (padrão Map / parallel for) e o mutex
  `__minipar_impure_mtx`;
- `fork`/`join`: pool `__active_fork_threads`, alocação de subtarefa em um núcleo da
  CPU (`__minipar_fixar_nucleo`) ou em outro computador (`__minipar_executar_remoto`
  e `__minipar_servir_tarefas`);
- canais de comunicação `c_channel` (classe `MiniParChannel`, via sockets TCP).

A string é "raw" (r"..."): o conteúdo é C++ puro, sem escapes de Python.
"""

_CPP_HEADER = r"""// ===== Runtime MiniPar 2026.2 (gerado automaticamente pelo compilador) =====
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <thread>
#include <mutex>
#include <memory>
#include <cstring>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <type_traits>
#include <atomic>
#include <algorithm>
#include <set>
#include <utility>

#ifdef _WIN32
  #ifndef NOMINMAX
    #define NOMINMAX
  #endif
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #include <windows.h>
  #pragma comment(lib, "ws2_32.lib")
  #define CLOSE_SOCK closesocket
  typedef SOCKET __minipar_sock_t;
  #define MINIPAR_SOCK_INVALIDO INVALID_SOCKET
#else
  #include <sys/socket.h>
  #include <sys/select.h>
  #include <sys/wait.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #include <spawn.h>
  #include <pthread.h>
  #include <sched.h>
  extern char **environ;
  #define CLOSE_SOCK close
  typedef int __minipar_sock_t;
  #define MINIPAR_SOCK_INVALIDO (-1)
#endif

// Mutex para regioes impuras (SPar Impure Protection)
static std::mutex __minipar_impure_mtx;
// Pool de threads ativas disparadas por Fork
static std::vector<std::thread> __active_fork_threads;

// Helper para Random nativo
double random_val() { return (double)rand() / RAND_MAX; }

// Temporizador nativo de alta precisao para benchmarks MiniPar (segundos)
double obter_tempo() {
    using namespace std::chrono;
    return duration_cast<duration<double>>(high_resolution_clock::now().time_since_epoch()).count();
}

// Simulador de carga de trabalho: espera ativa de N milissegundos (pelo relogio)
void simular_trabalho(double milissegundos) {
    auto inicio = std::chrono::high_resolution_clock::now();
    while (true) {
        auto agora = std::chrono::high_resolution_clock::now();
        double decorrido = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(agora - inicio).count();
        if (decorrido >= milissegundos) break;
    }
}

// Helper para Input
std::string input() {
    std::string s;
    std::getline(std::cin, s);
    return s;
}

std::string input(const std::string& prompt) {
    std::cout << prompt << std::flush;  // mostra a pergunta antes de ler (mesmo sem terminal)
    return input();
}

// to_number(texto): converte texto em numero. Texto invalido (ex.: vazio ou
// "abc") nao derruba o programa: mostra um aviso e usa 0 (tratamento de erro).
double __minipar_to_number(const std::string& texto) {
    try {
        return std::stod(texto);
    } catch (...) {
        std::cerr << "[ERRO] to_number: \"" << texto << "\" nao e um numero valido; usando 0." << std::endl;
        return 0.0;
    }
}

// Converte linha com inteiros separados por espaco em vetor (ex.: "10 -3 80")
std::vector<double> __parse_ints(const std::string& s) {
    std::vector<double> result;
    std::istringstream iss(s);
    double n;
    while (iss >> n) {
        result.push_back(n);
    }
    return result;
}

std::vector<int> __minipar_range(int end) {
    std::vector<int> values;
    for (int i = 0; i < end; ++i) values.push_back(i);
    return values;
}

std::vector<int> __minipar_range(int start, int end) {
    std::vector<int> values;
    for (int i = start; i < end; ++i) values.push_back(i);
    return values;
}

// Helper para Arrays (.pop) do Python
template<typename T>
auto __array_pop(std::vector<T>& v) {
    if (v.empty()) return T{};
    auto val = v.back();
    v.pop_back();
    return val;
}

// Helper para formatar e printar std::vector (arrays e matrizes) nativamente
template <typename T>
std::ostream& operator<<(std::ostream& os, const std::vector<T>& v) {
    os << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        os << v[i];
        if (i != v.size() - 1) os << ", ";
    }
    os << "]";
    return os;
}

// print() atomico: monta a linha inteira e escreve com uma unica operacao,
// para que threads (par, fork, pure) nao misturem pedacos de linhas no console.
template <typename... Args>
void __minipar_print(const Args&... args) {
    std::ostringstream linha;
    bool primeiro = true;
    ((linha << (primeiro ? "" : " ") << args, primeiro = false), ...);
    linha << '\n';
    std::cout << linha.str() << std::flush;
}

// ---------------------------------------------------------------------------
// SPar Pure (padrao Map / parallel for)
// ---------------------------------------------------------------------------
// Nucleos que a thread atual pode usar. Respeita a alocacao: dentro de um
// 'fork @nucleo(n)' a thread esta fixada em 1 nucleo, entao o 'pure' interno nao
// cria threads extras que ficariam disputando o mesmo nucleo.
unsigned __minipar_nucleos_disponiveis() {
#if defined(__linux__)
    cpu_set_t conjunto;
    if (pthread_getaffinity_np(pthread_self(), sizeof(conjunto), &conjunto) == 0) {
        int n = CPU_COUNT(&conjunto);
        if (n > 0) return static_cast<unsigned>(n);
    }
#endif
    return std::thread::hardware_concurrency();
}

// Numero de threads de um laco 'pure': um por nucleo disponivel, limitado ao
// numero de iteracoes. Pode ser fixado pela variavel de ambiente
// MINIPAR_PURE_THREADS (ex.: MINIPAR_PURE_THREADS=1 executa o laco sequencialmente).
unsigned __minipar_pure_threads(long long iteracoes) {
    if (iteracoes <= 0) return 0;
    unsigned n = __minipar_nucleos_disponiveis();
    if (const char* env = std::getenv("MINIPAR_PURE_THREADS")) {
        int v = std::atoi(env);
        if (v > 0) n = static_cast<unsigned>(v);
    }
    if (n == 0) n = 1;
    if (static_cast<long long>(n) > iteracoes) n = static_cast<unsigned>(iteracoes);
    return n;
}

// Quantidade de iteracoes de um laco canonico com passo positivo:
// for (v = ini; v < lim; v = v + passo)  ou  v <= lim (inclusivo).
long long __minipar_pure_count(double ini, double lim, double passo, bool inclusivo) {
    double dist = lim - ini;
    if (dist < 0 || (dist == 0 && !inclusivo)) return 0;
    long long n = static_cast<long long>(std::floor(dist / passo));
    if (inclusivo) return n + 1;
    return (std::fmod(dist, passo) == 0) ? n : n + 1;
}

// Distribui as iteracoes [0, total) entre as threads e espera todas terminarem
// (barreira implicita no fim do laco 'pure'). Escalonamento dinamico: cada
// thread pega o proximo bloco livre de iteracoes, o que equilibra a carga
// quando algumas iteracoes sao mais pesadas que outras (ex.: Mandelbrot).
template <typename F>
void __minipar_pure_map(long long total, F bloco) {
    unsigned n = __minipar_pure_threads(total);
    if (n <= 1) {
        if (total > 0) bloco(0LL, total);
        return;
    }
    const long long tam_bloco = std::max(1LL, total / (static_cast<long long>(n) * 8));
    std::atomic<long long> proximo{0};
    auto trabalhador = [&]() {
        while (true) {
            long long ini = proximo.fetch_add(tam_bloco);
            if (ini >= total) break;
            bloco(ini, std::min(total, ini + tam_bloco));
        }
    };
    std::vector<std::thread> pool;
    pool.reserve(n);
    for (unsigned w = 0; w < n; ++w) pool.emplace_back(trabalhador);
    for (auto& t : pool) t.join();
}

// Converte um valor em texto para envio por c_channel (send). Numeros saem na
// forma curta: 42, 2.5, 479001600 (sem os zeros de std::to_string).
template<typename T>
std::string __to_string(const T& val) {
    if constexpr (std::is_constructible_v<std::string, T>) {
        return std::string(val);
    } else {
        std::ostringstream texto;
        texto.precision(15);
        texto << val;
        return texto.str();
    }
}

template<typename T>
auto __make_matrix(int rows, int cols, T init_val) {
    using ActualT = std::conditional_t<std::is_same_v<std::decay_t<T>, const char*>, std::string, T>;
    return std::vector<std::vector<ActualT>>(rows, std::vector<ActualT>(cols, init_val));
}

// ---------------------------------------------------------------------------
// Sockets TCP (base dos canais c_channel e do fork @computador)
// ---------------------------------------------------------------------------
// Conecta em ip:porta usando um socket novo a cada tentativa (um socket que
// falhou no connect() nao deve ser reutilizado). Retorna o socket ou invalido.
__minipar_sock_t __minipar_conectar(std::string ip, int porta, int tentativas, int espera_ms = 100) {
    if (ip == "localhost") ip = "127.0.0.1";
    sockaddr_in endereco{};
    endereco.sin_family = AF_INET;
    endereco.sin_port = htons(static_cast<unsigned short>(porta));
    inet_pton(AF_INET, ip.c_str(), &endereco.sin_addr);
    for (int i = 0; i < tentativas; ++i) {
        __minipar_sock_t s = socket(AF_INET, SOCK_STREAM, 0);
        if (s == MINIPAR_SOCK_INVALIDO) return MINIPAR_SOCK_INVALIDO;
        if (connect(s, (sockaddr*)&endereco, sizeof(endereco)) == 0) return s;
        CLOSE_SOCK(s);
        std::this_thread::sleep_for(std::chrono::milliseconds(espera_ms));
    }
    return MINIPAR_SOCK_INVALIDO;
}

// Cria um socket de escuta em todas as interfaces na porta indicada.
__minipar_sock_t __minipar_escutar(int porta) {
    for (int tentativa = 0; tentativa < 20; ++tentativa) {
        __minipar_sock_t s = socket(AF_INET, SOCK_STREAM, 0);
        if (s == MINIPAR_SOCK_INVALIDO) return MINIPAR_SOCK_INVALIDO;
        int opt = 1;
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
        sockaddr_in endereco{};
        endereco.sin_family = AF_INET;
        endereco.sin_addr.s_addr = INADDR_ANY;
        endereco.sin_port = htons(static_cast<unsigned short>(porta));
        if (bind(s, (sockaddr*)&endereco, sizeof(endereco)) == 0 && listen(s, 64) == 0) return s;
        CLOSE_SOCK(s);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));  // porta ainda ocupada
    }
    return MINIPAR_SOCK_INVALIDO;
}

void __minipar_enviar_tudo(__minipar_sock_t s, const std::string& msg) {
    size_t enviado = 0;
    while (enviado < msg.size()) {
        int n = send(s, msg.data() + enviado, static_cast<int>(msg.size() - enviado), 0);
        if (n <= 0) return;
        enviado += static_cast<size_t>(n);
    }
}

// Le ate o outro lado fechar a conexao (uma mensagem por conexao).
std::string __minipar_receber_tudo(__minipar_sock_t s) {
    std::string resultado;
    char buffer[4096];
    while (true) {
        int n = recv(s, buffer, sizeof(buffer), 0);
        if (n <= 0) break;
        resultado.append(buffer, static_cast<size_t>(n));
    }
    return resultado;
}

// Le uma linha (ate '\n') — usado nos pedidos do protocolo de subtarefas remotas.
std::string __minipar_receber_linha(__minipar_sock_t s) {
    std::string linha;
    char c;
    while (recv(s, &c, 1, 0) == 1 && c != '\n') linha.push_back(c);
    return linha;
}

// Canal de comunicacao c_channel(ip, porta): send() envia uma mensagem para
// ip:porta e receive() recebe uma mensagem que chegou na porta.
class MiniParChannel {
public:
    std::string ip;
    int port;

    MiniParChannel(std::string ip, int port) : ip(ip), port(port) {}
    ~MiniParChannel() {
        if (servidor != MINIPAR_SOCK_INVALIDO) CLOSE_SOCK(servidor);
    }

    // Abre uma conexao nova, envia a mensagem e fecha. Tenta por ate ~30 s, para
    // dar tempo do receptor (outra thread, processo ou computador) comecar a escutar.
    void sendData(std::string msg) {
        __minipar_sock_t s = __minipar_conectar(ip, port, 300);
        if (s == MINIPAR_SOCK_INVALIDO) {
            std::cerr << "[c_channel] nao foi possivel conectar em " << ip << ":" << port << std::endl;
            return;
        }
        __minipar_enviar_tudo(s, msg);
        CLOSE_SOCK(s);
    }

    // O socket de escuta e criado no primeiro receive() e fica aberto ate o fim do
    // canal: conexoes que chegam entre dois receive() esperam na fila do sistema
    // operacional e nenhuma mensagem se perde.
    std::string receiveData() {
        __minipar_sock_t srv;
        {
            std::lock_guard<std::mutex> trava(mtx);
            if (servidor == MINIPAR_SOCK_INVALIDO) servidor = __minipar_escutar(port);
            srv = servidor;
        }
        if (srv == MINIPAR_SOCK_INVALIDO) return "";
        __minipar_sock_t cliente = accept(srv, nullptr, nullptr);
        if (cliente == MINIPAR_SOCK_INVALIDO) return "";
        std::string mensagem = __minipar_receber_tudo(cliente);
        CLOSE_SOCK(cliente);
        return mensagem;
    }

private:
    __minipar_sock_t servidor = MINIPAR_SOCK_INVALIDO;
    std::mutex mtx;
};

// ---------------------------------------------------------------------------
// Fork com alocacao: @nucleo(n) e @computador(ip, porta)
// ---------------------------------------------------------------------------
// Fixa a thread atual em um nucleo da CPU (subtarefa alocada via fork @nucleo(n)).
void __minipar_fixar_nucleo(long long nucleo) {
    unsigned total = std::thread::hardware_concurrency();
    if (total == 0) return;
    unsigned alvo = static_cast<unsigned>(((nucleo % total) + total) % total);
#if defined(_WIN32)
    SetThreadAffinityMask(GetCurrentThread(), static_cast<DWORD_PTR>(1) << alvo);
#elif defined(__linux__)
    cpu_set_t conjunto;
    CPU_ZERO(&conjunto);
    CPU_SET(alvo, &conjunto);
    pthread_setaffinity_np(pthread_self(), sizeof(conjunto), &conjunto);
#endif
}

// Nucleo da CPU em que a thread atual esta executando (-1 se indisponivel).
int nucleo_atual() {
#if defined(_WIN32)
    return static_cast<int>(GetCurrentProcessorNumber());
#elif defined(__linux__)
    return sched_getcpu();
#else
    return -1;
#endif
}

// Estado do protocolo de subtarefas remotas.
// Cada computador executa o MESMO programa: o computador principal roda o
// programa normalmente; um "computador trabalhador" e o mesmo executavel
// iniciado com a variavel de ambiente MINIPAR_TRABALHADOR=<porta>. Ele so
// executa as subtarefas (fork @computador) que recebe pela rede. Nao ha memoria
// compartilhada: os dados vao e voltam por mensagens (c_channel).
static std::mutex __minipar_remoto_mtx;
static std::set<std::pair<std::string, int>> __minipar_computadores_usados;
static std::set<int> __minipar_trabalhadores_locais;
#ifdef _WIN32
static std::vector<HANDLE> __minipar_processos_filhos;
#else
static std::vector<pid_t> __minipar_processos_filhos;
#endif
static std::string __minipar_caminho_exe;
static int __minipar_porta_trabalhador = 0;
static long __minipar_pid_pai = 0;   // > 0: trabalhador iniciado automaticamente por este processo

// Chamado no inicio do main(): descobre o caminho do proprio executavel e se este
// processo e um computador trabalhador.
void __minipar_iniciar(int argc, char** argv) {
    if (argc > 0 && argv && argv[0]) __minipar_caminho_exe = argv[0];
#if defined(__linux__)
    char caminho[4096];
    ssize_t n = readlink("/proc/self/exe", caminho, sizeof(caminho) - 1);
    if (n > 0) { caminho[n] = '\0'; __minipar_caminho_exe = caminho; }
#elif defined(_WIN32)
    char caminho[MAX_PATH];
    DWORD n = GetModuleFileNameA(NULL, caminho, MAX_PATH);
    if (n > 0) __minipar_caminho_exe = std::string(caminho, n);
#endif
    if (const char* p = std::getenv("MINIPAR_TRABALHADOR")) __minipar_porta_trabalhador = std::atoi(p);
    if (const char* p = std::getenv("MINIPAR_PAI")) __minipar_pid_pai = std::atol(p);
}

bool __minipar_modo_trabalhador() { return __minipar_porta_trabalhador > 0; }

bool __minipar_ip_local(const std::string& ip) {
    return ip == "127.0.0.1" || ip == "localhost" || ip == "0.0.0.0";
}

// Inicia neste computador um processo trabalhador para a porta (simula outro
// computador via localhost). Deve ser chamado com __minipar_remoto_mtx travado.
void __minipar_iniciar_trabalhador_local(int porta) {
    if (__minipar_trabalhadores_locais.count(porta)) return;
    __minipar_trabalhadores_locais.insert(porta);
    std::string valor = std::to_string(porta);
#ifdef _WIN32
    SetEnvironmentVariableA("MINIPAR_TRABALHADOR", valor.c_str());
    SetEnvironmentVariableA("MINIPAR_PAI", std::to_string(GetCurrentProcessId()).c_str());
    STARTUPINFOA si{};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    std::string comando = "\"" + __minipar_caminho_exe + "\"";
    std::vector<char> linha(comando.begin(), comando.end());
    linha.push_back('\0');
    if (CreateProcessA(NULL, linha.data(), NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) {
        CloseHandle(pi.hThread);
        __minipar_processos_filhos.push_back(pi.hProcess);
    }
    SetEnvironmentVariableA("MINIPAR_TRABALHADOR", NULL);
    SetEnvironmentVariableA("MINIPAR_PAI", NULL);
#else
    std::string variavel = "MINIPAR_TRABALHADOR=" + valor;
    std::vector<char*> ambiente;
    for (char** e = environ; e && *e; ++e)
        if (std::strncmp(*e, "MINIPAR_TRABALHADOR=", 20) != 0 && std::strncmp(*e, "MINIPAR_PAI=", 12) != 0)
            ambiente.push_back(*e);
    std::string variavel_pai = "MINIPAR_PAI=" + std::to_string(static_cast<long>(getpid()));
    ambiente.push_back(const_cast<char*>(variavel.c_str()));
    ambiente.push_back(const_cast<char*>(variavel_pai.c_str()));
    ambiente.push_back(nullptr);
    char* argumentos[] = { const_cast<char*>(__minipar_caminho_exe.c_str()), nullptr };
    pid_t pid;
    if (posix_spawn(&pid, __minipar_caminho_exe.c_str(), nullptr, nullptr, argumentos, ambiente.data()) == 0)
        __minipar_processos_filhos.push_back(pid);
#endif
}

// Lado do computador principal: envia a subtarefa ao computador ip:porta e
// espera ela terminar (a thread do fork fica bloqueada aqui ate o join).
void __minipar_executar_remoto(const std::string& tarefa, const std::string& nome, std::string ip, int porta) {
    if (ip == "localhost") ip = "127.0.0.1";
    const std::string destino = ip + ":" + std::to_string(porta);
    {
        std::lock_guard<std::mutex> trava(__minipar_remoto_mtx);
        __minipar_computadores_usados.insert({ip, porta});
    }
    __minipar_sock_t s = __minipar_conectar(ip, porta, 10);
    if (s == MINIPAR_SOCK_INVALIDO) {
        if (__minipar_ip_local(ip)) {
            // Sem computador extra: a subtarefa roda neste computador, em outro processo
            __minipar_print("[fork " + nome + "] Nenhum computador extra aberto em " + destino +
                            " -> a subtarefa vai rodar NESTE computador, em um processo separado.");
            std::lock_guard<std::mutex> trava(__minipar_remoto_mtx);
            __minipar_iniciar_trabalhador_local(porta);
        } else {
            std::string programa = __minipar_caminho_exe.substr(__minipar_caminho_exe.find_last_of("/\\") + 1);
            __minipar_print("[fork " + nome + "] Aguardando o computador " + destino + " (ate 30 s). Nele deve estar aberto: MINIPAR_TRABALHADOR=" +
                            std::to_string(porta) + " " + programa);
        }
        s = __minipar_conectar(ip, porta, 300);  // espera o computador ficar pronto (~30 s)
    }
    if (s == MINIPAR_SOCK_INVALIDO) {
        __minipar_print("[fork " + nome + "] ERRO: o computador " + destino + " nao respondeu (trabalhador fechado, IP errado ou firewall). "
                        "Feche com Ctrl+C, abra o trabalhador nesse computador e execute de novo.");
        return;
    }
    __minipar_print("[fork " + nome + "] subtarefa enviada ao computador " + destino);
    __minipar_enviar_tudo(s, "EXEC " + tarefa + "\n");
    std::string resposta = __minipar_receber_tudo(s);  // bloqueia ate a subtarefa terminar
    CLOSE_SOCK(s);
    if (resposta.rfind("FIM", 0) == 0)
        __minipar_print("[fork " + nome + "] subtarefa concluida no computador " + destino);
    else
        __minipar_print("[fork " + nome + "] ERRO: o computador " + destino + " nao executou a subtarefa.");
}

// Lado do computador trabalhador: escuta a porta, executa cada subtarefa pedida
// (em paralelo, uma thread por pedido) e responde "FIM" quando ela termina.
// Encerra ao receber "SAIR" ou apos 120 s sem pedidos.
template <typename F>
void __minipar_servir_tarefas(F executar) {
    const int porta = __minipar_porta_trabalhador;
    __minipar_sock_t srv = __minipar_escutar(porta);
    if (srv == MINIPAR_SOCK_INVALIDO) {
        std::cerr << "[computador :" << porta << "] nao foi possivel escutar a porta." << std::endl;
        return;
    }
    __minipar_print("[computador :" + std::to_string(porta) + "] trabalhador pronto, aguardando subtarefas...");
    std::vector<std::thread> em_execucao;
#ifdef _WIN32
    HANDLE processo_pai = __minipar_pid_pai > 0 ? OpenProcess(SYNCHRONIZE, FALSE, static_cast<DWORD>(__minipar_pid_pai)) : NULL;
#endif
    bool encerrado_pelo_principal = false;
    int segundos_ocioso = 0;
    while (true) {
        // Trabalhador iniciado automaticamente: se o programa principal morreu
        // (ex.: tempo limite da interface web), este processo tambem termina,
        // em vez de ficar preso ocupando a porta.
#ifdef _WIN32
        if (processo_pai && WaitForSingleObject(processo_pai, 0) == WAIT_OBJECT_0) break;
#else
        if (__minipar_pid_pai > 0 && getppid() != __minipar_pid_pai) break;
#endif
        fd_set conjunto;
        FD_ZERO(&conjunto);
        FD_SET(srv, &conjunto);
        timeval limite{1, 0};
        int pronto = select(static_cast<int>(srv) + 1, &conjunto, nullptr, nullptr, &limite);
        if (pronto < 0) break;
        if (pronto == 0) {
            if (++segundos_ocioso >= 120) break;   // 2 minutos sem pedidos
            continue;
        }
        segundos_ocioso = 0;
        __minipar_sock_t cliente = accept(srv, nullptr, nullptr);
        if (cliente == MINIPAR_SOCK_INVALIDO) continue;
        std::string pedido = __minipar_receber_linha(cliente);
        if (pedido == "SAIR") { CLOSE_SOCK(cliente); encerrado_pelo_principal = true; break; }
        if (pedido.rfind("EXEC ", 0) != 0) { CLOSE_SOCK(cliente); continue; }
        std::string tarefa = pedido.substr(5);
        em_execucao.emplace_back([cliente, tarefa, porta, &executar]() {
            std::string nome = tarefa.substr(0, tarefa.find('#'));
            __minipar_print("[computador :" + std::to_string(porta) + "] executando subtarefa " + nome);
            bool conhecida = executar(tarefa);
            __minipar_enviar_tudo(cliente, conhecida ? "FIM\n" : "DESCONHECIDA\n");
            CLOSE_SOCK(cliente);
        });
    }
    CLOSE_SOCK(srv);
    if (!encerrado_pelo_principal) {
        // Principal morreu ou ficou 2 min sem pedidos: sai sem esperar subtarefas
        // que possam estar bloqueadas esperando mensagens que nunca virao.
        std::cout << std::flush;
        std::_Exit(0);
    }
    for (auto& t : em_execucao) t.join();
}

// Chamado no fim do main(): barreira final para forks sem join, aviso de
// encerramento aos computadores trabalhadores e espera dos processos locais.
void __minipar_finalizar() {
    for (auto& t : __active_fork_threads)
        if (t.joinable()) t.join();
    __active_fork_threads.clear();

    std::set<std::pair<std::string, int>> usados;
    {
        std::lock_guard<std::mutex> trava(__minipar_remoto_mtx);
        usados = __minipar_computadores_usados;
    }
    for (const auto& destino : usados) {
        __minipar_sock_t s = __minipar_conectar(destino.first, destino.second, 3);
        if (s == MINIPAR_SOCK_INVALIDO) continue;
        __minipar_enviar_tudo(s, "SAIR\n");
        CLOSE_SOCK(s);
    }
#ifdef _WIN32
    for (HANDLE h : __minipar_processos_filhos) { WaitForSingleObject(h, 10000); CloseHandle(h); }
#else
    for (pid_t pid : __minipar_processos_filhos) { int estado; waitpid(pid, &estado, 0); }
#endif
}

"""
