from ldap3 import Server, Connection, ALL, SIMPLE
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo
from Conexoes import ObterSessaoSqlServer
from Configuracoes import ConfiguracaoAtual

class AuthService:
    """
    🎩 O GRANDE PORTEIRO (The Bouncer)
    """

    @staticmethod
    def AutenticarNoAd(usuario, senha):
        """
        Tenta logar o sujeito no Active Directory.
        Atualizado para usar SIMPLE BIND e evitar o erro do MD4.
        """
        # Cheat code de desenvolvimento
        if ConfiguracaoAtual.DEBUG and senha == "admin":
            print("🔓 [AuthService] Modo Debug: Login ignorado pelo 'admin'.")
            return True

        AD_SERVER = ConfiguracaoAtual.AD_SERVER
        AD_DOMAIN = ConfiguracaoAtual.AD_DOMAIN

        # No modo SIMPLE, alguns ADs preferem 'user@domain.com' ou 'DOMAIN\user'
        # O formato DOMAIN\user costuma funcionar bem.
        user_ad = f"{AD_DOMAIN}\\{usuario}"
        
        try:
            print(f"🔑 [AuthService] Tentando login AD para '{usuario}'...")
            
            server = Server(AD_SERVER, get_info=ALL)
            
            # --- AQUI ESTÁ A CORREÇÃO ---
            # Trocamos authentication=NTLM por authentication=SIMPLE
            # O NTLM usa MD4 (que foi bloqueado). O SIMPLE passa direto.
            conn = Connection(server, user=user_ad, password=senha, authentication=SIMPLE)
            
            if conn.bind():
                print(f"✅ [AuthService] Login AD Sucesso: A porta abriu.")
                conn.unbind()
                return True
            else:
                print(f"⛔ [AuthService] Login AD Falhou: Credenciais inválidas.")
                return False
                
        except Exception as e:
            # Agora com menos fogo e mais detalhes
            print(f"🔥 [AuthService] Erro na conexão LDAP: {e}")
            return False

    @staticmethod
    def BuscarUsuarioNoBanco(login):
        Sessao = ObterSessaoSqlServer()
        DadosUsuario = None

        try:
            Resultado = Sessao.query(Usuario, UsuarioGrupo)\
                .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
                .filter(Usuario.Login_Usuario == login)\
                .first()

            if Resultado:
                UsuarioEncontrado, GrupoEncontrado = Resultado
                
                DadosUsuario = {
                    "id": UsuarioEncontrado.Codigo_Usuario,
                    "nome": UsuarioEncontrado.Nome_Usuario,
                    "email": UsuarioEncontrado.Email_Usuario,
                    "login": UsuarioEncontrado.Login_Usuario,
                    "grupo": GrupoEncontrado.Sigla_UsuarioGrupo if GrupoEncontrado else "VISITANTE",
                    "ativo": True 
                }
                print(f"✅ [AuthService] Usuário '{login}' encontrado no SQL. Grupo: {DadosUsuario['grupo']}")
            else:
                print(f"👻 [AuthService] Usuário '{login}' logou no AD mas não existe no SQL.")

        except Exception as e:
            print(f"💀 [AuthService] Erro no Banco: {e}")
        
        finally:
            if Sessao: Sessao.close()

        return DadosUsuario

    @staticmethod
    def ValidarAcessoCompleto(usuario, senha):
        if AuthService.AutenticarNoAd(usuario, senha):
            return AuthService.BuscarUsuarioNoBanco(usuario)
        return None