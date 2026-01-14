import os
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy import desc
from sqlalchemy.orm import aliased
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import Aeroporto
from Models.POSTGRES.MalhaAerea import RemessaMalha, VooMalha
from Utils.Formatadores import PadronizarData
from Utils.Geometria import Haversine

# Pasta temporária para guardar o arquivo enquanto o usuário confirma
DIR_TEMP = 'Data/Temp_Malhas'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

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
    """
    Passo 1: Salva o arquivo temporariamente, lê a data e verifica se já existe malha ativa.
    Retorna: (Status, InfoDict ou MensagemErro)
    """
    try:
        # Salva em pasta temporária
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        # Lê o Excel
        Df = pd.read_excel(CaminhoTemp, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        if not ColunaData:
            return False, "Coluna de DATA não encontrada."

        # Pega a primeira data válida para definir o mês
        PrimeiraData = PadronizarData(Df[ColunaData].iloc[0])
        if not PrimeiraData:
            return False, "Não foi possível ler a data do arquivo."
            
        DataRef = PrimeiraData.replace(day=1) # 01/MM/YYYY
        
        # Verifica conflito no Banco
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
    """
    Passo 2: Efetiva a gravação no banco (Desativa anterior e Insere nova).
    """
    Sessao = ObterSessaoPostgres()
    try:
        # Lê novamente do temp
        Df = pd.read_excel(CaminhoArquivo, engine='openpyxl')
        Df.columns = [c.strip().upper() for c in Df.columns]
        ColunaData = next((col for col in ['DIA', 'DATA'] if col in Df.columns), None)
        
        # Aplica padronização em tudo
        Df['DATA_PADRAO'] = Df[ColunaData].apply(PadronizarData)
        Df = Df.dropna(subset=['DATA_PADRAO'])

        # Se for Substituição ou Importação nova, desativa a anterior (Garante integridade)
        RemessaAnterior = Sessao.query(RemessaMalha).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if RemessaAnterior:
            RemessaAnterior.Ativo = False

        # Cria Nova Remessa
        NovaRemessa = RemessaMalha(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao, # <--- Gravamos se foi Importação ou Substituição
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        # Insere Voos (Mesma lógica de antes)
        ListaVoos = []
        for _, Linha in Df.iterrows():
             # ... (Lógica de horários igual à anterior) ...
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
        
        # Limpa arquivo temporário
        if os.path.exists(CaminhoArquivo):
            os.remove(CaminhoArquivo)
            
        return True, f"Malha de {DataRef.strftime('%m/%Y')} processada com sucesso! ({TipoAcao})"

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro ao gravar: {e}"
    finally:
        Sessao.close()
        
def BuscarRotasInteligentes(DataInicio, DataFim, OrigemIata=None, DestinoIata=None):
    Sessao = ObterSessaoPostgres()
    try:
        OrigemIata = OrigemIata.upper().strip() if OrigemIata else None
        DestinoIata = DestinoIata.upper().strip() if DestinoIata else None
        
        # Aliases
        AeroOrigem = aliased(Aeroporto)
        AeroDestino = aliased(Aeroporto)

        # --- CENÁRIO 1: VISÃO GERAL (Sem filtros ou filtro parcial) ---
        if not (OrigemIata and DestinoIata):
            Query = Sessao.query(
                VooMalha,
                AeroOrigem.Latitude.label('LatOrigem'),
                AeroOrigem.Longitude.label('LonOrigem'),
                AeroOrigem.NomeAeroporto.label('NomeOrigem'),
                AeroDestino.Latitude.label('LatDestino'),
                AeroDestino.Longitude.label('LonDestino'),
                AeroDestino.NomeAeroporto.label('NomeDestino')
            ).join(AeroOrigem, VooMalha.AeroportoOrigem == AeroOrigem.CodigoIata)\
             .join(AeroDestino, VooMalha.AeroportoDestino == AeroDestino.CodigoIata)\
             .filter(VooMalha.DataPartida >= DataInicio, VooMalha.DataPartida <= DataFim)

            if OrigemIata: Query = Query.filter(VooMalha.AeroportoOrigem == OrigemIata)
            if DestinoIata: Query = Query.filter(VooMalha.AeroportoDestino == DestinoIata)
            
            # Limite de segurança
            Resultados = Query.limit(5000).all()
            print(f"--> Mapa Geral: Encontrados {len(Resultados)} voos.")
            return FormatarListaRotas(Resultados, Tipo='Geral')

        # --- CENÁRIO 2: BUSCA VOO DIRETO ---
        # AQUI ESTAVA O ERRO: Faltava buscar os nomes na query específica
        # Adicionamos NomeOrigem e NomeDestino
        Diretos = Sessao.query(
            VooMalha,
            AeroOrigem.Latitude.label('LatOrigem'),
            AeroOrigem.Longitude.label('LonOrigem'),
            AeroOrigem.NomeAeroporto.label('NomeOrigem'),  # <--- ADICIONADO
            AeroDestino.Latitude.label('LatDestino'),
            AeroDestino.Longitude.label('LonDestino'),
            AeroDestino.NomeAeroporto.label('NomeDestino') # <--- ADICIONADO
        ).join(AeroOrigem, VooMalha.AeroportoOrigem == AeroOrigem.CodigoIata)\
         .join(AeroDestino, VooMalha.AeroportoDestino == AeroDestino.CodigoIata)\
         .filter(
             VooMalha.AeroportoOrigem == OrigemIata,
             VooMalha.AeroportoDestino == DestinoIata,
             VooMalha.DataPartida >= DataInicio, 
             VooMalha.DataPartida <= DataFim
         ).all()

        if Diretos:
            return FormatarListaRotas(Diretos, Tipo='Direto')

        # --- CENÁRIO 3: BUSCA CONEXÃO (Se não achou direto) ---
        # Se não achou direto, tenta conexão nos próximos 3 dias
        DataLimite = DataFim + timedelta(days=3)
        RotaConexao = BuscarConexaoSQL(Sessao, OrigemIata, DestinoIata, DataInicio, DataLimite)
        
        if RotaConexao:
            return RotaConexao
        
        return []

    except Exception as e:
        print(f"Erro Busca: {e}")
        return []
    finally:
        Sessao.close()

def BuscarConexaoSQL(Sessao, Origem, Destino, DataIni, DataFim):
    """
    Busca conexão com JOIN no próprio banco.
    """
    V1 = aliased(VooMalha)
    V2 = aliased(VooMalha)
    AeroO = aliased(Aeroporto)
    AeroH = aliased(Aeroporto)
    AeroD = aliased(Aeroporto)
    
    # Query de Conexão (Atualizada para pegar nomes também)
    Resultado = Sessao.query(
        V1, V2, 
        AeroO.Latitude, AeroO.Longitude, AeroO.NomeAeroporto, # Origem
        AeroH.Latitude, AeroH.Longitude, AeroH.NomeAeroporto, # Hub
        AeroD.Latitude, AeroD.Longitude, AeroD.NomeAeroporto  # Destino
    ).join(V2, V1.AeroportoDestino == V2.AeroportoOrigem) \
     .join(AeroO, V1.AeroportoOrigem == AeroO.CodigoIata) \
     .join(AeroH, V1.AeroportoDestino == AeroH.CodigoIata) \
     .join(AeroD, V2.AeroportoDestino == AeroD.CodigoIata) \
     .filter(
         V1.AeroportoOrigem == Origem,
         V2.AeroportoDestino == Destino,
         V1.DataPartida >= DataIni,
         V1.DataPartida <= DataFim,
         or_(
             (V2.DataPartida == V1.DataPartida) & (V2.HorarioSaida > V1.HorarioChegada),
             (V2.DataPartida == V1.DataPartida + timedelta(days=1))
         )
     ).order_by(V1.DataPartida, V1.HorarioSaida).first()

    if Resultado:
        # Unpack seguro com nomes (agora temos 11 variáveis na query)
        ObjV1, ObjV2, LatO, LonO, NomeO, LatH, LonH, NomeH, LatD, LonD, NomeD = Resultado
        
        # Verifica tempo de conexão (Mínimo 1h)
        from datetime import datetime
        # Tratamento para evitar erro se Horario for None
        if not ObjV1.HorarioChegada or not ObjV2.HorarioSaida:
             return []

        ChegadaV1 = datetime.combine(ObjV1.DataPartida, ObjV1.HorarioChegada)
        SaidaV2 = datetime.combine(ObjV2.DataPartida, ObjV2.HorarioSaida)
        Diferenca = (SaidaV2 - ChegadaV1).total_seconds() / 3600
        
        if Diferenca >= 1:
            Rotas = []
            # Passando nomes para o montador
            Rotas.append(MontarObjetoRota(ObjV1, LatO, LonO, NomeO, LatH, LonH, NomeH, 'Conexao'))
            Rotas.append(MontarObjetoRota(ObjV2, LatH, LonH, NomeH, LatD, LonD, NomeD, 'Conexao'))
            return Rotas
    return []

def FormatarListaRotas(DadosBrutos, Tipo):
    Rotas = []
    for Row in DadosBrutos:
        # Agora sim espera 7 valores em todos os casos (Direto e Geral)
        if len(Row) == 7:
            Voo, LatO, LonO, NomeO, LatD, LonD, NomeD = Row
            
            Sai = Voo.HorarioSaida.strftime('%H:%M') if Voo.HorarioSaida else '--:--'
            Che = Voo.HorarioChegada.strftime('%H:%M') if Voo.HorarioChegada else '--:--'

            Rotas.append({
                'tipo_resultado': Tipo,
                'voo': Voo.NumeroVoo,
                'cia': Voo.CiaAerea.upper().strip(),
                'data': Voo.DataPartida.strftime('%d/%m/%Y'),
                'horario_saida': Sai,
                'horario_chegada': Che,
                'origem': {'iata': Voo.AeroportoOrigem, 'nome': NomeO, 'lat': LatO, 'lon': LonO},
                'destino': {'iata': Voo.AeroportoDestino, 'nome': NomeD, 'lat': LatD, 'lon': LonD}
            })
    return Rotas

def MontarObjetoRota(Voo, LatO, LonO, NomeO, LatD, LonD, NomeD, Tipo):
    """Auxiliar para conexões"""
    Sai = Voo.HorarioSaida.strftime('%H:%M') if Voo.HorarioSaida else '--:--'
    Che = Voo.HorarioChegada.strftime('%H:%M') if Voo.HorarioChegada else '--:--'
    return {
        'tipo_resultado': Tipo,
        'voo': Voo.NumeroVoo,
        'cia': Voo.CiaAerea.upper().strip(),
        'data': Voo.DataPartida.strftime('%d/%m/%Y'),
        'horario_saida': Sai,
        'horario_chegada': Che,
        'origem': {'iata': Voo.AeroportoOrigem, 'nome': NomeO, 'lat': LatO, 'lon': LonO},
        'destino': {'iata': Voo.AeroportoDestino, 'nome': NomeD, 'lat': LatD, 'lon': LonD}
    }