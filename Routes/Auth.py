from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from Services.AuthService import AuthService  # <--- Olha a estrela do show aqui!
from Models.UsuarioModel import UsuarioSistema

# Definição do Blueprint
AuthBp = Blueprint('Auth', __name__)

@AuthBp.route('/Logar', methods=['GET', 'POST'])
def Login():
    """
    Rota de Login: Agora clean, moderna e cheirosa.
    O trabalho sujo fica pro AuthService. Aqui a gente só sorri e acena. 👋
    """
    if request.method == 'POST':
        Username = request.form.get('username')
        Password = request.form.get('password')
        
        # Chama o nosso "Porteiro" (Service) que resolve tudo (AD + Banco)
        # Retorna um dict com os dados ou None se falhar
        DadosUsuario = AuthService.ValidarAcessoCompleto(Username, Password)

        if DadosUsuario:
            # Se chegou aqui, o crachá passou! 🎉
            
            # Reconstrói o objeto que o Flask-Login gosta
            UsuarioLogado = UsuarioSistema(
                Login=DadosUsuario['login'],
                Nome=DadosUsuario['nome'],
                Email=DadosUsuario['email'],
                Grupo=DadosUsuario['grupo'],
                IdBanco=DadosUsuario['id']
            )

            # Carimba o passaporte
            login_user(UsuarioLogado)
            
            flash(f'Bem-vindo(a) a bordo, {DadosUsuario["nome"]}! ✈️', 'success')
            
            # Redireciona para onde o usuário queria ir ou para a Home
            ProximaPagina = request.args.get('next')
            return redirect(ProximaPagina or '/')
        
        else:
            # Se falhar, a culpa pode ser do AD ou do Banco, mas pro usuário a gente diz isso:
            flash('Login falhou. Verifique usuário, senha ou se você foi demitido. 😅', 'danger')

    # Se for GET, só mostra a tela de login (agora na pasta certa!)
    return render_template('Auth/Login.html')

@AuthBp.route('/Deslogar')
@login_required
def Logout():
    logout_user()
    flash('Você saiu do sistema. Câmbio desligo. 📻', 'info')
    return redirect(url_for('Auth.Login'))