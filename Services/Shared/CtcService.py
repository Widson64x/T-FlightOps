from datetime import datetime, date, time
from decimal import Decimal
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Ctc import CtcEsp, CtcEspCpl
from Services.LogService import LogService

class CtcService:
    """
    Serviço Compartilhado para operações globais de CTC.
    Acessível por qualquer módulo (Planejamento, Reversa, Monitoramento).
    """

    @staticmethod
    def ObterCtcCompleto(filial, serie, ctc_num):
        """
        Busca um CTC específico + DADOS COMPLEMENTARES (CPL)
        Retorna um dicionário unificado.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # Busca flexível
            f, s, n = str(filial).strip(), str(serie).strip(), str(ctc_num).strip()
            
            Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                CtcEspCpl, 
                CtcEsp.filialctc == CtcEspCpl.filialctc
            ).filter(
                CtcEsp.filial == f,
                CtcEsp.seriectc == s,
                CtcEsp.filialctc == n
            )

            Resultado = Query.first()

            # Fallback para zeros a esquerda
            if not Resultado:
                Query = Sessao.query(CtcEsp, CtcEspCpl).outerjoin(
                    CtcEspCpl, CtcEsp.filialctc == CtcEspCpl.filialctc
                ).filter(
                    CtcEsp.filial == f, 
                    CtcEsp.seriectc == s, 
                    CtcEsp.filialctc == n.lstrip('0')
                )
                Resultado = Query.first()

            if not Resultado: 
                LogService.Warning("Shared.CtcService", f"CTC não encontrado {f}-{s}-{n}")
                return None

            # Desempacota
            Ctc, Cpl = Resultado
            dados_completos = {}

            # 1. Serializa CTC Principal
            for coluna in Ctc.__table__.columns:
                valor = getattr(Ctc, coluna.name)
                if isinstance(valor, (datetime, date, time)): valor = str(valor)
                elif isinstance(valor, Decimal): valor = float(valor)
                elif valor is None: valor = ""
                dados_completos[coluna.name] = valor
            
            # 2. Serializa CPL
            if Cpl:
                for coluna in Cpl.__table__.columns:
                    valor = getattr(Cpl, coluna.name)
                    if isinstance(valor, (datetime, date, time)): valor = str(valor)
                    elif isinstance(valor, Decimal): valor = float(valor)
                    elif valor is None: valor = ""
                    dados_completos[coluna.name] = valor
            else:
                dados_completos['StatusCTC'] = 'N/A'
                dados_completos['TipoCarga'] = 'N/A'

            return dados_completos

        except Exception as e:
            LogService.Error("Shared.CtcService", "Erro ao obter CTC completo", e)
            return None
        finally:
            Sessao.close()