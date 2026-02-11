import os
import pandas as pd
from datetime import datetime
from sqlalchemy import desc
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.TabelaFrete import RemessaFrete, TabelaFrete
from Configuracoes import ConfiguracaoBase
from Services.LogService import LogService

class TabelaFreteService:
    DIR_TEMP = ConfiguracaoBase.DIR_TEMP

    @staticmethod
    def _GarantirDiretorio():
        if not os.path.exists(TabelaFreteService.DIR_TEMP):
            try:
                os.makedirs(TabelaFreteService.DIR_TEMP)
            except Exception as e:
                LogService.Error("TabelaFreteService", "Falha ao criar diretório temp", e)

    @staticmethod
    def _NormalizarTarifa(val):
        """
        Retorna float se válido, ou None se vazio/inválido.
        """
        if pd.isna(val): return None
        s = str(val).strip().upper()
        if s in ['', '-', 'NAN', 'NONE', 'N/A']: return None
        
        try:
            # Remove R$, espaços e converte vírgula
            clean_val = s.replace('R$', '').replace(' ', '').replace(',', '.')
            return float(clean_val)
        except:
            return None

    @staticmethod
    def _NormalizarNomeCia(cia_input):
        """
        Converte códigos IATA/ICAO ou nomes longos para o padrão da Tabela de Frete.
        Padrão esperado no Banco: GOL, LATAM, AZUL.
        """
        if not cia_input: return ""
        s = str(cia_input).upper().strip()
        
        # Mapeamento GOL
        if 'GOL' in s or 'G3' in s or 'GLO' in s: return 'GOL'
        
        # Mapeamento LATAM
        if 'LATAM' in s or 'TAM' in s or 'JJ' in s or 'LA' in s: return 'LATAM'
        
        # Mapeamento AZUL
        if 'AZUL' in s or 'AD' in s or 'AZU' in s: return 'AZUL'
        
        return s

    @staticmethod
    def ListarRemessas():
        Sessao = ObterSessaoSqlServer()
        try:
            return Sessao.query(RemessaFrete).order_by(desc(RemessaFrete.DataUpload)).all()
        finally:
            Sessao.close()

    @staticmethod
    def ExcluirRemessa(id_remessa):
        Sessao = ObterSessaoSqlServer()
        try:
            Remessa = Sessao.query(RemessaFrete).get(id_remessa)
            if Remessa:
                Sessao.delete(Remessa)
                Sessao.commit()
                return True, "Tabela excluída com sucesso."
            return False, "Registro não encontrado."
        except Exception as e:
            Sessao.rollback()
            return False, str(e)
        finally:
            Sessao.close()

    @staticmethod
    def ProcessarArquivo(arquivo, usuario):
        TabelaFreteService._GarantirDiretorio()
        Caminho = os.path.join(TabelaFreteService.DIR_TEMP, arquivo.filename)
        Sessao = ObterSessaoSqlServer()
        
        try:
            arquivo.save(Caminho)
            LogService.Info("TabelaFreteService", f"Analisando arquivo: {arquivo.filename}")
            
            DfRaw = None
            
            # --- BLOCO DE LEITURA BLINDADO (Context Manager) ---
            with pd.ExcelFile(Caminho, engine='openpyxl') as XlsFile:
                
                # 1. Identificar a aba correta
                SheetName = None
                for sheet in XlsFile.sheet_names:
                    if 'TARIF' in sheet.upper(): 
                        SheetName = sheet
                        break
                
                if not SheetName:
                    SheetName = XlsFile.sheet_names[0]
                    LogService.Warning("TabelaFreteService", f"Aba 'TARIFÁRIO' não encontrada. Usando: {SheetName}")
                else:
                    LogService.Info("TabelaFreteService", f"Processando aba: {SheetName}")

                # 2. Ler os dados
                DfRaw = pd.read_excel(XlsFile, sheet_name=SheetName, header=None)

            # 3. Localizar Cabeçalho
            RowHeaderIdx = -1
            ColOrigemIdx = -1
            ColDestinoIdx = -1
            
            for i in range(min(15, len(DfRaw))):
                RowVals = [str(x).strip().upper() for x in DfRaw.iloc[i].values]
                if 'ORIGEM' in RowVals and 'DESTINO' in RowVals:
                    RowHeaderIdx = i
                    for idx, val in enumerate(RowVals):
                        if val == 'ORIGEM': ColOrigemIdx = idx
                        elif val == 'DESTINO': ColDestinoIdx = idx
                    break
            
            if RowHeaderIdx == -1:
                return False, "Estrutura inválida. Colunas Origem/Destino não encontradas."

            # 4. Mapear Serviços
            if RowHeaderIdx == 0:
                return False, "Arquivo sem linha de títulos de serviços."

            MapServicos = {}
            RowServicosIdx = RowHeaderIdx - 1
            
            for col in range(len(DfRaw.columns)):
                if col in [ColOrigemIdx, ColDestinoIdx]: continue
                
                NomeServico = str(DfRaw.iloc[RowServicosIdx, col]).strip()
                
                if NomeServico and NomeServico.upper() not in ['NAN', 'NONE', '', 'N/A']:
                    if " X " in NomeServico.upper(): continue
                    MapServicos[col] = NomeServico

            if not MapServicos:
                return False, "Nenhum serviço identificado."

            # 5. Persistir Dados
            NovaRemessa = RemessaFrete(
                DataReferencia=datetime.now().date(),
                NomeArquivoOriginal=arquivo.filename,
                UsuarioResponsavel=usuario,
                Ativo=True
            )
            Sessao.add(NovaRemessa)
            Sessao.flush()

            ListaInsert = []
            
            for i in range(RowHeaderIdx + 1, len(DfRaw)):
                Row = DfRaw.iloc[i]
                
                RawOrigem = str(Row[ColOrigemIdx]).strip().upper()
                RawDestino = str(Row[ColDestinoIdx]).strip().upper()
                
                if RawOrigem in ['', 'NAN', 'NONE'] or RawDestino in ['', 'NAN', 'NONE']: continue
                
                Origens = [o.strip() for o in RawOrigem.split('/')]
                
                for Origem in Origens:
                    for ColIdx, NomeServico in MapServicos.items():
                        ValorRaw = Row[ColIdx]
                        ValorTarifa = TabelaFreteService._NormalizarTarifa(ValorRaw)
                        
                        # Normaliza Cia aqui também para garantir consistência
                        CiaBruta = NomeServico.split(' ')[0].upper()
                        CiaNormalizada = TabelaFreteService._NormalizarNomeCia(CiaBruta)

                        Item = TabelaFrete(
                            IdRemessa=NovaRemessa.Id,
                            Origem=Origem,
                            Destino=RawDestino,
                            CiaAerea=CiaNormalizada, # Salva já normalizado (GOL, LATAM)
                            Servico=NomeServico,
                            Tarifa=ValorTarifa
                        )
                        ListaInsert.append(Item)

            if ListaInsert:
                Sessao.bulk_save_objects(ListaInsert)
                Sessao.commit()
                Msg = f"Sucesso! {len(ListaInsert)} linhas de tarifa importadas."
                LogService.Info("TabelaFreteService", Msg)
                return True, Msg
            else:
                return False, "Arquivo processado mas nenhum dado encontrado."

        except Exception as e:
            Sessao.rollback()
            LogService.Error("TabelaFreteService", "Erro fatal no processamento", e)
            return False, f"Erro técnico: {str(e)}"
        
        finally:
            if os.path.exists(Caminho):
                try: os.remove(Caminho)
                except: pass
            Sessao.close()
            
    @staticmethod
    def CalcularCustoEstimado(origem, destino, cia, peso):
        """
        Busca a tarifa na tabela e calcula o custo total.
        Retorna (CustoTotal, Detalhes).
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # 1. Normaliza o nome da Cia para bater com o banco (ex: G3 -> GOL)
            cia_buscada = TabelaFreteService._NormalizarNomeCia(cia)

            # 2. Busca Tarifa (Ordenando pela MENOR tarifa para pegar o melhor preço)
            # Usa .join(RemessaFrete) para garantir que só pega de tabelas ativas
            Item = Sessao.query(TabelaFrete).join(RemessaFrete).filter(
                RemessaFrete.Ativo == True,
                TabelaFrete.Origem == origem,
                TabelaFrete.Destino == destino,
                TabelaFrete.CiaAerea == cia_buscada
            ).order_by(TabelaFrete.Tarifa.asc()).first() # <--- O PULO DO GATO: Pega a mais barata

            if Item and Item.Tarifa:
                vl_tarifa = float(Item.Tarifa)
                vl_peso = float(peso)
                Custo = vl_tarifa * vl_peso
                
                Detalhes = {
                    'tarifa_base': vl_tarifa,
                    'servico': Item.Servico,
                    'cia_tarifaria': Item.CiaAerea,
                    'peso_calculado': vl_peso
                }
                
                # Debug para confirmar no terminal
                LogService.Debug("TarifaFound", f"{origem}->{destino} ({cia_buscada}): R$ {vl_tarifa} [{Item.Servico}]")
                
                return Custo, Detalhes
            
            # Se não achar
            LogService.Debug("TarifaMiss", f"Nenhuma tarifa ativa para {origem}->{destino} ({cia_buscada})")
            return 0.0, {}

        except Exception as e:
            LogService.Error("TabelaFreteService", f"Erro calc custo {origem}->{destino}", e)
            return 0.0, {}
        finally:
            Sessao.close()