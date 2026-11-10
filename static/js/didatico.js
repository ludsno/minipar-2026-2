/**
 * MiniPar 2026.2 — Script da Interface Web Didática (Estilo IFSC)
 * Suporte a D3.js v7, Visualização Gráfica de AST, Tokens, Semântico, TAC e Speedup
 */

document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // 1. Elementos da Interface
    // ==========================================
    const selectTest = document.getElementById('select-test');
    const btnInspect = document.getElementById('btn-inspect');
    const btnRun = document.getElementById('btn-run');
    const btnDownload = document.getElementById('btn-download');
    const btnClear = document.getElementById('btn-clear');
    const editorMiniparEl = document.getElementById('editor-minipar');
    const editorFilename = document.getElementById('editor-filename');
    const editorLinesCount = document.getElementById('editor-lines-count');
    const terminalOutput = document.getElementById('terminal-output');
    const btnClearTerminal = document.getElementById('btn-clear-terminal');
    const executionTimeBadge = document.getElementById('execution-time-badge');
    const statusPill = document.getElementById('status-pill');
    const statusLabel = document.getElementById('status-label');
    const inputContainer = document.getElementById('input-container');
    const userInputsEl = document.getElementById('user-inputs');

    // Alternância de Tema (Claro / Escuro)
    const btnThemeToggle = document.getElementById('btn-theme-toggle');
    const themeToggleIcon = document.getElementById('theme-toggle-icon');
    const themeToggleLabel = document.getElementById('theme-toggle-label');

    // Abas
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Badges de Contagem
    const badgeTokensCount = document.getElementById('badge-tokens-count');
    const badgeAstNodes = document.getElementById('badge-ast-nodes');
    const badgeSymbolsCount = document.getElementById('badge-symbols-count');

    // Tokens
    const filterTokenCategory = document.getElementById('filter-token-category');
    const tokensSearch = document.getElementById('tokens-search');
    const tokensTbody = document.getElementById('tokens-tbody');
    const tokensCountLabel = document.getElementById('tokens-count-label');

    // Semântico
    const symbolsTbody = document.getElementById('symbols-tbody');
    const symbolsCountLabel = document.getElementById('symbols-count-label');
    const semanticBadge = document.getElementById('semantic-badge');
    const semanticErrorsList = document.getElementById('semantic-errors-list');

    // TAC & C++
    const tacCodeContent = document.getElementById('tac-code-content');
    const cppCodeContent = document.getElementById('cpp-code-content');
    const btnCopyTac = document.getElementById('btn-copy-tac');
    const btnCopyCpp = document.getElementById('btn-copy-cpp');

    // Benchmarks
    const kpiSpeedup = document.getElementById('kpi-speedup');
    const kpiTimeSeq = document.getElementById('kpi-time-seq');
    const kpiTimePar = document.getElementById('kpi-time-par');
    const kpiReduction = document.getElementById('kpi-reduction');

    // AST Controls
    const astSvg = d3.select('#ast-svg');
    const astTooltip = document.getElementById('ast-tooltip');
    const astEmptyMessage = document.getElementById('ast-empty-message');
    const btnAstZoomIn = document.getElementById('btn-ast-zoom-in');
    const btnAstZoomOut = document.getElementById('btn-ast-zoom-out');
    const btnAstReset = document.getElementById('btn-ast-reset');
    const btnAstToggleCollapse = document.getElementById('btn-ast-toggle-collapse');
    const astSearchInput = document.getElementById('ast-search-input');

    // ==========================================
    // 2. Estado Global do Frontend
    // ==========================================
    let currentTokens = [];
    let currentAstData = null;
    let d3Root = null;
    let d3Zoom = null;
    let d3SvgGroup = null;
    let allNodesCollapsed = false;

    // ==========================================
    // 3. Inicialização do CodeMirror
    // ==========================================
    const editor = CodeMirror.fromTextArea(editorMiniparEl, {
        lineNumbers: true,
        mode: 'text/x-csrc',
        theme: 'neo',
        matchBrackets: true,
        autoCloseBrackets: true,
        tabSize: 4,
        indentUnit: 4,
        lineWrapping: false
    });

    const updateLineCount = () => {
        const lines = editor.lineCount();
        editorLinesCount.textContent = `${lines} ${lines === 1 ? 'linha' : 'linhas'}`;
    };

    editor.on('change', updateLineCount);

    // ==========================================
    // 3.1 Gerenciamento de Tema (Claro / Escuro)
    // ==========================================
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('minipar_theme', theme);

        if (theme === 'dark') {
            if (themeToggleIcon) themeToggleIcon.className = 'fa-solid fa-sun';
            if (themeToggleLabel) themeToggleLabel.textContent = 'Tema Claro';
            editor.setOption('theme', 'dracula');
        } else {
            if (themeToggleIcon) themeToggleIcon.className = 'fa-solid fa-moon';
            if (themeToggleLabel) themeToggleLabel.textContent = 'Tema Escuro';
            editor.setOption('theme', 'neo');
        }
    }

    if (btnThemeToggle) {
        btnThemeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    }

    // Inicializa o tema com base na preferência salva (padrão 'light' para estilo IFSC)
    const savedTheme = localStorage.getItem('minipar_theme') || 'light';
    applyTheme(savedTheme);

    // Código inicial padrão (Demonstração didática das novidades)
    const DEFAULT_CODE = `# MiniPar 2026.2 — Exemplo Didático das Novas Primitivas
# Demonstrando Paralelismo de Dados SPar (Pure/Impure) e Tarefas (Fork/Join)

var total_geral = 0;

# 1. Região Pura SPar com Proteção por Lock na Região Impura
pure for (var i = 0; i < 20; i = i + 1) {
    var calculo_parcial = i * 5;
    impure {
        total_geral = total_geral + calculo_parcial;
    }
}

print("Resultado apos processamento Pure/Impure: ", total_geral);

# 2. Concorrência com Fork e Barreira Join
fork tarefa_worker_1 {
    print("Worker 1 executando em paralelo...");
}

fork tarefa_worker_2 {
    print("Worker 2 executando em paralelo...");
}

join;
print("Todas as tarefas filhas foram sincronizadas!");
`;

    editor.setValue(DEFAULT_CODE);
    updateLineCount();

    // ==========================================
    // 4. Carregamento dos Programas de Teste
    // ==========================================
    const TEST_LABELS = {
        'teste_sanidade_fase1.minipar': '⭐ Teste de Sanidade (Pure, Impure, Fork, Join)',
        'teste1_calculadora_cliente_servidor.minipar': 'Teste 1: Calculadora Cliente/Servidor (Sockets)',
        'teste2_fatorial_fibonacci_par.minipar': 'Teste 2: Fatorial e Fibonacci Concorrentes (Par)',
        'teste3_neuronio.minipar': 'Teste 3: Neurônio Artificial (Classes e Métodos)',
        'teste4_rede_neural_xor.minipar': 'Teste 4: Rede Neural XOR (MLP Backpropagation)',
        'teste5_recomendacao.minipar': 'Teste 5: Recomendação de E-commerce (POO)',
        'teste6_quicksort_classes.minipar': 'Teste 6: Quicksort com Classes',
        'teste7_quicksort_iterativo_tac.minipar': 'Teste 7: Quicksort Iterativo (TAC)',
        'teste8_avaliacao_4nucleos.minipar': '🚀 Teste 8: Avaliação Paralela em 4 Núcleos (Fork/Join)',
        'teste9_mandelbrot_5nucleos.minipar': '🚀 Teste 9: Mandelbrot em 5 Núcleos (Pure/Impure SPar)',
        'teste10_6nucleos_2fractais.minipar': '🚀 Teste 10: Mandelbrot + Sierpinski em 6 Núcleos',
        'teste_adicional1_paralelismo_3_computadores.minipar': 'Extra: Paralelismo em 3 Máquinas',
        'teste_adicional2_tapete_sierpinski.minipar': 'Extra: Tapete de Sierpinski',
        'teste_ascii_art_divertidapkrl.minipar': 'Extra: Arte ASCII',
        'teste_bnf_controles_input.minipar': 'Extra: Controles e Input'
    };

    function loadTestList() {
        fetch('/api/tests')
            .then(res => res.json())
            .then(data => {
                selectTest.innerHTML = '<option value="" disabled selected>-- Selecione um programa de teste --</option>';
                
                // Opção padrão
                const optDefault = document.createElement('option');
                optDefault.value = '__default__';
                optDefault.textContent = '💡 Exemplo Didático Rápido (Pure / Impure & Fork / Join)';
                selectTest.appendChild(optDefault);

                (data.tests || []).forEach(filename => {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = TEST_LABELS[filename] || filename;
                    selectTest.appendChild(opt);
                });
            })
            .catch(err => {
                console.error('Erro ao carregar lista de testes:', err);
                selectTest.innerHTML = '<option value="">Falha ao listar testes</option>';
            });
    }

    selectTest.addEventListener('change', () => {
        const val = selectTest.value;
        if (!val) return;

        if (val === '__default__') {
            editor.setValue(DEFAULT_CODE);
            editorFilename.textContent = 'exemplo_didatico.minipar';
            setStatus('ready', 'Exemplo didático carregado');
            return;
        }

        setStatus('working', `Carregando ${val}...`);
        fetch('/api/get_test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: val })
        })
        .then(res => res.json())
        .then(data => {
            if (data.code) {
                editor.setValue(data.code);
                editorFilename.textContent = val;
                setStatus('ready', `${val} pronto`);
                
                // Verifica requisitos de input
                fetch('/api/test_spec', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: val })
                })
                .then(r => r.json())
                .then(spec => {
                    if (spec.requires_input) {
                        inputContainer.style.display = 'flex';
                    } else {
                        inputContainer.style.display = 'none';
                    }
                })
                .catch(() => {});
            }
        })
        .catch(err => {
            setStatus('error', 'Falha ao carregar arquivo');
            console.error(err);
        });
    });

    loadTestList();

    // ==========================================
    // 5. Navegação das Abas
    // ==========================================
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add('active');
                if (targetId === 'tab-ast' && d3Root) {
                    // Força ajuste de layout da AST ao alternar para a aba
                    setTimeout(() => fitAstToView(), 50);
                }
            }
        });
    });

    // ==========================================
    // 6. Funções de Status e Feedback
    // ==========================================
    function setStatus(state, message) {
        statusPill.className = `status-indicator ${state}`;
        const dot = statusPill.querySelector('.status-dot');
        dot.className = `status-dot ${state}`;
        statusLabel.textContent = message;
    }

    // ==========================================
    // 7. Ação: Inspecionar Pipeline (/api/inspect)
    // ==========================================
    btnInspect.addEventListener('click', () => {
        const code = editor.getValue();
        const filename = editorFilename.textContent || 'codigo.minipar';

        if (!code.trim()) {
            alert('Por favor, digite ou selecione um código MiniPar antes de inspecionar.');
            return;
        }

        setStatus('working', 'Analisando código...');
        btnInspect.disabled = true;

        fetch('/api/inspect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, filename })
        })
        .then(res => res.json())
        .then(data => {
            btnInspect.disabled = false;
            if (data.success) {
                setStatus('ready', 'Inspeção concluída com sucesso!');
            } else {
                setStatus('error', `Falha na fase: ${data.phase || 'desconhecida'}`);
            }

            // Atualiza Fase 1: Tokens
            renderTokens(data.tokens || []);

            // Atualiza Fase 2: Árvore AST Visual
            if (data.ast) {
                renderAstTree(data.ast);
            } else {
                clearAstTree();
            }

            // Atualiza Fase 3: Semântico e Tabela de Símbolos
            renderSemantic(data.symbols || [], data.semantic_checks, data.error, data.phase);

            // Atualiza Fase 4: TAC
            tacCodeContent.textContent = data.tac || '# Nenhum código TAC gerado.';

            // Atualiza Fase 5: C++
            cppCodeContent.textContent = data.cpp || '// Nenhum código C++ gerado.';

            // Atualiza terminal com resumo
            let summary = `=== MiniPar Pipeline Inspector ===\n`;
            summary += `Arquivo: ${data.filename}\n`;
            summary += `Tokens Léxicos: ${data.tokens_count || 0}\n`;
            summary += `Nós na AST: ${countAstNodes(data.ast)}\n`;
            summary += `Símbolos Registrados: ${data.symbols ? data.symbols.length : 0}\n`;
            if (data.semantic_checks) {
                summary += `Blocos Pure: ${data.semantic_checks.pure_blocks || 0} | Impure: ${data.semantic_checks.impure_blocks || 0}\n`;
                summary += `Tarefas Fork: ${data.semantic_checks.fork_blocks || 0} | Barreiras Join: ${data.semantic_checks.join_stmts || 0}\n`;
            }
            if (!data.success && data.error) {
                summary += `\n[ERRO NA FASE ${data.phase.toUpperCase()}]: ${data.error}\n`;
            } else {
                summary += `\nStatus: Compilação e Verificações 100% Válidas! Pronto para execução.\n`;
            }
            terminalOutput.textContent = summary;
        })
        .catch(err => {
            btnInspect.disabled = false;
            setStatus('error', 'Erro de comunicação');
            terminalOutput.textContent = `[ERRO]: ${err.message}`;
            console.error(err);
        });
    });

    // ==========================================
    // 8. Renderização da Tabela de Tokens
    // ==========================================
    function renderTokens(tokens) {
        currentTokens = tokens;
        badgeTokensCount.textContent = tokens.length;
        tokensCountLabel.textContent = `${tokens.length} tokens identificados`;

        applyTokensFilter();
    }

    function applyTokensFilter() {
        const categoryFilter = filterTokenCategory.value;
        const searchFilter = (tokensSearch.value || '').toLowerCase().trim();

        const filtered = currentTokens.filter(t => {
            const matchesCat = categoryFilter === 'all' || t.category === categoryFilter;
            const matchesSearch = !searchFilter || 
                t.lexeme.toLowerCase().includes(searchFilter) || 
                t.type.toLowerCase().includes(searchFilter);
            return matchesCat && matchesSearch;
        });

        tokensCountLabel.textContent = `${filtered.length} de ${currentTokens.length} tokens`;

        if (filtered.length === 0) {
            tokensTbody.innerHTML = `<tr><td colspan="6" class="text-center empty-cell">Nenhum token encontrado com os filtros aplicados.</td></tr>`;
            return;
        }

        tokensTbody.innerHTML = filtered.map(t => {
            let badgeClass = 'badge-literal';
            if (t.category.includes('SPar')) badgeClass = 'badge-spar';
            else if (t.category.includes('Concorrência') || t.category.includes('Paralelismo')) badgeClass = 'badge-fork';
            else if (t.category.includes('Objetos')) badgeClass = 'badge-oop';
            else if (t.category.includes('Controle')) badgeClass = 'badge-ctrl';
            else if (t.category.includes('Declaração')) badgeClass = 'badge-decl';
            else if (t.category.includes('Operador')) badgeClass = 'badge-op';
            else if (t.category.includes('Delimitador')) badgeClass = 'badge-delim';

            return `
                <tr>
                    <td><strong>${t.index}</strong></td>
                    <td><span class="token-lexeme">${escapeHtml(t.lexeme)}</span></td>
                    <td><code>${t.type}</code></td>
                    <td><span class="badge ${badgeClass}">${t.category}</span></td>
                    <td>Linha ${t.line}</td>
                    <td>Col ${t.col}</td>
                </tr>
            `;
        }).join('');
    }

    filterTokenCategory.addEventListener('change', applyTokensFilter);
    tokensSearch.addEventListener('input', applyTokensFilter);

    // ==========================================
    // 9. Renderização da Tabela de Símbolos
    // ==========================================
    function renderSemantic(symbols, checks, errorMsg, phase) {
        badgeSymbolsCount.textContent = symbols.length;
        symbolsCountLabel.textContent = `${symbols.length} identificadores registrados`;

        if (checks && checks.valid) {
            semanticBadge.className = 'badge badge-success';
            semanticBadge.textContent = 'Validações OK';
            semanticErrorsList.style.display = 'none';
        } else {
            semanticBadge.className = 'badge badge-error';
            semanticBadge.textContent = 'Erro Semântico Detectado';
            semanticErrorsList.style.display = 'block';
            semanticErrorsList.innerHTML = `<strong>Falha na Validação:</strong> ${escapeHtml(errorMsg || 'Erro na análise semântica.')}`;
        }

        if (symbols.length === 0) {
            symbolsTbody.innerHTML = `<tr><td colspan="5" class="text-center empty-cell">Nenhum símbolo declarado no programa.</td></tr>`;
            return;
        }

        symbolsTbody.innerHTML = symbols.map(s => {
            let scopeBadge = 'badge-literal';
            if (s.scope === 'Global') scopeBadge = 'badge-oop';
            else if (s.scope === 'PureBlock') scopeBadge = 'badge-spar';
            else if (s.scope.startsWith('Func:')) scopeBadge = 'badge-ctrl';
            else if (s.scope.startsWith('Class:')) scopeBadge = 'badge-decl';

            const details = (s.params && s.params.length > 0) ? `Parâmetros: (${s.params.join(', ')})` : '--';

            return `
                <tr>
                    <td><strong>${escapeHtml(s.name)}</strong></td>
                    <td><code>${escapeHtml(s.type)}</code></td>
                    <td><span class="badge ${scopeBadge}">${escapeHtml(s.scope)}</span></td>
                    <td>Linha ${s.line}</td>
                    <td>${escapeHtml(details)}</td>
                </tr>
            `;
        }).join('');
    }

    // ==========================================
    // 10. RENDERIZAÇÃO DA ÁRVORE SINTÁTICA (AST) EM D3.JS / SVG (DESTAQUE!)
    // ==========================================
    function countAstNodes(node) {
        if (!node) return 0;
        let count = 1;
        if (node.children) {
            node.children.forEach(c => { count += countAstNodes(c); });
        }
        if (node._children) {
            node._children.forEach(c => { count += countAstNodes(c); });
        }
        return count;
    }

    function clearAstTree() {
        astSvg.selectAll('*').remove();
        astEmptyMessage.style.display = 'block';
        badgeAstNodes.textContent = '0';
    }

    function renderAstTree(astData) {
        currentAstData = JSON.parse(JSON.stringify(astData)); // Cópia profunda
        astEmptyMessage.style.display = 'none';
        astSvg.selectAll('*').remove();

        const totalNodes = countAstNodes(currentAstData);
        badgeAstNodes.textContent = totalNodes;

        const container = document.getElementById('ast-canvas-container');
        const width = container.clientWidth || 800;
        const height = container.clientHeight || 600;

        // Grupo principal para Zoom e Pan
        d3SvgGroup = astSvg.append('g').attr('class', 'viewport');

        d3Zoom = d3.zoom()
            .scaleExtent([0.15, 3.0])
            .on('zoom', (event) => {
                d3SvgGroup.attr('transform', event.transform);
            });

        astSvg.call(d3Zoom)
              .on('dblclick.zoom', null); // Desabilita zoom em duplo clique para não conflitar com nós

        // Cria a hierarquia D3
        d3Root = d3.hierarchy(currentAstData, d => d.children);
        d3Root.x0 = width / 2;
        d3Root.y0 = 40;

        // Se a árvore for muito grande, colapsa nós abaixo do 3º nível por padrão para manter didático e limpo
        if (totalNodes > 30) {
            collapseDeepNodes(d3Root, 0, 3);
        }

        updateAst(d3Root);
        fitAstToView();
    }

    function collapseDeepNodes(d, currentDepth, maxDepth) {
        if (d.children) {
            if (currentDepth >= maxDepth) {
                d._children = d.children;
                d.children = null;
            } else {
                d.children.forEach(child => collapseDeepNodes(child, currentDepth + 1, maxDepth));
            }
        }
    }

    // Atualização e transição suave da Árvore
    function updateAst(source) {
        const CARD_W = 150;
        const CARD_H = 50;

        const treeLayout = d3.tree()
            .nodeSize([CARD_W + 35, CARD_H + 50])
            .separation((a, b) => (a.parent === b.parent ? 1.15 : 1.35));

        const treeData = treeLayout(d3Root);
        const nodes = treeData.descendants();
        const links = treeData.links();

        // Animação de nós
        const duration = 400;

        // ==========================================
        // 10.1 Arestas (Links)
        // ==========================================
        const link = d3SvgGroup.selectAll('path.ast-link')
            .data(links, d => d.target.id || (d.target.id = Math.random()));

        const linkEnter = link.enter().insert('path', 'g')
            .attr('class', 'ast-link')
            .attr('d', () => {
                const o = { x: source.x0 || source.x, y: source.y0 || source.y };
                return d3.linkVertical().x(d => d.x).y(d => d.y)({ source: o, target: o });
            });

        const linkUpdate = linkEnter.merge(link);
        linkUpdate.transition()
            .duration(duration)
            .attr('d', d3.linkVertical().x(d => d.x).y(d => d.y));

        link.exit().transition()
            .duration(duration)
            .attr('d', () => {
                const o = { x: source.x, y: source.y };
                return d3.linkVertical().x(d => d.x).y(d => d.y)({ source: o, target: o });
            })
            .remove();

        // ==========================================
        // 10.2 Nós (Nodes)
        // ==========================================
        const node = d3SvgGroup.selectAll('g.ast-node')
            .data(nodes, d => d.id || (d.id = Math.random()));

        const nodeEnter = node.enter().append('g')
            .attr('class', d => `ast-node ${getNodeCategoryClass(d.data)}`)
            .attr('transform', () => `translate(${source.x0 || source.x},${source.y0 || source.y})`)
            .on('click', (event, d) => {
                event.stopPropagation();
                toggleNode(d);
            })
            .on('mouseenter', (event, d) => showNodeTooltip(event, d))
            .on('mouseleave', hideNodeTooltip);

        // Retângulo do Cartão do Nó
        nodeEnter.append('rect')
            .attr('class', 'node-card')
            .attr('width', CARD_W)
            .attr('height', CARD_H)
            .attr('x', -CARD_W / 2)
            .attr('y', -CARD_H / 2);

        // Faixa de Categoria / Tag Superior
        nodeEnter.append('text')
            .attr('class', 'node-type-label')
            .attr('x', -CARD_W / 2 + 10)
            .attr('y', -CARD_H / 2 + 18)
            .text(d => truncate(d.data.type || 'Node', 16));

        // Tag da Linha (L..)
        nodeEnter.append('text')
            .attr('class', 'node-line-badge')
            .attr('x', CARD_W / 2 - 10)
            .attr('y', -CARD_H / 2 + 18)
            .attr('text-anchor', 'end')
            .text(d => `L${d.data.line || 1}`);

        // Detalhes / Operador / Valor Central
        nodeEnter.append('text')
            .attr('class', 'node-detail-label')
            .attr('x', 0)
            .attr('y', CARD_H / 2 - 12)
            .attr('text-anchor', 'middle')
            .text(d => {
                const dt = d.data.details;
                return dt ? `[ ${truncate(dt, 16)} ]` : '•';
            });

        // Indicador de Filhos (Círculo de expansão/recolhimento)
        nodeEnter.append('circle')
            .attr('class', 'collapse-indicator')
            .attr('r', 7)
            .attr('cx', 0)
            .attr('cy', CARD_H / 2)
            .attr('fill', '#ffffff')
            .attr('stroke', '#64748b')
            .style('display', d => (d.children || d._children) ? 'block' : 'none');

        nodeEnter.append('text')
            .attr('class', 'collapse-icon-text')
            .attr('x', 0)
            .attr('y', CARD_H / 2 + 3.5)
            .attr('text-anchor', 'middle')
            .attr('font-size', '9px')
            .attr('font-weight', '700')
            .attr('fill', '#64748b')
            .attr('pointer-events', 'none')
            .text(d => d._children ? '+' : (d.children ? '−' : ''));

        // Transição de Entrada para Posição Final
        const nodeUpdate = nodeEnter.merge(node);

        nodeUpdate.transition()
            .duration(duration)
            .attr('transform', d => `translate(${d.x},${d.y})`);

        nodeUpdate.select('circle.collapse-indicator')
            .style('display', d => (d.children || d._children) ? 'block' : 'none')
            .attr('fill', d => d._children ? '#3b82f6' : '#ffffff')
            .attr('stroke', d => d._children ? '#1d4ed8' : '#64748b');

        nodeUpdate.select('text.collapse-icon-text')
            .text(d => d._children ? '+' : (d.children ? '−' : ''))
            .attr('fill', d => d._children ? '#ffffff' : '#64748b');

        // Saída de nós colapsados
        const nodeExit = node.exit().transition()
            .duration(duration)
            .attr('transform', () => `translate(${source.x},${source.y})`)
            .remove();

        nodeExit.select('rect').attr('width', 0).attr('height', 0);

        // Salva posições para próxima animação
        nodes.forEach(d => {
            d.x0 = d.x;
            d.y0 = d.y;
        });
    }

    function toggleNode(d) {
        if (d.children) {
            d._children = d.children;
            d.children = null;
        } else if (d._children) {
            d.children = d._children;
            d._children = null;
        }
        updateAst(d);
    }

    function getNodeCategoryClass(data) {
        const cat = data.category || '';
        const type = data.type || '';
        if (cat === 'pure' || type === 'PureBlock') return 'pure';
        if (cat === 'impure' || type === 'ImpureBlock') return 'impure';
        if (cat === 'fork' || type === 'ForkBlock') return 'fork';
        if (cat === 'join' || type === 'JoinStmt') return 'join';
        if (cat === 'class' || cat === 'func' || type === 'ClassDecl' || type === 'FuncDecl') return 'class';
        if (cat === 'control' || type.endsWith('Stmt')) return 'control';
        return 'default';
    }

    function showNodeTooltip(event, d) {
        const dt = d.data;
        let role = 'Instrução / Expressão da AST';
        if (dt.type === 'PureBlock') role = '🌿 Anotação SPar: Região de dados independente (Paralelizável sem locks)';
        else if (dt.type === 'ImpureBlock') role = '🔒 Anotação SPar: Região impura com efeito colateral (Protegida por Mutex Lock)';
        else if (dt.type === 'ForkBlock') role = '⚡ Primitiva Fork: Disparo assíncrono de subtarefa em thread separada';
        else if (dt.type === 'JoinStmt') role = '🛑 Primitiva Join: Barreira de sincronização que aguarda todas as tarefas filhas';
        else if (dt.type === 'ClassDecl') role = '📦 Declaração de Classe Orientada a Objetos';
        else if (dt.type === 'FuncDecl') role = '⚙️ Declaração de Função / Método';

        const childrenCount = (d.children ? d.children.length : (d._children ? d._children.length : 0));

        astTooltip.innerHTML = `
            <div class="ast-tooltip-title">${dt.type}</div>
            <div><strong>Detalhes:</strong> ${dt.details ? escapeHtml(dt.details) : 'N/A'}</div>
            <div><strong>Linha no Código:</strong> Linha ${dt.line || 1}</div>
            <div><strong>Subnós Filhos:</strong> ${childrenCount}</div>
            <div style="margin-top: 4px; font-size: 0.72rem; color: #93c5fd;">${role}</div>
        `;
        astTooltip.style.display = 'block';

        const containerRect = document.getElementById('ast-canvas-container').getBoundingClientRect();
        astTooltip.style.left = `${event.clientX - containerRect.left + 15}px`;
        astTooltip.style.top = `${event.clientY - containerRect.top + 15}px`;
    }

    function hideNodeTooltip() {
        astTooltip.style.display = 'none';
    }

    // Centralizar e ajustar AST na tela
    function fitAstToView() {
        if (!d3SvgGroup || !d3Root) return;
        const container = document.getElementById('ast-canvas-container');
        const containerW = container.clientWidth || 800;
        const containerH = container.clientHeight || 600;

        const bounds = d3SvgGroup.node().getBBox();
        if (!bounds || bounds.width === 0 || bounds.height === 0) return;

        const fullW = bounds.width;
        const fullH = bounds.height;
        const midX = bounds.x + fullW / 2;
        const midY = bounds.y + fullH / 2;

        const scale = Math.min(0.9, Math.min(containerW / (fullW + 80), containerH / (fullH + 80)));
        const transform = d3.zoomIdentity
            .translate(containerW / 2 - scale * midX, 40)
            .scale(scale);

        astSvg.transition().duration(500).call(d3Zoom.transform, transform);
    }

    btnAstReset.addEventListener('click', fitAstToView);

    btnAstZoomIn.addEventListener('click', () => {
        astSvg.transition().duration(250).call(d3Zoom.scaleBy, 1.3);
    });

    btnAstZoomOut.addEventListener('click', () => {
        astSvg.transition().duration(250).call(d3Zoom.scaleBy, 0.75);
    });

    // Expandir / Recolher Todos
    btnAstToggleCollapse.addEventListener('click', () => {
        if (!d3Root) return;
        allNodesCollapsed = !allNodesCollapsed;
        function toggleAll(d) {
            if (allNodesCollapsed) {
                if (d.children) {
                    d._children = d.children;
                    d.children = null;
                }
            } else {
                if (d._children) {
                    d.children = d._children;
                    d._children = null;
                }
            }
            const arr = d.children || d._children;
            if (arr) arr.forEach(toggleAll);
        }
        toggleAll(d3Root);
        updateAst(d3Root);
        setTimeout(fitAstToView, 450);
    });

    // Busca de nós na AST
    astSearchInput.addEventListener('input', () => {
        const query = astSearchInput.value.toLowerCase().trim();
        if (!d3SvgGroup) return;

        const nodeCards = d3SvgGroup.selectAll('rect.node-card');
        if (!query) {
            nodeCards.style('stroke', null).style('stroke-width', null);
            return;
        }

        let firstMatch = null;
        nodeCards.each(function(d) {
            const matches = (d.data.type || '').toLowerCase().includes(query) ||
                            (d.data.details || '').toLowerCase().includes(query);
            if (matches) {
                d3.select(this)
                    .style('stroke', '#e11d48')
                    .style('stroke-width', '3.5px');
                if (!firstMatch) firstMatch = d;
            } else {
                d3.select(this)
                    .style('stroke', null)
                    .style('stroke-width', null);
            }
        });

        // Foca suavemente no primeiro nó encontrado
        if (firstMatch) {
            const container = document.getElementById('ast-canvas-container');
            const transform = d3.zoomIdentity
                .translate(container.clientWidth / 2 - 1.2 * firstMatch.x, container.clientHeight / 2 - 1.2 * firstMatch.y)
                .scale(1.2);
            astSvg.transition().duration(500).call(d3Zoom.transform, transform);
        }
    });

    // ==========================================
    // 11. Ação: Compilar e Executar (/api/compile)
    // ==========================================
    btnRun.addEventListener('click', () => {
        const code = editor.getValue();
        const filename = editorFilename.textContent || 'ide_temp.minipar';
        const userInputs = userInputsEl.value ? userInputsEl.value.split('\n') : [];

        if (!code.trim()) {
            alert('Por favor, digite ou selecione um código MiniPar antes de executar.');
            return;
        }

        setStatus('working', 'Compilando e executando binário C++...');
        btnRun.disabled = true;
        terminalOutput.textContent = 'Compilando código MiniPar e gerando executável nativo via g++ (-std=c++20 -O3 -pthread)...';

        fetch('/api/compile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, filename, inputs: userInputs })
        })
        .then(res => res.json())
        .then(data => {
            btnRun.disabled = false;
            if (data.success) {
                setStatus('ready', 'Execução concluída com sucesso!');
                terminalOutput.textContent = data.stdout || 'Executado sem saídas no console.';
            } else {
                setStatus('error', 'Falha na compilação ou execução');
                terminalOutput.textContent = data.stderr || data.error || 'Erro desconhecido.';
            }

            // Atualiza TAC e C++ se retornados
            if (data.tac) tacCodeContent.textContent = data.tac;
            if (data.cpp) cppCodeContent.textContent = data.cpp;

            // Atualiza métricas de benchmark se disponíveis
            if (data.benchmark) {
                const b = data.benchmark;
                if (b.execution_time_total) {
                    executionTimeBadge.style.display = 'inline-block';
                    executionTimeBadge.textContent = `${b.execution_time_total}s`;
                }

                if (b.speedup) {
                    kpiSpeedup.textContent = `${b.speedup}x`;
                    kpiSpeedup.style.color = '#059669';
                } else {
                    kpiSpeedup.textContent = '--';
                }

                kpiTimeSeq.textContent = b.time_seq ? `${b.time_seq}s` : '--';
                kpiTimePar.textContent = b.time_par ? `${b.time_par}s` : '--';
                kpiReduction.textContent = b.reduction_pct ? `${b.reduction_pct}%` : '--';

                // Se tiver speedup relevante, sugere visualização na aba de benchmark
                if (b.is_benchmark) {
                    const benchTab = document.querySelector('.tab-btn[data-tab="tab-benchmark"]');
                    if (benchTab) {
                        benchTab.classList.add('pulse-benchmark');
                    }
                }
            }
        })
        .catch(err => {
            btnRun.disabled = false;
            setStatus('error', 'Falha na comunicação');
            terminalOutput.textContent = `[ERRO]: ${err.message}`;
            console.error(err);
        });
    });

    // ==========================================
    // 12. Ação: Baixar Executável (.exe)
    // ==========================================
    btnDownload.addEventListener('click', () => {
        const filename = editorFilename.textContent || 'ide_temp.minipar';
        setStatus('working', 'Preparando download do .exe...');
        window.location.href = `/api/download_exe/${encodeURIComponent(filename)}`;
        setTimeout(() => setStatus('ready', 'Download solicitado'), 1200);
    });

    // Limpar editor
    btnClear.addEventListener('click', () => {
        if (confirm('Deseja limpar todo o código do editor?')) {
            editor.setValue('');
            editorFilename.textContent = 'novo_programa.minipar';
            setStatus('ready', 'Editor limpo');
        }
    });

    btnClearTerminal.addEventListener('click', () => {
        terminalOutput.textContent = 'Terminal limpo.';
        executionTimeBadge.style.display = 'none';
    });

    // ==========================================
    // 13. Copiar TAC e C++
    // ==========================================
    function setupCopy(btn, contentEl, label) {
        btn.addEventListener('click', () => {
            const text = contentEl.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const oldHtml = btn.innerHTML;
                btn.innerHTML = `<i class="fa-solid fa-check"></i> Copiado!`;
                setTimeout(() => { btn.innerHTML = oldHtml; }, 1800);
            }).catch(() => {
                alert(`Não foi possível copiar o código ${label}.`);
            });
        });
    }

    setupCopy(btnCopyTac, tacCodeContent, 'TAC');
    setupCopy(btnCopyCpp, cppCodeContent, 'C++');

    // ==========================================
    // 14. Utilitários
    // ==========================================
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function truncate(str, len) {
        if (!str) return '';
        return str.length > len ? str.substring(0, len) + '…' : str;
    }
});

