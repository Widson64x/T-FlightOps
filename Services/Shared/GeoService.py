from sqlalchemy import distinct
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Cidade import Cidade, RemessaCidade
from Models.SQL_SERVER.Aeroporto import Aeroporto, RemessaAeroportos
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha 
from Utils.Geometria import Haversine
from Utils.Texto import NormalizarTexto
from Services.LogService import LogService

def BuscarCoordenadasCidade(NomeCidade, Uf):
    Sessao = ObterSessaoSqlServer()
    try:
        if not NomeCidade or not Uf: return None
        
        # Normalização para evitar erros de acento (Itajaí vs Itajai)
        NomeBusca = NormalizarTexto(NomeCidade)
        UfBusca = NormalizarTexto(Uf)
        
        # Buscar todas as cidades do estado (Com JOIN para evitar produto cartesiano e erros)
        CidadesDoEstado = Sessao.query(Cidade)\
            .join(RemessaCidade)\
            .filter(RemessaCidade.Ativo == True) \
            .filter(Cidade.Uf == UfBusca).all()
        
        for c in CidadesDoEstado:
            NomeBanco = NormalizarTexto(c.NomeCidade)
            if NomeBanco == NomeBusca or NomeBusca in NomeBanco:
                return {
                    'lat': float(c.Latitude) if c.Latitude else 0.0, 
                    'lon': float(c.Longitude) if c.Longitude else 0.0, 
                    'nome': c.NomeCidade,
                    'uf': c.Uf
                }
        return None
    except Exception as e:
        LogService.Error("GeoService", f"Erro ao buscar cidade {NomeCidade}-{Uf}", e)
        return None
    finally:
        Sessao.close()

def BuscarAeroportoMaisProximo(Lat, Lon):
    """
    Busca o aeroporto mais próximo que TENHA VOOS NA MALHA ATIVA.
    """
    Sessao = ObterSessaoSqlServer()
    try:
        # 1. Lista de aeroportos que realmente operam (têm voos saindo) NA MALHA ATIVA
        AeroportosAtivos = Sessao.query(distinct(VooMalha.AeroportoOrigem))\
            .join(RemessaMalha)\
            .filter(RemessaMalha.Ativo == True)\
            .all()
            
        ListaIatasAtivos = [a[0] for a in AeroportosAtivos]

        if not ListaIatasAtivos:
            # Se não tem malha ativa, não retorna nenhum aeroporto como "ativo"
            return None
        else:
            # Busca dados geográficos apenas dos aeroportos ativos
            TodosAeroportos = Sessao.query(
                Aeroporto.CodigoIata, 
                Aeroporto.Latitude, 
                Aeroporto.Longitude, 
                Aeroporto.NomeAeroporto
            ).join(RemessaAeroportos)\
            .filter(RemessaAeroportos.Ativo == True)\
            .filter(
                Aeroporto.Latitude != None,
                Aeroporto.CodigoIata.in_(ListaIatasAtivos)
            ).all()
        
        MenorDistancia = float('inf')
        AeroportoEscolhido = None
        
        for Aero in TodosAeroportos:
            Dist = Haversine(Lat, Lon, float(Aero.Latitude), float(Aero.Longitude))
            
            if Dist < MenorDistancia:
                MenorDistancia = Dist
                AeroportoEscolhido = {
                    'iata': Aero.CodigoIata,
                    'nome': Aero.NomeAeroporto,
                    'lat': float(Aero.Latitude),
                    'lon': float(Aero.Longitude),
                    'distancia_km': round(Dist, 1)
                }
        
        if AeroportoEscolhido:
            LogService.Debug("GeoService", f"Aeroporto mais próximo: {AeroportoEscolhido['iata']} ({AeroportoEscolhido['distancia_km']}km)")
            
        return AeroportoEscolhido
    except Exception as e:
        LogService.Error("GeoService", "Erro ao buscar aeroporto mais próximo", e)
        return None
    finally:
        Sessao.close()

def BuscarTopAeroportos(lat_cidade, lon_cidade, limite=2):
    """
    Retorna uma lista com os 'limite' aeroportos mais próximos (Ativos).
    Retorna lista de dicts: [{'iata': 'GRU', 'distancia': 25.5, ...}, ...]
    """
    Sessao = ObterSessaoSqlServer()
    try:
        # CORREÇÃO: Faz join com RemessaAeroportos e filtra RemessaAeroportos.Ativo
        aeroportos = Sessao.query(Aeroporto)\
            .join(RemessaAeroportos)\
            .filter(
                RemessaAeroportos.Ativo == True,
                Aeroporto.Latitude != None,
                Aeroporto.Longitude != None
            ).all()
        
        lista_distancias = []
        
        for aero in aeroportos:
            # Usa Haversine interno
            dist = Haversine(lat_cidade, lon_cidade, float(aero.Latitude), float(aero.Longitude))
            
            lista_distancias.append({
                'iata': aero.CodigoIata,
                'nome': aero.NomeAeroporto,
                'lat': float(aero.Latitude),
                'lon': float(aero.Longitude),
                'distancia': dist
            })

        # Ordena pela distância (menor para maior)
        lista_distancias.sort(key=lambda x: x['distancia'])
        
        # Retorna os Top X (ex: Top 2)
        return lista_distancias[:limite]

    except Exception as e:
        LogService.Error("GeoService", "Erro ao buscar Top Aeroportos", e)
        return []
    finally:
        Sessao.close()