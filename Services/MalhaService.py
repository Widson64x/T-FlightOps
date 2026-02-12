import os
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta, date, time
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Utils.Formatadores import PadronizarData
from Models.SQL_SERVER.Aeroporto import Aeroporto
from Models.SQL_SERVER.MalhaAerea import RemessaMalha, VooMalha
from Services.TabelaFreteService import TabelaFreteService
from Services.CiaAereaService import CiaAereaService
from Services.LogService import LogService
from Services.Logic.RouteIntelligenceService import RouteIntelligenceService
from Configuracoes import ConfiguracaoBase

class MalhaService:
    
    DIR_TEMP = ConfiguracaoBase.DIR_TEMP
    
    # --- MÉTODOS DE GESTÃO (CRUD) ---

    @staticmethod
    def ListarRemessas():
        """Lista histórico de importações de malha."""
        Sessao = ObterSessaoSqlServer()
        try:
            return Sessao.query(RemessaMalha).order_by(desc(RemessaMalha.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        """Realiza a exclusão lógica ou física de uma remessa e seus voos associados."""
        Sessao = ObterSessaoSqlServer()
        try:
            RemessaAlvo = Sessao.query(RemessaMalha).get(id_remessa)
            if RemessaAlvo:
                Sessao.delete(RemessaAlvo)
                Sessao.commit()
                LogService.Info("MalhaService", f"Remessa ID {id_remessa} excluída com sucesso.")
                return True, "Remessa excluída com sucesso."
            
            LogService.Warning("MalhaService", f"Tentativa de excluir remessa inexistente ID {id_remessa}.")
            return False, "Remessa não encontrada."
        except Exception as e:
            Sessao.rollback()
            LogService.Error("MalhaService", f"Erro técnico ao excluir remessa ID {id_remessa}", e)
            return False, f"Erro técnico ao excluir: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def AnalisarArquivo(file_storage):
        """
        Analisa a integridade do arquivo enviado e verifica conflitos de vigência.
        Retorna metadados para confirmação do usuário.
        """
        try:
            LogService.Info("MalhaService", f"Iniciando análise do arquivo: {file_storage.filename}")
            MalhaService._GarantirDiretorio()
            CaminhoTemp = os.path.join(MalhaService.DIR_TEMP, file_storage.filename)
            file_storage.save(CaminhoTemp)
            
            Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
            Df.columns = [c.strip().upper() for c in Df.columns]
            
            ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
            if not ColunaData:
                LogService.Warning("MalhaService", "Arquivo rejeitado: Coluna de DATA não encontrada.")
                return False, "Coluna de DATA não encontrada no arquivo."

            PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
            if not PrimeiraData:
                LogService.Warning("MalhaService", "Arquivo rejeitado: Falha ao analisar formato de data.")
                return False, "Falha ao analisar formato de data."
            
            # Define o primeiro dia do mês como referência
            DataRef = PrimeiraData.replace(day=1) 
            
            Sessao = ObterSessaoSqlServer()
            ExisteConflito = False
            try:
                Anterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
                if Anterior:
                    ExisteConflito = True
                    LogService.Info("MalhaService", f"Conflito detectado para mês referência: {DataRef}")
            finally:
                Sessao.close()
                
            return True, {
                'caminho_temp': CaminhoTemp,
                'mes_ref': DataRef,
                'nome_arquivo': file_storage.filename,
                'conflito': ExisteConflito
            }
        except Exception as e:
            LogService.Error("MalhaService", "Exceção durante análise do arquivo", e)
            return False, f"Exceção durante análise do arquivo: {e}"

    @staticmethod
    def ProcessarMalhaFinal(caminho_arquivo, data_ref, nome_original, usuario, tipo_acao):
        """
        Processa o arquivo validado e persiste os voos no banco de dados.
        Realiza a substituição de malha anterior caso necessário.
        """
        LogService.Info("MalhaService", f"Iniciando processamento final ({tipo_acao}) para {data_ref}")
        Sessao = ObterSessaoSqlServer()
        try:
            Df = pd.read_excel(caminho_arquivo, engine='openpyxl')
            Df.columns = [c.strip().upper() for c in Df.columns]
            ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
            
            Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
            Df = Df.dropna(subset=['DATA_PADRAO'])

            # Desativa remessa anterior
            RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=data_ref, Ativo=True).first()
            if RemessaAnterior:
                RemessaAnterior.Ativo = False

            NovaRemessa = RemessaMalha(
                MesReferencia=data_ref,
                NomeArquivoOriginal=nome_original,
                UsuarioResponsavel=usuario,
                TipoAcao=tipo_acao,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            ListaVoos = []
            for _, Linha in Df.iterrows():
                try:
                    # Tratamento de Horário
                    raw_saida = str(Linha.get('HORÁRIO DE SAIDA', ''))
                    raw_chegada = str(Linha.get('HORÁRIO DE CHEGADA', ''))
                    
                    if len(raw_saida) == 5: raw_saida += ":00"
                    if len(raw_chegada) == 5: raw_chegada += ":00"

                    H_Saida = pd.to_datetime(raw_saida, format='%H:%M:%S', errors='coerce').time() if raw_saida != 'nan' else time(0,0)
                    H_Chegada = pd.to_datetime(raw_chegada, format='%H:%M:%S', errors='coerce').time() if raw_chegada != 'nan' else time(0,0)
                except:
                    H_Saida = time(0,0)
                    H_Chegada = time(0,0)

                Voo = VooMalha(
                    IdRemessa=NovaRemessa.Id,
                    CiaAerea=str(Linha.get('CIA', '')),
                    NumeroVoo=str(Linha.get('Nº VOO', '')),
                    DataPartida=Linha['DATA_PADRAO'],
                    AeroportoOrigem=str(Linha.get('ORIGEM', '')).strip().upper(),
                    HorarioSaida=H_Saida,
                    HorarioChegada=H_Chegada,
                    AeroportoDestino=str(Linha.get('DESTINO', '')).strip().upper()
                )
                ListaVoos.append(Voo)

            Sessao.bulk_save_objects(ListaVoos)
            Sessao.commit()
            
            LogService.Info("MalhaService", f"Malha processada com sucesso. {len(ListaVoos)} voos importados.")
            
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
                
            return True, "Malha processada e persistida com sucesso."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("MalhaService", "Erro de persistência na Malha", e)
            return False, f"Erro de persistência: {e}"
        finally:
            Sessao.close()

    @staticmethod
    def _GarantirDiretorio():
        if not os.path.exists(MalhaService.DIR_TEMP):
            os.makedirs(MalhaService.DIR_TEMP)

    @staticmethod
    def BuscarOpcoesDeRotas(data_inicio, data_fim, lista_origens, lista_destinos, peso_total=100.0):
        """
        Retorna dicionário expandido com as novas categorias.
        """
        Sessao = ObterSessaoSqlServer()
        ResultadosFormatados = {
            'recomendada': [], 
            'direta': [],
            'rapida': [], 
            'economica': [], 
            'conexao_mesma_cia': [],
            'interline': []
        }
        
        if isinstance(lista_origens, str): lista_origens = [lista_origens]
        if isinstance(lista_destinos, str): lista_destinos = [lista_destinos]

        lista_origens = [o.strip().upper() for o in lista_origens]
        lista_destinos = [d.strip().upper() for d in lista_destinos]

        try:
            LogService.Warning("MalhaService", f"=== BUSCA INTELIGENTE INICIADA ===")
            FiltroDataInicio = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
            FiltroDataFim = data_fim.date() if isinstance(data_fim, datetime) else data_fim
            
            # 1. Busca no Banco
            VoosDB = Sessao.query(VooMalha).join(RemessaMalha).filter(
                    RemessaMalha.Ativo == True,
                    VooMalha.DataPartida >= FiltroDataInicio, 
                    VooMalha.DataPartida <= FiltroDataFim + timedelta(days=5) 
                ).all()

            if not VoosDB: 
                LogService.Error("MalhaDebug", "[CRÍTICO] Nenhum voo encontrado no banco para este período/remessa ativa.")
                return ResultadosFormatados
            
            # 2. Montagem do Grafo
            G = nx.DiGraph()
            for Voo in VoosDB:
                OrigemNo = Voo.AeroportoOrigem.strip().upper()
                DestinoNo = Voo.AeroportoDestino.strip().upper()

                if G.has_edge(OrigemNo, DestinoNo):
                    G[OrigemNo][DestinoNo]['voos'].append(Voo)
                else:
                    G.add_edge(OrigemNo, DestinoNo, voos=[Voo])
            
            ListaCandidatos = []
            ScoresParceria = CiaAereaService.ObterDicionarioScores()

            # 3. Processamento de Rotas
            for origem_iata in lista_origens:
                for destino_iata in lista_destinos:
                    
                    if not G.has_node(origem_iata) or not G.has_node(destino_iata):
                        continue 

                    try:
                        CaminhosNos = list(nx.all_simple_paths(G, source=origem_iata, target=destino_iata, cutoff=3))
                    except Exception as e: 
                        LogService.Error("MalhaDebug", f"Erro no algoritmo nx.all_simple_paths para {origem_iata}->{destino_iata}", e)
                        continue 

                    if not CaminhosNos: continue

                    # CHECK 3: Validação de Horários (Cronologia)
                    for Caminho in CaminhosNos:
                        SequenciaVoos = MalhaService._ValidarCaminhoCronologico(G, Caminho, data_inicio)
                        
                        if not SequenciaVoos: continue
                        
                        # --- Processamento da Rota Válida ---
                        Duracao = MalhaService._CalcularDuracaoRota(SequenciaVoos)
                        TrocasCia = MalhaService._ContarTrocasCia(SequenciaVoos)
                        QtdEscalas = len(SequenciaVoos) - 1
                        CustoTotal = 0.0
                        ScoreParceriaAcumulado = 0 
                        SemTarifaFlag = False
                        DetalhesTarifarios = []
                        IdRota = "->".join(Caminho)
                        
                        for i, v in enumerate(SequenciaVoos):
                            c, info_frete = TabelaFreteService.CalcularCustoEstimado(v.AeroportoOrigem, v.AeroportoDestino, v.CiaAerea, peso_total)
                            
                            # AQUI MUDOU: Verifica a flag retornada pelo serviço
                            if info_frete.get('tarifa_missing', False):
                                SemTarifaFlag = True
                                LogService.Warning("MalhaDebug", f"[TARIFACAO MISS] {IdRota} Trecho {i+1} ({v.CiaAerea}): Penalidade Virtual")
                            
                            # 'c' agora é 0.0 se não tiver tarifa, então CustoTotal não explode visualmente
                            info_frete['custo_calculado'] = c
                            CustoTotal += c
                            DetalhesTarifarios.append(info_frete)
                            ScoreParceriaAcumulado += ScoresParceria.get(v.CiaAerea.strip().upper(), 50)
                        
                        MediaParceria = ScoreParceriaAcumulado / len(SequenciaVoos) if len(SequenciaVoos) > 0 else 50
                        
                        ListaCandidatos.append({
                            'rota': SequenciaVoos,
                            'detalhes_tarifas': DetalhesTarifarios,
                            'metricas': {
                                'duracao': Duracao, 
                                'custo': CustoTotal, 
                                'escalas': QtdEscalas, 
                                'trocas_cia': TrocasCia, 
                                'indice_parceria': MediaParceria,
                                'sem_tarifa': SemTarifaFlag, # Flag repassada para Intelligence
                                'score': 0
                            }
                        })
                    
            if not ListaCandidatos: 
                LogService.Warning("MalhaDebug", "Finalizado sem candidatos válidos.")
                return ResultadosFormatados

            # 4. Inteligência
            LogService.Info("MalhaDebug", f"Aplicando Inteligência em {len(ListaCandidatos)} candidatos...")
            OpcoesBrutas = RouteIntelligenceService.OtimizarOpcoes(ListaCandidatos)

            # 5. Formatação e Cache
            DadosAeroportos = {}
            VoosParaCache = []
            for cat, val in OpcoesBrutas.items():
                if val: VoosParaCache.extend(val['rota'])
            
            MalhaService._CompletarCacheDestinos(Sessao, VoosParaCache, DadosAeroportos)

            def formatar_candidato(candidato, tag):
                if not candidato: return []
                return MalhaService._FormatarListaRotas(candidato['rota'], DadosAeroportos, tag, candidato['metricas'], candidato['detalhes_tarifas'])

            ResultadosFormatados['recomendada'] = formatar_candidato(OpcoesBrutas.get('recomendada'), 'Recomendada')
            ResultadosFormatados['direta'] = formatar_candidato(OpcoesBrutas.get('direta'), 'Voo Direto')
            ResultadosFormatados['rapida'] = formatar_candidato(OpcoesBrutas.get('rapida'), 'Mais Rápida')
            ResultadosFormatados['economica'] = formatar_candidato(OpcoesBrutas.get('economica'), 'Mais Econômica')
            ResultadosFormatados['conexao_mesma_cia'] = formatar_candidato(OpcoesBrutas.get('conexao_mesma_cia'), 'Conexão (Mesma Cia)')
            ResultadosFormatados['interline'] = formatar_candidato(OpcoesBrutas.get('interline'), 'Interline (Múltiplas Cias)')

            LogService.Info("MalhaDebug", "Busca finalizada com sucesso. Retornando dados.")
            return ResultadosFormatados

        except Exception as e:
            LogService.Error("MalhaService", "ERRO CRÍTICO em BuscarOpcoesDeRotas", e)
            import traceback
            LogService.Error("MalhaService", traceback.format_exc()) # Adiciona Traceback completo no log
            return ResultadosFormatados
        finally:
            Sessao.close()

    @staticmethod
    def _ValidarCaminhoCronologico(Grafo, ListaNos, DataInicio):
        VoosEscolhidos = []
        MomentoDisponivel = DataInicio if isinstance(DataInicio, datetime) else datetime.combine(DataInicio, time.min)
        for i in range(len(ListaNos) - 1):
            Origem, Destino = ListaNos[i], ListaNos[i+1]
            if Destino not in Grafo[Origem]: return None
            OpcoesVoos = sorted(Grafo[Origem][Destino]['voos'][:], key=lambda v: (v.DataPartida, v.HorarioSaida))
            CiaPreferida = VoosEscolhidos[-1].CiaAerea if VoosEscolhidos else None
            if CiaPreferida: OpcoesVoos = [v for v in OpcoesVoos if v.CiaAerea == CiaPreferida] + [v for v in OpcoesVoos if v.CiaAerea != CiaPreferida]
            VooViavel = None
            for Voo in OpcoesVoos:
                SaidaVoo = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                if i == 0:
                    if SaidaVoo >= MomentoDisponivel: VooViavel = Voo; break
                else:
                    ChegadaAnt = datetime.combine(VoosEscolhidos[-1].DataPartida, VoosEscolhidos[-1].HorarioChegada)
                    if VoosEscolhidos[-1].HorarioChegada < VoosEscolhidos[-1].HorarioSaida: ChegadaAnt += timedelta(days=1)
                    if SaidaVoo >= ChegadaAnt + timedelta(hours=1) and SaidaVoo <= ChegadaAnt + timedelta(hours=48): VooViavel = Voo; break
            if VooViavel:
                VoosEscolhidos.append(VooViavel)
                ChegadaVoo = datetime.combine(VooViavel.DataPartida, VooViavel.HorarioChegada)
                if VooViavel.HorarioChegada < VooViavel.HorarioSaida: ChegadaVoo += timedelta(days=1)
                MomentoDisponivel = ChegadaVoo
            else: return None
        return VoosEscolhidos

    @staticmethod
    def _CalcularDuracaoRota(ListaVoos):
        if not ListaVoos: return 0
        Primeiro, Ultimo = ListaVoos[0], ListaVoos[-1]
        Inicio = datetime.combine(Primeiro.DataPartida, Primeiro.HorarioSaida)
        Fim = datetime.combine(Ultimo.DataPartida, Ultimo.HorarioChegada)
        if Ultimo.HorarioChegada < Ultimo.HorarioSaida: Fim += timedelta(days=1)
        while Fim < Inicio: Fim += timedelta(days=1)
        return (Fim - Inicio).total_seconds() / 60

    @staticmethod
    def _ContarTrocasCia(ListaVoos):
        if not ListaVoos: return 0
        return sum(1 for i in range(len(ListaVoos)-1) if ListaVoos[i].CiaAerea != ListaVoos[i+1].CiaAerea)

    @staticmethod
    def _CompletarCacheDestinos(Sessao, ListaVoos, Cache):
        Iatas = set()
        for v in ListaVoos:
            Iatas.add(v.AeroportoOrigem); Iatas.add(v.AeroportoDestino)
        Faltantes = [i for i in Iatas if i not in Cache]
        if Faltantes:
            for a in Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(Faltantes)).all():
                Cache[a.CodigoIata] = {'nome': a.NomeAeroporto, 'lat': float(a.Latitude or 0), 'lon': float(a.Longitude or 0)}

    @staticmethod
    def _FormatarListaRotas(ListaVoos, Cache, Tipo, Metricas=None, DetalhesTarifas=None):
        Resultado = []
        InfoAdicional = {}
        if Metricas:
            seg = int(Metricas['duracao'] * 60)
            dias, resto = divmod(seg, 86400)
            horas, mins = divmod(resto, 3600); mins //= 60
            duracao_fmt = f"{dias}d {horas:02}:{mins:02}" if dias > 0 else f"{horas:02}:{mins:02}"
            custo_fmt = f"R$ {Metricas['custo']:,.2f}"
            InfoAdicional = {'total_duracao': duracao_fmt, 'total_custo': custo_fmt, 'total_custo_fmt': custo_fmt, 'total_custo_raw': Metricas['custo']}
        for i, Voo in enumerate(ListaVoos):
            Orig = Cache.get(Voo.AeroportoOrigem, {'nome': Voo.AeroportoOrigem})
            Dest = Cache.get(Voo.AeroportoDestino, {'nome': Voo.AeroportoDestino})
            dados_frete = DetalhesTarifas[i] if DetalhesTarifas and i < len(DetalhesTarifas) else {}
            custo_trecho = dados_frete.get('custo_calculado', 0.0)
            Resultado.append({
                'tipo_resultado': Tipo,
                'cia': Voo.CiaAerea.strip(),
                'voo': Voo.NumeroVoo,
                'data': Voo.DataPartida.strftime('%d/%m/%Y'),
                'horario_saida': Voo.HorarioSaida.strftime('%H:%M'),
                'horario_chegada': Voo.HorarioChegada.strftime('%H:%M'),
                'origem': {'iata': Voo.AeroportoOrigem, 'nome': Orig.get('nome'), 'lat': Orig.get('lat'), 'lon': Orig.get('lon')},
                'destino': {'iata': Voo.AeroportoDestino, 'nome': Dest.get('nome'), 'lat': Dest.get('lat'), 'lon': Dest.get('lon')},
                'base_calculo': {
                    'tarifa': dados_frete.get('tarifa_base', 0.0),
                    'servico': dados_frete.get('servico', 'STANDARD'),
                    'cia_tabela': dados_frete.get('cia_tarifaria', Voo.CiaAerea),
                    'peso_usado': dados_frete.get('peso_calculado', 0),
                    'custo_trecho': custo_trecho,
                    'custo_trecho_fmt': f"R$ {custo_trecho:,.2f}"
                },
                **InfoAdicional
            })
        return Resultado