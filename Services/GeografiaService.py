from sqlalchemy import distinct
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Cidade import Cidade
from Models.POSTGRES.Aeroporto import Aeroporto
from Models.POSTGRES.MalhaAerea import VooMalha
from Utils.Geometria import Haversine
from Utils.Texto import NormalizarTexto

def BuscarCoordenadasCidade(NomeCidade, Uf):
    Sessao = ObterSessaoPostgres()
    try:
        if not NomeCidade or not Uf: return None
        
        # Normalização para evitar erros de acento (Itajaí vs Itajai)
        NomeBusca = NormalizarTexto(NomeCidade)
        UfBusca = NormalizarTexto(Uf)

        CidadesDoEstado = Sessao.query(Cidade).filter(Cidade.Uf == UfBusca).all()
        
        for c in CidadesDoEstado:
            NomeBanco = NormalizarTexto(c.NomeCidade)
            if NomeBanco == NomeBusca or NomeBusca in NomeBanco:
                return {
                    'lat': c.Latitude, 
                    'lon': c.Longitude, 
                    'nome': c.NomeCidade,
                    'uf': c.Uf
                }
        return None
    finally:
        Sessao.close()

def BuscarAeroportoMaisProximo(Lat, Lon):
    """
    Busca o aeroporto mais próximo que TENHA VOOS na malha.
    Ignora aeroportos fantasmas (ex: GYA) que travam a busca.
    """
    Sessao = ObterSessaoPostgres()
    try:
        # 1. Lista de aeroportos que realmente operam (têm voos saindo)
        # Isso evita pegar aeroportos da Bolívia ou pistas de pouso sem rota
        AeroportosAtivos = Sessao.query(distinct(VooMalha.AeroportoOrigem)).all()
        ListaIatasAtivos = [a[0] for a in AeroportosAtivos]

        if not ListaIatasAtivos:
            # Fallback se a tabela de voos estiver vazia
            print("⚠️ Tabela de VooMalha vazia. Usando todos os aeroportos.")
            TodosAeroportos = Sessao.query(Aeroporto).all()
        else:
            # Busca apenas aeroportos que existem na malha ativa
            TodosAeroportos = Sessao.query(
                Aeroporto.CodigoIata, 
                Aeroporto.Latitude, 
                Aeroporto.Longitude, 
                Aeroporto.NomeAeroporto
            ).filter(
                Aeroporto.Latitude != None,
                Aeroporto.CodigoIata.in_(ListaIatasAtivos) # O Pulo do Gato
            ).all()
        
        MenorDistancia = float('inf')
        AeroportoEscolhido = None
        
        for Aero in TodosAeroportos:
            Dist = Haversine(Lat, Lon, Aero.Latitude, Aero.Longitude)
            
            # Prioriza aeroportos num raio aceitável (ex: até 600km)
            # Se for muito longe, continua buscando o menor
            if Dist < MenorDistancia:
                MenorDistancia = Dist
                AeroportoEscolhido = {
                    'iata': Aero.CodigoIata,
                    'nome': Aero.NomeAeroporto,
                    'lat': Aero.Latitude,
                    'lon': Aero.Longitude,
                    'distancia_km': round(Dist, 1)
                }
        
        if AeroportoEscolhido:
            print(f"📍 Aeroporto Ativo mais próximo: {AeroportoEscolhido['iata']} ({AeroportoEscolhido['distancia_km']}km)")
            
        return AeroportoEscolhido
    finally:
        Sessao.close()