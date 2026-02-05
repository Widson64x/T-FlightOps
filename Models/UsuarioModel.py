from flask_login import UserMixin

class UsuarioSistema(UserMixin):
    """
    Representa o usuário logado.
    Armazena apenas os dados essenciais para não precisar ir ao banco em toda verificação simples.
    """
    # Adicionado Id_Grupo_Banco=None no init
    def __init__(self, Login, Nome, Email=None, Grupo=None, IdBanco=None, Id_Grupo_Banco=None):
        self.id = Login  # O Flask-Login usa isso como identificador na sessão (cookie)
        self.Login = Login
        self.Nome = Nome
        self.Email = Email
        self.Grupo = Grupo
        self.IdBanco = IdBanco # O ID numérico (PK) do SQL Server
        self.Id_Grupo_Banco = Id_Grupo_Banco # <--- NOVO CAMPO OBRIGATÓRIO PARA PERMISSÕES

    def TemPermissao(self, PermissaoNecessaria):
        # Agora você já tem o self.Id_Grupo_Banco aqui se precisar validar algo rápido na memória
        pass