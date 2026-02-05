from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker

# --- LOG SERVICE ---
from Conexoes import ObterEngineSqlServer
from Services.AcompanhamentoService import AcompanhamentoService
from Services import AcompanhamentoService
from Services.LogService import LogService

# --- MODELS SQL SERVER (LEGADO) ---
from Models.SQL_SERVER.Awb import Awb, AwbStatus, AwbNota

class AwbService:
    """
    Serviço Compartilhado para operações globais de AWB.
    Acessível por qualquer módulo (Planejamento, Reversa, Monitoramento).
    """
    @staticmethod
    def _ObterSessaoSql():
        Engine = ObterEngineSqlServer()
        return sessionmaker(bind=Engine)()
    
    @staticmethod
    def BuscarDetalhesAwbCompleto(cod_awb_req):
        LogService.Info("AwbService", f"Buscando detalhes completos (Modal) da AWB ID: {cod_awb_req}")
        session = AwbService._ObterSessaoSql()
        try:
            # 1. Busca Tabela Base (tb_airAWB) pelo codawb
            awb = session.query(Awb).filter(Awb.codawb == cod_awb_req).first()
            if not awb: 
                LogService.Warning("AwbService", f"AWB ID {cod_awb_req} não encontrada.")
                return None
            
            def fmt(v, t='str'):
                if v is None: return 0.0 if t=='num' else ''
                if t == 'num': return float(v)
                if t == 'date': 
                    if isinstance(v, str): return v
                    return v.strftime('%d/%m/%Y')
                if t == 'datetime': return v.strftime('%d/%m/%Y %H:%M')
                return str(v).strip()

            # 2. Busca Notas (tb_airAWBnota) 
            notas_db = session.query(AwbNota).filter(AwbNota.codawb == awb.codawb).all()
            lista_notas = []
            for n in notas_db:
                lista_notas.append({
                    'nota': fmt(n.nota),
                    'serie': fmt(n.serie),
                    'tipo': fmt(n.tipo), 
                    'filial': n.filialctc,
                    'valor': fmt(n.valor, 'num'),
                    'chave': '', 
                    'data': '',
                    'peso': 0,
                    'volumes': 0,
                    'especie': fmt(n.tipo) 
                })

            # 3. Busca Histórico (TB_AWB_STATUS)
            status_db = session.query(AwbStatus)\
                .filter(AwbStatus.CODAWB == awb.codawb)\
                .order_by(desc(AwbStatus.DATAHORA_STATUS)).all()
                
            lista_status = []
            for s in status_db:
                lista_status.append({
                    'status': fmt(s.STATUS_AWB),
                    'data': fmt(s.DATAHORA_STATUS, 'datetime'),
                    'local': fmt(s.LOCAL_STATUS),
                    'voo': fmt(s.VOO),
                    'usuario': fmt(s.Usuario),
                    'volumes': fmt(s.VOLUMES, 'num')
                })

            # 4. Monta Objeto Completo
            return {
                "codawb": awb.codawb,
                "awb": awb.awb,
                "dig": awb.dig,
                "cia": f"{fmt(awb.nomecia)} ({fmt(awb.cia)})",
                "emissao": {
                    "data": fmt(awb.data, 'date'),
                    "hora": fmt(awb.hora),
                    "filial": fmt(awb.filial),
                    "tipo": fmt(awb.Tipo_Servico)
                },
                "origem": f"{fmt(awb.siglaorigem)} - {fmt(awb.aeroportoorigem)}",
                "destino": f"{fmt(awb.siglades)} - {fmt(awb.aeroportodestino)}",
                "lugar_entrega": fmt(awb.lugar),
                
                "remetente": {
                    "nome": fmt(awb.nomeexp), "cnpj": fmt(awb.cnpjexp), "ie": fmt(awb.inscrestexp),
                    "endereco": f"{fmt(awb.endexp)}, {fmt(awb.bairroexp)}",
                    "local": f"{fmt(awb.cidadexp)} / {fmt(awb.ufexp)} - {fmt(awb.cepexp)}",
                    "contato": f"Tel: {fmt(awb.telexp)} | Fax: {fmt(awb.faxexp)}"
                },
                "destinatario": {
                    "nome": fmt(awb.nomedes), "cnpj": fmt(awb.cnpjdes), "ie": fmt(awb.inscrestdes),
                    "endereco": f"{fmt(awb.enddes)}, {fmt(awb.bairrodes)}",
                    "local": f"{fmt(awb.cidadedes)} / {fmt(awb.ufdes)} - {fmt(awb.cepdes)}",
                    "contato": f"Tel: {fmt(awb.teldes)} | Fax: {fmt(awb.faxdes)}"
                },
                
                "carga": {
                    "especie": fmt(awb.especie),
                    "volumes": fmt(awb.volumes, 'num'),
                    "peso_real": fmt(awb.pesoreal, 'num'),
                    "peso_cubado": fmt(awb.pesocubado, 'num'),
                    "dimensoes": f"{fmt(awb.comprimento, 'num')} x {fmt(awb.largura, 'num')} x {fmt(awb.altura, 'num')}",
                    "valor": fmt(awb.valmerc, 'num'),
                    "perecivel": fmt(awb.perecivel_duracao)
                },
                "notas": lista_notas,
                "historico": lista_status,
                "entregue": awb.ENTREGUE == 'S',
                "cancelado": awb.cancelado == 'S',
                "motivo_canc": fmt(awb.canc_motivo),
                "integracao": {
                    "nOca": fmt(awb.nOca),
                    "chave_cte": fmt(awb.chCTe_AWB),
                    "dt_importacao": fmt(awb.Data_Importacao, 'datetime')
                }
            }
        except Exception as e:
            LogService.Error("AcompanhamentoService", "Erro ao buscar detalhes completos da AWB.", e)
            return None
        finally:
            session.close()