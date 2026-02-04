from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from Models.SQL_SERVER.Base import Base

class PlanejamentoCabecalho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoCabecalho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdPlanejamento = Column(Integer, primary_key=True, autoincrement=True)
    DataCriacao = Column(DateTime, default=datetime.now)
    UsuarioCriacao = Column(String(50)) 
    Status = Column(String(20), default='Rascunho')
    
    # Mantive as colunas string para facilitar a leitura rápida, 
    # mas o vínculo real acontece nos IDs abaixo
    AeroportoOrigem = Column(String(3)) 
    AeroportoDestino = Column(String(3)) 
    
    # NOVAS CHAVES ESTRANGEIRAS (FK)
    IdAeroportoOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)
    IdAeroportoDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)

    TotalVolumes = Column(Integer, default=0)
    TotalPeso = Column(Numeric(10,2), default=0.00)
    TotalValor = Column(Numeric(15,2), default=0.00)

    # Relacionamentos Internos
    Itens = relationship("PlanejamentoItem", back_populates="Cabecalho", cascade="all, delete-orphan")
    Trechos = relationship("PlanejamentoTrecho", back_populates="Cabecalho", cascade="all, delete-orphan")

    # Relacionamentos Externos (Com Aeroporto)
    # Usamos foreign_keys para diferenciar Origem de Destino
    AeroportoOrigemObj = relationship("Aeroporto", foreign_keys=[IdAeroportoOrigem])
    AeroportoDestinoObj = relationship("Aeroporto", foreign_keys=[IdAeroportoDestino])


class PlanejamentoItem(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoItem'
    __table_args__ = {'schema': 'intec.dbo'}

    IdItem = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Filial = Column(String(10))
    Serie = Column(String(5))
    Ctc = Column(String(20))
    DataEmissao = Column(DateTime)
    Hora = Column(String(5))
    Remetente = Column(String(100))
    Destinatario = Column(String(100))
    
    # Strings originais
    OrigemCidade = Column(String(50))
    DestinoCidade = Column(String(50))

    # NOVAS CHAVES ESTRANGEIRAS (FK) PARA CIDADES
    IdCidadeOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Cidade.Id'), nullable=True)
    IdCidadeDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Cidade.Id'), nullable=True)

    Volumes = Column(Integer)
    PesoTaxado = Column(Numeric(10,3))
    ValMercadoria = Column(Numeric(15,2))
    IndConsolidado = Column(Boolean, default=False)
    
    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Itens")

    # Relacionamentos Externos (Com Cidade)
    CidadeOrigemObj = relationship("Cidade", foreign_keys=[IdCidadeOrigem])
    CidadeDestinoObj = relationship("Cidade", foreign_keys=[IdCidadeDestino])


class PlanejamentoTrecho(Base):
    __tablename__ = 'Tb_PLN_PlanejamentoTrecho'
    __table_args__ = {'schema': 'intec.dbo'}

    IdTrecho = Column(Integer, primary_key=True, autoincrement=True)
    IdPlanejamento = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_PlanejamentoCabecalho.IdPlanejamento'))
    Ordem = Column(Integer, nullable=False)
    
    CiaAerea = Column(String(50))
    NumeroVoo = Column(String(20))
    
    # NOVA CHAVE ESTRANGEIRA PARA A MALHA AÉREA
    # Nullable=True pois pode ser um voo charter ou rodoviário que não está na malha importada
    IdVoo = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Voo.Id'), nullable=True)

    AeroportoOrigem = Column(String(3))
    AeroportoDestino = Column(String(3))

    # NOVAS CHAVES ESTRANGEIRAS PARA AEROPORTOS (Trecho)
    IdAeroportoOrigem = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)
    IdAeroportoDestino = Column(Integer, ForeignKey('intec.dbo.Tb_PLN_Aeroporto.Id'), nullable=True)

    DataPartida = Column(DateTime)
    DataChegada = Column(DateTime)
    StatusTrecho = Column(String(20), default='Previsto')

    Cabecalho = relationship("PlanejamentoCabecalho", back_populates="Trechos")
    
    # Relacionamentos Externos
    VooObj = relationship("VooMalha", foreign_keys=[IdVoo])
    AeroportoOrigemObj = relationship("Aeroporto", foreign_keys=[IdAeroportoOrigem])
    AeroportoDestinoObj = relationship("Aeroporto", foreign_keys=[IdAeroportoDestino])