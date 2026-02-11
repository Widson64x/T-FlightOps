/**
 * Ranking.js - Versão 3.0 (Performance Otimizada)
 * - Infinite Scroll
 * - Debounce na Pesquisa
 * - Manipulação eficiente do DOM
 */

let EstadoAtual = {
    modo: 'GLOBAL', 
    ufSelecionada: null,
    listaCompletaFiltrada: [], // A lista total que atende aos filtros atuais
    itensRenderizados: 0,      // Controle de paginação
    ITENS_POR_PAGINA: 50       // Quantidade de cards por lote
};

let CacheGlobal = null; // Cache para não recalcular o "Global" toda vez
let TimeoutPesquisa = null; // Para o debounce

document.addEventListener('DOMContentLoaded', () => {
    ConfigurarScrollInfinito();
    AtivarModoGlobal(); 
});

// --- MODOS DE NAVEGAÇÃO ---

function AtivarModoGlobal() {
    EstadoAtual.modo = 'GLOBAL';
    EstadoAtual.ufSelecionada = null;
    ResetarSidebar();
    document.getElementById('btn-global').classList.add('active');

    // Usa cache se já tiver calculado antes
    if (!CacheGlobal) {
        let todos = [];
        Object.keys(window.DadosRanking).forEach(uf => {
            const aeroportosUf = window.DadosRanking[uf].map(a => ({...a, ufOrigem: uf}));
            todos = [...todos, ...aeroportosUf];
        });
        // Ordena maior -> menor
        todos.sort((a, b) => b.importancia - a.importancia);
        CacheGlobal = todos;
    }

    AtualizarHeader('Visão Global', 'Ordenado por Índice de Importância');
    
    // Reseta lista e renderiza o primeiro lote
    EstadoAtual.listaCompletaFiltrada = CacheGlobal;
    ResetarRenderizacao();
}

function SelecionarUf(uf) {
    EstadoAtual.modo = 'UF';
    EstadoAtual.ufSelecionada = uf;

    ResetarSidebar();
    const btnUf = document.getElementById(`uf-${uf}`);
    if(btnUf) btnUf.classList.add('active');

    const lista = window.DadosRanking[uf] || [];
    
    AtualizarHeader(`Aeroportos de ${uf}`, 'Ajuste a prioridade local');
    
    EstadoAtual.listaCompletaFiltrada = lista;
    ResetarRenderizacao();
}

function ResetarSidebar() {
    document.querySelectorAll('.uf-card').forEach(el => el.classList.remove('active'));
    // Opcional: Manter o termo de pesquisa ou limpar? Aqui limpei para evitar confusão
    const input = document.getElementById('global-search');
    if(input && EstadoAtual.modo !== 'GLOBAL') input.value = '';
}

// --- PESQUISA COM DEBOUNCE (LEVEZA) ---

function FiltrarGlobal(termo) {
    // Cancela a execução anterior se o usuário ainda estiver digitando
    clearTimeout(TimeoutPesquisa);

    // Aguarda 300ms antes de processar
    TimeoutPesquisa = setTimeout(() => {
        ExecutarFiltro(termo);
    }, 300);
}

function ExecutarFiltro(termo) {
    termo = termo.toLowerCase().trim();

    if (termo === '') {
        if (EstadoAtual.modo === 'GLOBAL') AtivarModoGlobal();
        else SelecionarUf(EstadoAtual.ufSelecionada);
        return;
    }

    // Remove active da sidebar visualmente
    document.querySelectorAll('.uf-card').forEach(el => el.classList.remove('active'));

    // Busca sempre na base completa (CacheGlobal)
    // Se quiser buscar só na UF atual, mude CacheGlobal para window.DadosRanking[EstadoAtual.ufSelecionada]
    if (!CacheGlobal) AtivarModoGlobal(); // Garante que o cache exista

    const baseBusca = CacheGlobal; 
    
    const resultados = baseBusca.filter(a => {
        return (a.iata && a.iata.toLowerCase().includes(termo)) ||
               (a.nome && a.nome.toLowerCase().includes(termo)) ||
               (a.regiao && a.regiao.toLowerCase().includes(termo));
    });

    AtualizarHeader('Resultados da Busca', `${resultados.length} aeroportos encontrados`);
    
    EstadoAtual.listaCompletaFiltrada = resultados;
    ResetarRenderizacao();
}

// --- RENDERIZAÇÃO INTELIGENTE (SCROLL INFINITO) ---

function ConfigurarScrollInfinito() {
    const container = document.getElementById('container-aeroportos');
    container.addEventListener('scroll', () => {
        // Se rolou até perto do final (margem de 100px)
        if (container.scrollTop + container.clientHeight >= container.scrollHeight - 100) {
            RenderizarProximoLote();
        }
    });
}

function ResetarRenderizacao() {
    const container = document.getElementById('container-aeroportos');
    container.scrollTop = 0; // Volta ao topo
    container.innerHTML = '';
    EstadoAtual.itensRenderizados = 0;
    
    if (EstadoAtual.listaCompletaFiltrada.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--cor-texto-secundario); opacity: 0.7;">
                <i class="ph-duotone ph-airplane-slash" style="font-size: 3rem; margin-bottom:15px;"></i>
                <p style="font-size: 1.1rem;">Nenhum aeroporto encontrado.</p>
            </div>`;
        return;
    }

    RenderizarProximoLote();
}

function RenderizarProximoLote() {
    const total = EstadoAtual.listaCompletaFiltrada.length;
    if (EstadoAtual.itensRenderizados >= total) return; // Já renderizou tudo

    const inicio = EstadoAtual.itensRenderizados;
    const fim = Math.min(inicio + EstadoAtual.ITENS_POR_PAGINA, total);
    
    const lote = EstadoAtual.listaCompletaFiltrada.slice(inicio, fim);
    
    // Constrói HTML em uma única string gigante (Muito mais rápido que innerHTML += repetido)
    const htmlLote = lote.map(aero => ConstruirCardHTML(aero)).join('');
    
    const container = document.getElementById('container-aeroportos');
    // Insere o HTML sem destruir o que já existe (insertAdjacentHTML é performático)
    container.insertAdjacentHTML('beforeend', htmlLote);

    EstadoAtual.itensRenderizados = fim;
}

function ConstruirCardHTML(aero) {
    const tierClass = GetTierClass(aero.importancia);
    const colorStyle = GetColorStyle(aero.importancia);
    const mostrarUf = EstadoAtual.modo === 'GLOBAL' || aero.ufOrigem;
    
    const htmlUf = mostrarUf ? 
        `<span class="uf-mini-badge">${aero.ufOrigem || ''}</span>` : '';

    return `
        <div class="airport-card ${tierClass}" id="card-${aero.id_aeroporto}">
            <div class="card-top">
                <div style="display:flex; justify-content:space-between; width:100%; align-items:flex-start;">
                    <div class="iata-tag">${aero.iata || '---'}</div>
                    ${htmlUf}
                </div>
                <div class="airport-details" style="margin-top: 10px;">
                    <h3 title="${aero.nome}">${aero.nome}</h3>
                    <p><i class="ph-fill ph-map-pin"></i> ${aero.regiao || 'Região Desconhecida'}</p>
                </div>
            </div>
            
            <div class="slider-section">
                <div class="slider-labels">
                    <span>Importância</span>
                    <span class="percent-badge" id="badge-${aero.id_aeroporto}" style="color: ${colorStyle}">
                        ${aero.importancia}%
                    </span>
                </div>
                <div class="range-wrapper">
                    <div class="range-fill" id="fill-${aero.id_aeroporto}" style="width: ${aero.importancia}%; background: ${colorStyle}"></div>
                    <input type="range" min="0" max="100" value="${aero.importancia}" 
                           class="range-input" 
                           oninput="AtualizarInput(${aero.id_aeroporto}, this.value, '${aero.ufOrigem}')"
                           data-id="${aero.id_aeroporto}">
                </div>
            </div>
        </div>
    `;
}

function AtualizarHeader(titulo, subtitulo) {
    document.getElementById('titulo-view').innerText = titulo;
    document.getElementById('subtitulo-view').innerText = subtitulo;
}

// --- UPDATE E SALVAMENTO ---

function AtualizarInput(id, valor, ufRef) {
    valor = parseInt(valor);
    
    // Atualiza Visual (Apenas do card específico, muito leve)
    const badge = document.getElementById(`badge-${id}`);
    const fill = document.getElementById(`fill-${id}`);
    const card = document.getElementById(`card-${id}`);
    const color = GetColorStyle(valor);
    
    if(badge) { badge.innerText = `${valor}%`; badge.style.color = color; }
    if(fill) { fill.style.width = `${valor}%`; fill.style.background = color; }
    if(card) { card.className = `airport-card ${GetTierClass(valor)}`; }

    // Atualiza Fonte de Dados
    const ufAlvo = (ufRef && ufRef !== 'undefined') ? ufRef : EstadoAtual.ufSelecionada;
    if(ufAlvo && window.DadosRanking[ufAlvo]) {
        const index = window.DadosRanking[ufAlvo].findIndex(x => x.id_aeroporto === id);
        if(index >= 0) window.DadosRanking[ufAlvo][index].importancia = valor;
    }
}

function SalvarRankingAtual() {
    const btn = document.querySelector('.btn-save');
    const text = btn.querySelector('.btn-text');
    const originalText = text.innerText;
    
    text.innerText = 'Processando...';
    btn.disabled = true;

    // Salva todas as UFs em paralelo
    const promises = Object.keys(window.DadosRanking).map(uf => {
        return fetch('/Luft-ConnectAir/Aeroportos/API/SalvarRanking', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uf: uf, aeroportos: window.DadosRanking[uf] })
        }).then(r => r.json());
    });

    Promise.all(promises)
    .then(results => {
        const falhas = results.filter(r => !r.sucesso);
        if(falhas.length === 0) {
            text.innerText = 'Tudo Salvo!';
            btn.style.background = 'var(--cor-sucesso)';
            setTimeout(() => {
                text.innerText = originalText;
                btn.style.background = '';
                btn.disabled = false;
            }, 2000);
        } else {
            alert(`Erro ao salvar ${falhas.length} estados.`);
            text.innerText = originalText;
            btn.disabled = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert('Erro de comunicação.');
        text.innerText = originalText;
        btn.disabled = false;
    });
}

// Helpers
function GetTierClass(val) {
    if (val < 30) return 'tier-low';
    if (val < 70) return 'tier-mid';
    return 'tier-high';
}

function GetColorStyle(val) {
    if (val < 30) return 'var(--cor-erro)';
    if (val < 70) return 'var(--cor-aviso)';
    return 'var(--cor-sucesso)';
}