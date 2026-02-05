from functools import wraps
from flask import request, abort, flash, redirect, url_for
from flask_login import current_user
from sqlalchemy import or_
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Permissoes import Tb_PLN_Permissao, Tb_PLN_PermissaoGrupo, Tb_PLN_PermissaoUsuario, Tb_PLN_LogAcesso
from Services.LogService import LogService

class PermissaoService:
    
    @staticmethod
    def VerificarPermissao(Usuario, ChavePermissao):
        """
        Verifica se o usuário tem permissão via Grupo OU via Permissão Individual.
        Retorna True/False.
        """
        if not Usuario.is_authenticated:
            return False

        # Super Admin Bypass (Opcional)
        if Usuario.Grupo == 'ADM_SISTEMA': 
            return True

        Sessao = ObterSessaoSqlServer()
        TemPermissao = False
        
        try:
            # 1. Busca ID da permissão pela chave
            Permissao = Sessao.query(Tb_PLN_Permissao).filter_by(Chave_Permissao=ChavePermissao).first()
            
            if not Permissao:
                LogService.Warning("PermissaoService", f"Permissão não cadastrada: {ChavePermissao}")
                return False # Se não existe a chave, nega por segurança

            # 2. Verifica se o GRUPO do usuário possui essa permissão
            # Assumindo que você consegue pegar o ID do grupo do current_user
            # Você precisará garantir que current_user tenha Codigo_UsuarioGrupo ou similar carregado
            
            # Nota: No seu UsuarioSistema atual, você tem 'Grupo' (Sigla). 
            # Idealmente, carregue o ID do Grupo no UserLoader do App.py para otimizar.
            # Aqui farei uma query simplificada assumindo que temos o ID do usuário para buscar seus vinculos
            
            # Checa Grupo
            NoGrupo = Sessao.query(Tb_PLN_PermissaoGrupo).filter(
                Tb_PLN_PermissaoGrupo.Id_Permissao == Permissao.Id_Permissao,
                Tb_PLN_PermissaoGrupo.Codigo_UsuarioGrupo == Usuario.Id_Grupo_Banco # Precisa mapear isso no User Object
            ).count() > 0

            # Checa Individual
            NoUsuario = Sessao.query(Tb_PLN_PermissaoUsuario).filter(
                Tb_PLN_PermissaoUsuario.Id_Permissao == Permissao.Id_Permissao,
                Tb_PLN_PermissaoUsuario.Codigo_Usuario == Usuario.IdBanco
            ).first()

            # Lógica: Se tem no grupo E NÃO foi revogado explicitamente no usuário (se usar essa lógica)
            # Ou: Se tem no grupo OU tem no usuário
            
            if NoUsuario:
                TemPermissao = NoUsuario.Conceder # Prevalece a regra individual (seja true ou false)
            else:
                TemPermissao = NoGrupo

        except Exception as e:
            LogService.Error("PermissaoService", "Erro ao validar permissão", e)
        finally:
            Sessao.close()
            
        return TemPermissao

    @staticmethod
    def RegistrarLog(Usuario, Rota, Metodo, Ip, Chave, Permitido):
        Sessao = ObterSessaoSqlServer()
        try:
            NovoLog = Tb_PLN_LogAcesso(
                Id_Usuario=Usuario.IdBanco if Usuario.is_authenticated else None,
                Nome_Usuario=Usuario.Nome if Usuario.is_authenticated else 'Anonimo',
                Rota_Acessada=Rota,
                Metodo_Http=Metodo,
                Ip_Origem=Ip,
                Permissao_Exigida=Chave,
                Acesso_Permitido=Permitido
            )
            Sessao.add(NovoLog)
            Sessao.commit()
        except Exception as e:
            LogService.Error("PermissaoService", "Falha ao gravar log de acesso", e)
        finally:
            Sessao.close()

# --- O DECORATOR ---
def RequerPermissao(ChavePermissao):
    def Decorator(F):
        @wraps(F)
        def Wrapper(*args, **kwargs):
            
            Permitido = PermissaoService.VerificarPermissao(current_user, ChavePermissao)
            
            # Grava Log
            PermissaoService.RegistrarLog(
                Usuario=current_user,
                Rota=request.path,
                Metodo=request.method,
                Ip=request.remote_addr,
                Chave=ChavePermissao,
                Permitido=Permitido
            )

            if not Permitido:
                flash("Você não tem permissão para acessar este recurso.", "danger")
                return redirect(url_for('Dashboard')) # Ou renderizar página 403
            
            return F(*args, **kwargs)
        return Wrapper
    return Decorator