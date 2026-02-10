from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, func
from Models.SQL_SERVER.Base import Base

class CiaConfig(Base):
    __tablename__ = 'Tb_PLN_CiaConfig'
    __table_args__ = {'schema': 'intec.dbo'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CiaAerea = Column(String(10), nullable=False, unique=True) # Ex: LATAM, GOL, AZUL
    
    # O "Índice de Puxar Saco" (0 a 100)
    # 0 = Evitar a todo custo
    # 50 = Neutro
    # 100 = Prioridade Máxima (Parceiro Preferencial)
    ScoreParceria = Column(Integer, default=50) 
    
    Ativo = Column(Boolean, default=True)
    DataAtualizacao = Column(DateTime, default=func.now(), onupdate=func.now())