import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DE AMBIENTE ---
# Adiciona diretório raiz ao path para conseguir importar os Services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock das dependências ANTES de importar o Service para evitar erros de conexão
sys.modules['Conexoes'] = MagicMock()
sys.modules['Services.LogService'] = MagicMock()

# Configura Logger para aparecer no terminal
def fake_log(src, msg):
    if "FINAL:" in str(msg) or "Rota Vencedora" in str(msg): # Filtra só o que importa
        print(f"[LOG] {msg}")

sys.modules['Services.LogService'].LogService.Debug = fake_log
sys.modules['Services.LogService'].LogService.Info = fake_log
sys.modules['Services.LogService'].LogService.Error = lambda src, msg, err: print(f"[ERRO] {msg} | {err}")

# Agora importamos o Service
from Services.MalhaService import MalhaService

def RodarSimulacao():
    print("\n" + "="*60)
    print(" SIMULAÇÃO DE SCORE: GOL (Barata) vs LATAM (Parceira)")
    print("="*60 + "\n")

    # 1. CRIAR DADOS FALSOS (MOCKS)
    dt = datetime.now()

    # Voo GOL: Barato, Rápido, mas Score Parceria BAIXO (20)
    voo_gol = MagicMock()
    voo_gol.CiaAerea = 'GOL'
    voo_gol.NumeroVoo = 'G3-1000'
    voo_gol.AeroportoOrigem = 'GRU'
    voo_gol.AeroportoDestino = 'MAO'
    voo_gol.DataPartida = dt
    voo_gol.HorarioSaida = dt.time()
    voo_gol.HorarioChegada = (dt + timedelta(hours=1)).time() # 1h duração

    # Voo LATAM: Caro, Lento, mas Score Parceria ALTO (90)
    voo_latam = MagicMock()
    voo_latam.CiaAerea = 'LATAM'
    voo_latam.NumeroVoo = 'LA-3000'
    voo_latam.AeroportoOrigem = 'GRU'
    voo_latam.AeroportoDestino = 'MAO'
    voo_latam.DataPartida = dt
    voo_latam.HorarioSaida = dt.time()
    voo_latam.HorarioChegada = (dt + timedelta(hours=2)).time() # 2h duração

    # 2. DEFINIR O CENÁRIO (PATCHES)
    
    # A. Simula o Banco de Dados vazio (não vamos usar pois vamos injetar as rotas)
    with patch('Services.MalhaService.ObterSessaoSqlServer') as mock_conn:
        
        # B. Simula Scores de Parceria
        with patch('Services.CiaAereaService.CiaAereaService.ObterDicionarioScores') as mock_scores:
            mock_scores.return_value = {'GOL': 20, 'LATAM': 90}

            # C. Simula Custo do Frete
            with patch('Services.TabelaFreteService.TabelaFreteService.CalcularCustoEstimado') as mock_custo:
                # GOL = 500 reais, LATAM = 1200 reais
                mock_custo.side_effect = lambda org, dst, cia, peso: (500.0, 0) if cia == 'GOL' else (1200.0, 0)

                # D. BYPASS TOTAL: Enganamos o NetworkX e o Validador
                # Dizemos ao código que ele encontrou 2 caminhos
                with patch('networkx.all_simple_paths', return_value=[['GRU', 'MAO'], ['GRU', 'MAO']]):
                    
                    # Dizemos ao código: "Para o primeiro caminho, use o voo GOL. Para o segundo, use LATAM"
                    with patch('Services.MalhaService.MalhaService._ValidarCaminhoCronologico', side_effect=[[voo_gol], [voo_latam]]):
                        
                        # Mock para não quebrar na formatação final
                        with patch('Services.MalhaService.MalhaService._CompletarCacheDestinos'):
                            with patch('Services.MalhaService.MalhaService._FormatarListaRotas', side_effect=lambda l, c, t, m: [{'cia': l[0].CiaAerea, 'score': m['score'], 'custo': m['custo']}]):

                                # --- 3. EXECUTAR O TESTE ---
                                print("[INFO] Executando algoritmo...")
                                Resultados = MalhaService.BuscarOpcoesDeRotas(dt, dt, 'GRU', 'MAO')

                                # --- 4. EXIBIR RESULTADOS ---
                                if not Resultados['recomendada']:
                                    print("[ERRO] Nenhuma rota foi gerada.")
                                else:
                                    print("\n" + "-"*30)
                                    print(" RESULTADO FINAL (RANKING)")
                                    print("-"[-30:])
                                    
                                    # Exibe a Recomendada (Vencedora)
                                    vencedora = Resultados['recomendada'][0]
                                    print(f"🏆 RECOMENDADA: {vencedora['cia']}")
                                    print(f"   Score Final: {vencedora['score']:.1f} (Menor é melhor)")
                                    print(f"   Custo Real:  R$ {vencedora['custo']:.2f}")

                                    print("\n--- COMPARAÇÃO ---")
                                    # Tenta achar a GOL e LATAM nas listas para comparar
                                    # Como o nosso mock de formatação retorna lista simples, vamos iterar o mock
                                    pass

if __name__ == "__main__":
    RodarSimulacao()