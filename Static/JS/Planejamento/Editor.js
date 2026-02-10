/**
 * Editor.js - Cockpit de Planejamento Visual (Versão Glass)
 */

let map;
let routeLayerGroup; 
let currentState = {
    estrategia: 'recomendada',
    rotaSelecionada: null
};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    // Inicia selecionando a estratégia recomendada com um pequeno delay para efeito visual
    setTimeout(() => SelecionarEstrategia('recomendada'), 300);
});

// --- 1. Inicialização do Mapa ---
function initMap() {
    // Fallback para centro do Brasil se coords zeradas
    const lat = window.origemCoords.lat || -15.79;
    const lon = window.origemCoords.lon || -47.88;

    map = L.map('map', { zoomControl: false, attributionControl: false }).setView([lat, lon], 5);

    // Tiles (CartoDB Voyager - Clean & Modern)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    L.control.zoom({ position: 'topright' }).addTo(map);
    routeLayerGroup = L.layerGroup().addTo(map);
}

// --- 2. Lógica de Seleção de Estratégia ---
window.SelecionarEstrategia = function(tipo) {
    currentState.estrategia = tipo;

    // UI: Atualiza Abas
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tab-${tipo}`);
    if(btn) btn.classList.add('active');

    // Dados
    const rotas = window.opcoesRotas[tipo];
    currentState.rotaSelecionada = rotas;

    // Renderização
    RenderizarRotaNoMapa(rotas);
    RenderizarTimeline(rotas);
    AtualizarMetricas(rotas);
    
    // Controle do Botão
    const btnSalvar = document.getElementById('btn-confirmar');
    if(!rotas || rotas.length === 0) {
        btnSalvar.disabled = true;
        btnSalvar.innerHTML = '<i class="ph-bold ph-warning"></i> Sem Rota Disponível';
    } else {
        btnSalvar.disabled = false;
        btnSalvar.innerHTML = '<i class="ph-bold ph-check-circle"></i> Confirmar Rota';
    }
};

// --- 3. Renderização Visual ---

function RenderizarRotaNoMapa(listaTrechos) {
    routeLayerGroup.clearLayers();
    if (!listaTrechos || listaTrechos.length === 0) return;

    const latlngs = [];

    listaTrechos.forEach((trecho, index) => {
        const origem = [trecho.origem.lat, trecho.origem.lon];
        const destino = [trecho.destino.lat, trecho.destino.lon];

        // Marcador Origem
        if (index === 0) {
            L.circleMarker(origem, { color: '#10b981', radius: 8, fillOpacity: 1, fillColor: '#fff', weight: 3 }).addTo(routeLayerGroup)
                .bindPopup(`<b>Origem:</b> ${trecho.origem.nome}`);
            latlngs.push(origem);
        }

        // Marcador Destino
        L.circleMarker(destino, { color: '#004aad', radius: 8, fillOpacity: 1, fillColor: '#fff', weight: 3 }).addTo(routeLayerGroup)
            .bindPopup(`<b>Destino:</b> ${trecho.destino.nome}`);
        
        latlngs.push(destino);
    });

    // Linha da Rota
    const polyline = L.polyline(latlngs, {
        color: '#004aad', 
        weight: 4,
        opacity: 0.8,
        dashArray: '10, 10', 
        lineCap: 'round'
    }).addTo(routeLayerGroup);

    // Ajusta Zoom com padding para não ficar embaixo da sidebar
    map.fitBounds(polyline.getBounds(), { 
        paddingTopLeft: [450, 50],  // Compensa a sidebar
        paddingBottomRight: [50, 50]
    });
}

function RenderizarTimeline(listaTrechos) {
    const container = document.getElementById('timeline-content');
    container.innerHTML = '';

    if (!listaTrechos || listaTrechos.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--cor-texto-secundario); opacity: 0.7;">
                <i class="ph-duotone ph-airplane-slash" style="font-size: 3rem; margin-bottom: 10px;"></i>
                <p>Nenhuma rota encontrada para esta estratégia.</p>
            </div>
        `;
        return;
    }

    let html = '';
    listaTrechos.forEach((trecho, idx) => {
        // Conexão
        if (idx > 0) {
            html += `
                <div class="connection-line">
                    <i class="ph-bold ph-clock-clockwise"></i> Troca de aeronave em ${trecho.origem.iata}
                </div>
            `;
        }

        // Card de Voo
        html += `
            <div class="flight-card" style="animation-delay: ${idx * 0.1}s">
                <div class="flight-header">
                    <div class="cia-logo-box">
                         <img src="/Luft-ConnectAir/Static/Img/Logos/${trecho.cia}.png" class="cia-logo" onerror="this.src='https://placehold.co/40x40?text=${trecho.cia}'">
                    </div>
                    <span class="cia-name">${trecho.cia} ${trecho.voo}</span>
                    <span class="flight-date">${trecho.data}</span>
                </div>
                
                <div class="flight-route">
                    <div class="airport-block">
                        <div class="airport-code">${trecho.origem.iata}</div>
                        <div class="flight-time">${trecho.horario_saida}</div>
                    </div>
                    
                    <div class="flight-arrow-anim">
                        <i class="ph-bold ph-airplane-tilt"></i>
                    </div>
                    
                    <div class="airport-block">
                        <div class="airport-code">${trecho.destino.iata}</div>
                        <div class="flight-time">${trecho.horario_chegada}</div>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function AtualizarMetricas(listaTrechos) {
    const container = document.getElementById('strategy-metrics');
    
    if(!listaTrechos || listaTrechos.length === 0) {
        container.style.opacity = '0.5';
        return;
    }
    
    const info = listaTrechos[0]; // Dados agregados vêm no primeiro item
    const els = container.children;
    
    // Animação simples de atualização de números
    els[0].querySelector('.val').innerText = info.total_custo || 'R$ --';
    els[1].querySelector('.val').innerText = info.total_duracao || '--:--';
    els[2].querySelector('.val').innerText = (listaTrechos.length - 1) + (listaTrechos.length > 1 ? ' escalas' : ' escala');
    
    container.style.opacity = '1';
}

// --- 4. Submissão ---
window.ConfirmarPlanejamento = function() {
    if (!currentState.rotaSelecionada) return;

    const btn = document.getElementById('btn-confirmar');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Processando...';

    // Prepara Payload
    const rotaFormatada = currentState.rotaSelecionada.map(trecho => ({
        cia: trecho.cia,
        voo: trecho.voo,
        origem: trecho.origem.iata,
        destino: trecho.destino.iata,
        partida_iso: InverterData(trecho.data) + 'T' + trecho.horario_saida + ':00',
        chegada_iso: InverterData(trecho.data) + 'T' + trecho.horario_chegada + ':00'
    }));

    const payload = {
        filial: window.ctc.filial,
        serie: window.ctc.serie,
        ctc: window.ctc.ctc,
        rota_completa: rotaFormatada,
        estrategia: currentState.estrategia
    };

    fetch(URL_GRAVAR_PLANEJAMENTO, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if(data.sucesso) {
            btn.innerHTML = '<i class="ph-bold ph-check"></i> Sucesso!';
            btn.style.background = '#10b981'; // Verde Sucesso
            btn.style.animation = 'none';
            setTimeout(() => {
                window.location.href = '/Luft-ConnectAir/Planejamento/Dashboard';
            }, 1000);
        } else {
            alert('Erro ao salvar: ' + (data.msg || 'Erro desconhecido'));
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert('Erro de comunicação com o servidor.');
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
};

function InverterData(strData) {
    if(!strData) return '';
    const parts = strData.split('/');
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
}

// --- 5. Controle do Modal de Lote ---

window.AbrirModalLote = function() {
    const backdrop = document.getElementById('modal-lote-backdrop');
    if(backdrop) {
        backdrop.classList.remove('hidden');
        // Pequeno timeout para permitir que a transição CSS funcione
        setTimeout(() => backdrop.classList.add('visible'), 10);
    }
};

window.FecharModalLote = function(event) {
    // Se passar evento (clique no backdrop), verifica se clicou fora
    if (event && !event.target.classList.contains('modal-backdrop')) return;

    const backdrop = document.getElementById('modal-lote-backdrop');
    if(backdrop) {
        backdrop.classList.remove('visible');
        setTimeout(() => backdrop.classList.add('hidden'), 300); // Espera animação acabar
    }
};

// Atalho de teclado para fechar (ESC)
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') window.FecharModalLote(null);
});