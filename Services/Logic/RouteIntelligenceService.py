from Services.LogService import LogService

class RouteIntelligenceService:
    """
    Serviço dedicado à inteligência de roteamento e categorização avançada.
    """

    # Pesos
    PESO_TEMPO = 1.0           
    PESO_CONEXAO = 150.0       
    PESO_CUSTO = 0.15        
    FATOR_PARCERIA_POWER = 2.2 
    PENALIDADE_SEM_TARIFA = 15000.0 

    @staticmethod
    def OtimizarOpcoes(lista_candidatos):
        """
        Gera as categorias
        """
        
        # Estrutura de Retorno
        Categorias = {
            'recomendada': [], 
            'direta': [],
            'rapida': [], 
            'economica': [], 
            'conexao_mesma_cia': [],
            'interline': []
        }

        if not lista_candidatos:
            return Categorias

        candidatos_processados = []

        LogService.Info("RouteIntelligence", f"--- CATEGORIZANDO {len(lista_candidatos)} OPCOES ---")

        # 1. Cálculo de Score para todos
        for i, item in enumerate(lista_candidatos):
            metricas = item['metricas']
            
            # Recalcula Score
            novo_score, _ = RouteIntelligenceService._CalcularScoreAvancado(
                duracao=metricas['duracao'],
                custo=metricas['custo'],
                conexoes=metricas['escalas'],
                trocas_cia=metricas['trocas_cia'],
                indice_parceria=metricas['indice_parceria'],
                sem_tarifa=metricas['sem_tarifa'] # Flag booleana vinda do MalhaService
            )
            item['metricas']['score'] = novo_score
            candidatos_processados.append(item)

        # 2. Preenchimento das Categorias

        # A) RECOMENDADA (Menor Score Geral)
        # O Score alto da penalidade já joga estas rotas para o final da lista,
        # mas elas ainda são retornadas se forem as únicas opções.
        candidatos_processados.sort(key=lambda x: x['metricas']['score'])
        
        # Tenta pegar uma que tenha custo < 10000 e NÃO seja "Sem Tarifa" primeiro
        if candidates_validos := [c for c in candidatos_processados if c['metricas']['custo'] < 10000 and not c['metricas']['sem_tarifa']]:
             Categorias['recomendada'] = candidates_validos[0]
        elif candidatos_processados:
             Categorias['recomendada'] = candidatos_processados[0]

        # B) DIRETA (0 Escalas)
        diretas = [c for c in candidatos_processados if c['metricas']['escalas'] == 0]
        if diretas:
            diretas.sort(key=lambda x: x['metricas']['score'])
            Categorias['direta'] = diretas[0]

        # C) RÁPIDA (Menor Duração)
        rapidas = sorted(candidatos_processados, key=lambda x: x['metricas']['duracao'])
        if rapidas:
            Categorias['rapida'] = rapidas[0]

        # D) ECONÔMICA (Menor Custo)
        # IMPORTANTE: Filtrar as que estão "sem tarifa", pois elas têm custo 0.0
        # Se não filtrar, a rota sem tarifa ganha sempre como "a mais barata".
        economicas = [c for c in candidatos_processados if c['metricas']['custo'] < 10000 and not c['metricas']['sem_tarifa']]
        if economicas:
            economicas.sort(key=lambda x: x['metricas']['custo'])
            Categorias['economica'] = economicas[0]

        # E) COM CONEXÕES (Mesma Cia)
        conexoes_simples = [c for c in candidatos_processados if c['metricas']['escalas'] > 0 and c['metricas']['trocas_cia'] == 0]
        if conexoes_simples:
            conexoes_simples.sort(key=lambda x: x['metricas']['score'])
            Categorias['conexao_mesma_cia'] = conexoes_simples[0]

        # F) INTERLINE (Troca de Cia)
        interline = [c for c in candidatos_processados if c['metricas']['trocas_cia'] > 0]
        if interline:
            interline.sort(key=lambda x: x['metricas']['score'])
            Categorias['interline'] = interline[0]

        return Categorias

    @staticmethod
    def _CalcularScoreAvancado(duracao, custo, conexoes, trocas_cia, indice_parceria, sem_tarifa):
        # Base
        pontos_tempo = duracao * RouteIntelligenceService.PESO_TEMPO
        pontos_conexoes = conexoes * RouteIntelligenceService.PESO_CONEXAO
        pontos_trocas = trocas_cia * 300 
        score_base = pontos_tempo + pontos_conexoes + pontos_trocas
        
        # Financeiro 
        fator_custo = 0
        if sem_tarifa:
            # Aplica a penalidade no SCORE, mas não altera o valor monetário exibido
            fator_custo = RouteIntelligenceService.PENALIDADE_SEM_TARIFA
        elif custo > 14000:
            fator_custo = RouteIntelligenceService.PENALIDADE_SEM_TARIFA
        else:
            fator_custo = float(custo) * RouteIntelligenceService.PESO_CUSTO

        # Parceria
        bonus_parceria = (float(indice_parceria) ** RouteIntelligenceService.FATOR_PARCERIA_POWER) / 50.0
        
        score_final = (score_base + fator_custo) - bonus_parceria
        
        return score_final, ""