import os
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import aliased
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import Aeroporto
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData
import networkx as nx # O segredo do sucesso!

# Pasta temporária
DIR_TEMP = 'Data/Temp_Malhas'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

# --- FUNÇÕES DE CONTROLE DE REMESSAS (Mantidas) ---
def ListarRemessas():
    Sessao = ObterSessaoPostgres()
    try:
        return Sessao.query(RemessaMalha).order_by(desc(RemessaMalha.DataUpload)).all()
    finally:
        Sessao.close()

def ExcluirRemessa(IdRemessa):
    Sessao = ObterSessaoPostgres()
    try:
        RemessaAlvo = Sessao.query(RemessaMalha).get(IdRemessa)
        if RemessaAlvo:
            Sessao.delete(RemessaAlvo)
            Sessao.commit()
            return True, "Remessa excluída com sucesso."
        return False, "Remessa não encontrada."
    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao excluir: {e}"
    finally:
        Sessao.close()

def AnalisarArquivo(FileStorage):
    try:
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        if not ColunaData:
            return False, "Coluna de DATA não encontrada."

        PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
        if not PrimeiraData:
            return False, "Não foi possível ler a data do arquivo."
            
        DataRef = PrimeiraData.replace(day=1) 
        
        Sessao = ObterSessaoPostgres()
        ExisteConflito = False
        try:
            Anterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
            if Anterior:
                ExisteConflito = True
        finally:
            Sessao.close()
            
        return True, {
            'caminho_temp': CaminhoTemp,
            'mes_ref': DataRef,
            'nome_arquivo': FileStorage.filename,
            'conflito': ExisteConflito
        }
    except Exception as e:
        return False, f"Erro ao analisar arquivo: {e}"

def ProcessarMalhaFinal(CaminhoArquivo, DataRef, NomeOriginal, Usuario, TipoAcao):
    Sessao = ObterSessaoPostgres()
    try:
        Df = pd.read_excel(CaminhoArquivo, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        
        Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
        Df = Df.dropna(subset=['DATA_PADRAO'])

        RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if RemessaAnterior:
            RemessaAnterior.Ativo = False

        NovaRemessa = RemessaMalha(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao,
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        ListaVoos = []
        for _, Linha in Df.iterrows():
            try:
                H_Saida = pd.to_datetime(str(Linha['HORÁRIO DE SAIDA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE SAIDA']) != 'nan' else datetime.min.time()
                H_Chegada = pd.to_datetime(str(Linha['HORÁRIO DE CHEGADA']), format='%H:%M:%S', errors='coerce').time() if str(Linha['HORÁRIO DE CHEGADA']) != 'nan' else datetime.min.time()
            except:
                H_Saida = datetime.min.time()
                H_Chegada = datetime.min.time()

            Voo = VooMalha(
                IdRemessa=NovaRemessa.Id,
                CiaAerea=str(Linha['CIA']),
                NumeroVoo=str(Linha['Nº VOO']),
                DataPartida=Linha['DATA_PADRAO'],
                AeroportoOrigem=str(Linha['ORIGEM']),
                HorarioSaida=H_Saida,
                HorarioChegada=H_Chegada,
                AeroportoDestino=str(Linha['DESTINO'])
            )
            ListaVoos.append(Voo)

        Sessao.bulk_save_objects(ListaVoos)
        Sessao.commit()
        
        if os.path.exists(CaminhoArquivo):
            os.remove(CaminhoArquivo)
            
        return True, f"Malha de {DataRef.strftime('%m/%Y')} processada com sucesso! ({TipoAcao})"

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao gravar: {e}"
    finally:
        Sessao.close()

# --- ALGORITMO DE ROTAS INTELIGENTES (GRAFO / NETWORKX) ---

def BuscarRotasInteligentes(DataInicio, DataFim, OrigemIata=None, DestinoIata=None):
    Sessao = ObterSessaoPostgres()
    try:
        OrigemIata = OrigemIata.upper().strip() if OrigemIata else None
        DestinoIata = DestinoIata.upper().strip() if DestinoIata else None
        
        # 1. Carregar Voos do Banco para Memória
        # Trazemos dados do período + 3 dias de margem para conexões
        VoosDB = Sessao.query(
            VooMalha,
            Aeroporto.Latitude, Aeroporto.Longitude, Aeroporto.NomeAeroporto
        ).join(Aeroporto, VooMalha.AeroportoOrigem == Aeroporto.CodigoIata)\
         .filter(VooMalha.DataPartida >= DataInicio, VooMalha.DataPartida <= DataFim + timedelta(days=3))\
         .all()
        
        # Cache de Dados dos Aeroportos (Lat/Lon/Nome)
        # Importante: O join acima traz dados da Origem. 
        # Precisamos garantir que temos dados do Destino também.
        DadosAeroportos = {}
        
        # 2. Montar o Grafo Direcionado (DiGraph)
        G = nx.DiGraph()
        
        # Lista simples para retorno caso não tenha filtro
        ListaGeral = []

        for Voo, Lat, Lon, Nome in VoosDB:
            # Popula Cache de Aeroportos (Origem)
            if Voo.AeroportoOrigem not in DadosAeroportos:
                DadosAeroportos[Voo.AeroportoOrigem] = {'lat': Lat, 'lon': Lon, 'nome': Nome}
            
            # Adiciona Aresta no Grafo
            # Cada voo é uma aresta com atributos (data, horario, objeto_voo)
            # Como NetworkX sobrescreve arestas repetidas, usamos MultiDiGraph ou 
            # gambiarra simples: chave única ou lista de atributos.
            # Aqui vamos usar o ID do voo como chave se for MultiDiGraph, mas para
            # simplificar roteamento, vamos adicionar o objeto voo como dado da aresta.
            
            # ATENÇÃO: NetworkX DiGraph padrão só tem 1 aresta entre dois nós.
            # Se tivermos 5 voos GRU->FOR, ele sobrescreve. 
            # Para roteamento simples (achar caminho), basta saber que EXISTE conexão.
            # Mas queremos os horários. Então vamos construir uma lista de voos na aresta.
            
            if G.has_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino):
                G[Voo.AeroportoOrigem][Voo.AeroportoDestino]['voos'].append(Voo)
            else:
                G.add_edge(Voo.AeroportoOrigem, Voo.AeroportoDestino, voos=[Voo])

            # Lógica Visão Geral (Sem Filtro)
            if not (OrigemIata and DestinoIata):
                # Aplica filtros parciais se houver
                if (not OrigemIata or Voo.AeroportoOrigem == OrigemIata) and \
                   (not DestinoIata or Voo.AeroportoDestino == DestinoIata):
                       # Só adiciona se estiver na data exata pedida (sem margem)
                       if DataInicio <= Voo.DataPartida <= DataFim:
                           ListaGeral.append(Voo)

        # --- ESTRATÉGIA 1: VISÃO GERAL ---
        if not (OrigemIata and DestinoIata):
            # Completa dados de destino que faltam
            CompletarCacheDestinos(Sessao, ListaGeral, DadosAeroportos)
            # Limita retorno
            return FormatarListaRotas(ListaGeral[:5000], DadosAeroportos, 'Geral')

        # --- ESTRATÉGIA 2: BUSCA DE MENOR CAMINHO (Shortest Path) ---
        # Verifica se existe caminho no grafo
        if not G.has_node(OrigemIata) or not G.has_node(DestinoIata):
            return []
            
        try:
            # Encontra todos os caminhos simples (sem repetição de nós) com até 3 saltos (2 conexões)
            # cutoff=3 significa: Origem -> A -> B -> Destino (3 voos)
            CaminhosPossiveis = list(nx.all_simple_paths(G, source=OrigemIata, target=DestinoIata, cutoff=3))
            
            if not CaminhosPossiveis:
                return []
                
            # Agora validamos os horários de cada caminho
            for CaminhoNos in CaminhosPossiveis:
                # CaminhoNos ex: ['CZS', 'RBR', 'BSB', 'FOR']
                
                RotaValida = ValidarCaminhoCronologico(G, CaminhoNos, DataInicio)
                if RotaValida:
                    # Se achou uma rota válida (respeitando conexões), retorna ela!
                    CompletarCacheDestinos(Sessao, RotaValida, DadosAeroportos)
                    Tipo = 'Direto' if len(RotaValida) == 1 else 'Conexao'
                    return FormatarListaRotas(RotaValida, DadosAeroportos, Tipo)
                    
        except nx.NetworkXNoPath:
            return []

        return []

    except Exception as e:
        print(f"Erro Busca: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        Sessao.close()

def ValidarCaminhoCronologico(Grafo, Nos, DataMinima):
    """
    Dado uma sequência de aeroportos (ex: A, B, C), verifica se existem voos
    conectando eles sequencialmente respeitando horários.
    Retorna a lista de objetos Voo se der certo, ou None.
    """
    VoosEscolhidos = []
    DataAtual = DataMinima
    HoraAtual = datetime.min.time() # Começa do zero no primeiro dia
    
    for i in range(len(Nos) - 1):
        Origem = Nos[i]
        Destino = Nos[i+1]
        
        # Pega todos os voos disponíveis nesse trecho
        Candidatos = Grafo[Origem][Destino]['voos']
        
        # Ordena por data/hora para pegar o mais cedo possível
        Candidatos.sort(key=lambda v: (v.DataPartida, v.HorarioSaida))
        
        VooEleito = None
        
        for Voo in Candidatos:
            # Regras de Conexão:
            
            # 1. Se for o primeiro voo da rota
            if i == 0:
                if Voo.DataPartida >= DataAtual:
                    VooEleito = Voo
                    break
            
            # 2. Se for conexão (voo subsequente)
            else:
                # Monta datetimes para comparar precisão
                ChegadaAnterior = datetime.combine(VoosEscolhidos[-1].DataPartida, VoosEscolhidos[-1].HorarioChegada)
                SaidaAtual = datetime.combine(Voo.DataPartida, Voo.HorarioSaida)
                
                # Diferença em horas
                Dif = (SaidaAtual - ChegadaAnterior).total_seconds() / 3600
                
                # Regra: Mínimo 1h, Máximo 24h de espera
                if 1 <= Dif <= 24:
                    VooEleito = Voo
                    break
        
        if VooEleito:
            VoosEscolhidos.append(VooEleito)
            # Atualiza referências para o próximo loop
            DataAtual = VooEleito.DataPartida
        else:
            return None # Quebrou a corrente, esse caminho não serve
            
    return VoosEscolhidos

def CompletarCacheDestinos(Sessao, ListaVoos, Cache):
    """Busca no banco dados de aeroportos de destino que não estejam no cache"""
    IatasFaltantes = set()
    for Voo in ListaVoos:
        if Voo.AeroportoDestino not in Cache:
            IatasFaltantes.add(Voo.AeroportoDestino)
            
    if IatasFaltantes:
        Infos = Sessao.query(Aeroporto).filter(Aeroporto.CodigoIata.in_(IatasFaltantes)).all()
        for Info in Infos:
            Cache[Info.CodigoIata] = {'lat': Info.Latitude, 'lon': Info.Longitude, 'nome': Info.NomeAeroporto}

def FormatarListaRotas(ListaVoos, CacheAeroportos, Tipo):
    Rotas = []
    for Voo in ListaVoos:
        Orig = CacheAeroportos.get(Voo.AeroportoOrigem, {})
        Dest = CacheAeroportos.get(Voo.AeroportoDestino, {})
        
        Sai = Voo.HorarioSaida.strftime('%H:%M') if Voo.HorarioSaida else '--:--'
        Che = Voo.HorarioChegada.strftime('%H:%M') if Voo.HorarioChegada else '--:--'

        Rotas.append({
            'tipo_resultado': Tipo,
            'voo': Voo.NumeroVoo,
            'cia': Voo.CiaAerea.upper().strip(),
            'data': Voo.DataPartida.strftime('%d/%m/%Y'),
            'horario_saida': Sai,
            'horario_chegada': Che,
            'origem': {
                'iata': Voo.AeroportoOrigem, 
                'nome': Orig.get('nome', Voo.AeroportoOrigem), 
                'lat': Orig.get('lat'), 'lon': Orig.get('lon')
            },
            'destino': {
                'iata': Voo.AeroportoDestino, 
                'nome': Dest.get('nome', Voo.AeroportoDestino), 
                'lat': Dest.get('lat'), 'lon': Dest.get('lon')
            }
        })
    return Rotas