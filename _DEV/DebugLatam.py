import sys
import os

# Adiciona o diretório raiz ao path para importar os Models e Conexões
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from sqlalchemy import cast, Date, text
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.MalhaAerea import VooMalha, RemessaMalha

# Ajuste de encoding para console Windows
sys.stdout.reconfigure(encoding='utf-8')

def executar_diagnostico():
    session = ObterSessaoSqlServer()
    # Data do erro relatado nos logs (09/02/2026)
    data_teste = datetime(2026, 2, 9).date() 

    print(f"\n{'='*20} DIAGNÓSTICO DE MALHA AÉREA {'='*20}")
    print(f"Data Alvo da Busca: {data_teste}")
    print("-" * 60)

    try:
        # 1. VERIFICAR SE EXISTE MALHA ATIVA
        print("[1] Verificando Remessas (Arquivos de Malha) Ativos...")
        remessas = session.query(RemessaMalha).filter(RemessaMalha.Ativo == True).all()
        
        if not remessas:
            print("    [!] CRÍTICO: Nenhuma remessa ativa encontrada. O sistema não vai achar nenhum voo.")
        else:
            for r in remessas:
                print(f"    ID: {r.Id} | Arquivo: {r.NomeArquivoOriginal} | Importado em: {r.DataUpload}")

        # 2. CONTAGEM GERAL NA DATA
        print(f"\n[2] Verificando total de voos para {data_teste} (Qualquer CIA)...")
        qtd_voos = session.query(VooMalha).join(RemessaMalha).filter(
            RemessaMalha.Ativo == True,
            cast(VooMalha.DataPartida, Date) == data_teste
        ).count()
        print(f"    Total de voos encontrados: {qtd_voos}")

        if qtd_voos == 0:
            print("    [!] AVISO: Não há voos nesta data. Verifique se a malha cobre este dia.")

        # 3. BUSCA ESPECÍFICA (LATAM / 3404)
        print(f"\n[3] Inspecionando dados brutos para 'LATAM' ou voo '3404'...")
        
        # Usando SQL RAW para ver exatamente o que tem no banco, sem filtros do SQLAlchemy
        sql = text("""
            SELECT TOP 20 v.Id, v.CiaAerea, v.NumeroVoo, v.DataPartida
            FROM intec.dbo.Tb_PLN_Voo v
            JOIN intec.dbo.Tb_PLN_RemessaVoo r ON v.IdRemessa = r.Id
            WHERE r.Ativo = 1 
              AND CAST(v.DataPartida AS DATE) = :data
              AND (v.NumeroVoo LIKE '%3404%' OR v.CiaAerea LIKE '%LA%' OR v.CiaAerea LIKE '%LATAM%')
        """)
        
        result = session.execute(sql, {'data': data_teste}).fetchall()
        
        if not result:
            print("    [!] NENHUM RESULTADO. O banco não contém voos com '3404' ou CIA 'LA' nesta data.")
        else:
            print(f"    Registros encontrados ({len(result)}). Veja atentamente o campo 'Numero':")
            print(f"    {'ID':<8} | {'CIA':<8} | {'NUMERO REAL (BD)':<20} | {'DATA'}")
            print("-" * 60)
            for row in result:
                # Destaque visual para caracteres invisíveis (espaços)
                numero_real = f"'{row[2]}'" 
                print(f"    {row[0]:<8} | {row[1]:<8} | {numero_real:<20} | {row[3]}")

    except Exception as e:
        print(f"\n[!] ERRO DURANTE EXECUÇÃO: {e}")

    finally:
        session.close()
        print(f"\n{'='*20} FIM DO DIAGNÓSTICO {'='*20}\n")

if __name__ == "__main__":
    executar_diagnostico()