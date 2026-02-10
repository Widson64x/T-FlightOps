from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.CiaConfig import CiaConfig
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha
from Services.LogService import LogService

class CiaAereaService:
    
    @staticmethod
    def ObterTodasCias():
        """
        Lista todas as Cias Aéreas que existem na Malha ou já configuradas,
        junto com seus scores atuais.
        """
        Sessao = ObterSessaoSqlServer()
        try:
            # 1. Busca Cias Configuradas
            Configs = Sessao.query(CiaConfig).all()
            MapConfigs = {c.CiaAerea: c.ScoreParceria for c in Configs}
            
            # 2. Busca Cias da Malha Ativa (para garantir que novas apareçam)
            CiasMalha = Sessao.query(VooMalha.CiaAerea).join(RemessaMalha)\
                .filter(RemessaMalha.Ativo == True).distinct().all()
            
            ListaFinal = []
            CiasVistas = set()

            # Adiciona as da Malha
            for (nome_cia,) in CiasMalha:
                nome_cia = nome_cia.strip().upper()
                score = MapConfigs.get(nome_cia, 50) # Padrão 50 (Neutro)
                ListaFinal.append({'cia': nome_cia, 'score': score})
                CiasVistas.add(nome_cia)
            
            # Adiciona as configuradas que talvez não estejam na malha hoje (histórico)
            for c in Configs:
                if c.CiaAerea not in CiasVistas:
                    ListaFinal.append({'cia': c.CiaAerea, 'score': c.ScoreParceria})
            
            # Ordena por nome
            ListaFinal.sort(key=lambda x: x['cia'])
            return ListaFinal

        except Exception as e:
            LogService.Error("CiaAereaService", "Erro ao listar cias", e)
            return []
        finally:
            Sessao.close()

    @staticmethod
    def AtualizarScore(cia, novo_score):
        """Atualiza o índice de 'parceria' de uma cia."""
        Sessao = ObterSessaoSqlServer()
        try:
            cia = cia.strip().upper()
            Config = Sessao.query(CiaConfig).filter(CiaConfig.CiaAerea == cia).first()
            
            if not Config:
                Config = CiaConfig(CiaAerea=cia, ScoreParceria=novo_score)
                Sessao.add(Config)
            else:
                Config.ScoreParceria = novo_score
            
            Sessao.commit()
            return True
        except Exception as e:
            LogService.Error("CiaAereaService", f"Erro ao atualizar score {cia}", e)
            return False
        finally:
            Sessao.close()

    @staticmethod
    def ObterDicionarioScores():
        """Retorna um dict simples {'LATAM': 100, 'GOL': 20} para uso rápido no algoritmo."""
        Sessao = ObterSessaoSqlServer()
        try:
            Configs = Sessao.query(CiaConfig).filter(CiaConfig.Ativo == True).all()
            return {c.CiaAerea: c.ScoreParceria for c in Configs}
        except:
            return {}
        finally:
            Sessao.close()