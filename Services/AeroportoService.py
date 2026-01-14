import os
import pandas as pd
from datetime import datetime, date
from sqlalchemy import desc
from Conexoes import ObterSessaoPostgres
from Models.POSTGRES.Aeroporto import RemessaAeroportos, Aeroporto

# Pasta temporária
DIR_TEMP = 'Data/Temp_Aeroportos'
if not os.path.exists(DIR_TEMP):
    os.makedirs(DIR_TEMP)

def ListarRemessasAeroportos():
    Sessao = ObterSessaoPostgres()
    try:
        return Sessao.query(RemessaAeroportos).order_by(desc(RemessaAeroportos.DataUpload)).all()
    finally:
        Sessao.close()

def ExcluirRemessaAeroporto(IdRemessa):
    Sessao = ObterSessaoPostgres()
    try:
        Remessa = Sessao.query(RemessaAeroportos).get(IdRemessa)
        if Remessa:
            Sessao.delete(Remessa)
            Sessao.commit()
            return True, "Versão da base de aeroportos excluída."
        return False, "Remessa não encontrada."
    except Exception as e:
        Sessao.rollback()
        return False, f"Erro: {e}"
    finally:
        Sessao.close()

def AnalisarArquivoAeroportos(FileStorage):
    try:
        # Salva Temp
        CaminhoTemp = os.path.join(DIR_TEMP, FileStorage.filename)
        FileStorage.save(CaminhoTemp)
        
        # Mês Atual como referência
        Hoje = date.today()
        DataRef = date(Hoje.year, Hoje.month, 1)

        # Verifica conflito
        Sessao = ObterSessaoPostgres()
        ExisteConflito = False
        try:
            Anterior = Sessao.query(RemessaAeroportos).filter_by(MesReferencia=DataRef, Ativo=True).first()
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

def ProcessarAeroportosFinal(CaminhoArquivo, DataRef, NomeOriginal, Usuario, TipoAcao):
    Sessao = ObterSessaoPostgres()
    try:
        # 1. Ler CSV
        # ALTERAÇÃO: Removemos quotechar='"' e forçamos engine='python'.
        # Isso faz o Pandas ser mais flexível com aspas excessivas.
        try:
            Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python')
        except:
            # Fallback para latin1 caso dê erro de encoding
            Df = pd.read_csv(CaminhoArquivo, sep=',', engine='python', encoding='latin1')
        
        # Se mesmo assim ele leu tudo numa coluna só (O erro que você teve), forçamos a barra:
        if len(Df.columns) < 2:
             # Tenta ler ignorando aspas (quoting=3 é QUOTE_NONE)
             import csv
             Df = pd.read_csv(CaminhoArquivo, sep=',', quoting=csv.QUOTE_NONE, engine='python')

        # 2. Limpeza dos Nomes das Colunas
        # Remove aspas duplas, aspas simples e espaços dos cabeçalhos
        Df.columns = [c.replace('"', '').replace("'", "").strip().lower() for c in Df.columns]
        
        # Mapeamento CSV -> Banco
        Mapa = {
            'country_code': 'CodigoPais',
            'region_name': 'NomeRegiao',
            'iata': 'CodigoIata',
            'icao': 'CodigoIcao',
            'airport': 'NomeAeroporto',
            'latitude': 'Latitude',
            'longitude': 'Longitude'
        }
        
        # Filtra colunas úteis
        ColunasUteis = [c for c in Mapa.keys() if c in Df.columns]
        
        if not ColunasUteis:
            # Mostra o que ele achou para ajudar no debug se der erro de novo
            return False, f"Colunas não identificadas. Encontradas: {list(Df.columns)}"

        Df = Df[ColunasUteis].rename(columns=Mapa)

        # 3. Gerenciar Histórico
        Anterior = Sessao.query(RemessaAeroportos).filter_by(MesReferencia=DataRef, Ativo=True).first()
        if Anterior:
            Anterior.Ativo = False

        # 4. Criar Nova Remessa
        NovaRemessa = RemessaAeroportos(
            MesReferencia=DataRef,
            NomeArquivoOriginal=NomeOriginal,
            UsuarioResponsavel=Usuario,
            TipoAcao=TipoAcao,
            Ativo=True
        )
        Sessao.add(NovaRemessa)
        Sessao.flush()

        # 5. Preparar Dados para Inserção
        ListaAeroportos = Df.to_dict(orient='records')
        
        for Aero in ListaAeroportos:
            Aero['IdRemessa'] = NovaRemessa.Id
            
            # Limpeza pesada nos dados (Remove aspas dos valores também)
            for key, val in Aero.items():
                if isinstance(val, str):
                    Aero[key] = val.replace('"', '').strip()

            # Conversão segura de Lat/Long
            try: Aero['Latitude'] = float(Aero['Latitude'])
            except: Aero['Latitude'] = None
            
            try: Aero['Longitude'] = float(Aero['Longitude'])
            except: Aero['Longitude'] = None

        Sessao.bulk_insert_mappings(Aeroporto, ListaAeroportos)
        Sessao.commit()

        # Limpa temp
        if os.path.exists(CaminhoArquivo): os.remove(CaminhoArquivo)

        return True, f"Base atualizada! {len(ListaAeroportos)} aeroportos importados."

    except Exception as e:
        Sessao.rollback()
        return False, f"Erro técnico ao processar: {e}"
    finally:
        Sessao.close()