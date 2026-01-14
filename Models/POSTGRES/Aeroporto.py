from sqlalchemy import Column, Date, DateTime, Integer, String, Float, func, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .Base import BasePostgres

class RemessaAeroportos(BasePostgres):
    """
    Tabela de CONTROLE para Aeroportos.
    Armazena o cabeçalho do upload (Quem subiu, quando e qual versão é a ativa).
    """
    __tablename__ = 'Tb_RemessaAeroporto' # Nome ajustado para não conflitar
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    MesReferencia = Column(Date, nullable=False, index=True)
    NomeArquivoOriginal = Column(String(255))
    DataUpload = Column(DateTime(timezone=True), server_default=func.now())
    UsuarioResponsavel = Column(String(100)) 
    
    # Tipo da operação: 'Importacao', 'Substituicao'
    TipoAcao = Column(String(50), nullable=False, default='Importacao')
    
    # Define qual é a versão atual dos aeroportos
    Ativo = Column(Boolean, default=True)
    
    # Relacionamento com os itens (Aeroportos)
    Aeroportos = relationship("Aeroporto", back_populates="Remessa", cascade="all, delete-orphan")
    
class Aeroporto(BasePostgres):
    """
    Tabela de DADOS dos Aeroportos.
    Vinculada a uma Remessa específica.
    """
    __tablename__ = 'Tb_Aeroporto'
    __table_args__ = {'schema': 'MalhaAerea'} 

    Id = Column(Integer, primary_key=True, autoincrement=True)
    
    # --- VÍNCULO COM A REMESSA (Necessário para a mecânica funcionar) ---
    IdRemessa = Column(Integer, ForeignKey('MalhaAerea.Tb_RemessaAeroporto.Id'), nullable=False, index=True)

    # Ex: 'BR'
    CodigoPais = Column(String(5), nullable=True)
    
    # Ex: 'Sao Paulo'
    NomeRegiao = Column(String(100), nullable=True)
    
    # Ex: 'CGH'
    CodigoIata = Column(String(3), nullable=True, index=True)
    
    # Ex: 'SBSP'
    CodigoIcao = Column(String(4), nullable=True)
    
    # Ex: 'Congonhas Airport'
    NomeAeroporto = Column(String(255), nullable=True)
    
    # Coordenadas
    Latitude = Column(Float, nullable=True)
    Longitude = Column(Float, nullable=True)

    # Relacionamento de volta
    Remessa = relationship("RemessaAeroportos", back_populates="Aeroportos")