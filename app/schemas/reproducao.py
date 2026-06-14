from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional


# ─── Reprodução ──────────────────────────────────────────────────────────────

class ReproducaoBase(BaseModel):
    animal_id:              int

    # Cio
    data_cio:               Optional[date] = None

    # Cobertura
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = None
    partida_semen:          Optional[str] = None

    # Diagnóstico
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = None

    observacao:             Optional[str] = None

    @validator("tipo_cobertura")
    def validar_tipo_cobertura(cls, v):
        if v is not None:
            opcoes = ("inseminacao_artificial", "monta_natural", "transferencia_embriao")
            if v not in opcoes:
                raise ValueError(f"Tipo de cobertura deve ser um de: {opcoes}")
        return v

    @validator("resultado_diagnostico")
    def validar_resultado(cls, v):
        if v is not None:
            opcoes = ("positivo", "negativo", "inconclusivo")
            if v not in opcoes:
                raise ValueError(f"Resultado deve ser um de: {opcoes}")
        return v

    @validator("data_cobertura")
    def validar_data_cobertura(cls, v, values):
        if v and values.get("data_cio") and v < values["data_cio"]:
            raise ValueError("Data de cobertura não pode ser antes do cio")
        return v

    @validator("data_diagnostico")
    def validar_data_diagnostico(cls, v, values):
        if v and values.get("data_cobertura") and v < values["data_cobertura"]:
            raise ValueError("Data do diagnóstico não pode ser antes da cobertura")
        return v


class ReproducaoCriar(ReproducaoBase):
    pass


class ReproducaoAtualizar(BaseModel):
    data_cio:               Optional[date] = None
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = None
    partida_semen:          Optional[str] = None
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = None
    observacao:             Optional[str] = None


class ReproducaoResposta(ReproducaoBase):
    id:                         int
    data_prevista_parto:        Optional[date] = None
    data_inicio_periodo_seco:   Optional[date] = None
    criado_em:                  Optional[datetime] = None
    atualizado_em:              Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Ocorrência Sanitária ─────────────────────────────────────────────────────

class OcorrenciaBase(BaseModel):
    animal_id:          int
    tipo:               str = "outro"
    descricao:          str
    data_ocorrencia:    date
    data_resolucao:     Optional[date] = None
    resultado_exame:    Optional[str] = None
    afeta_producao:     bool = False
    dias_afastamento:   int = 0
    responsavel:        Optional[str] = None
    observacao:         Optional[str] = None

    @validator("tipo")
    def validar_tipo(cls, v):
        opcoes = ("doenca", "exame", "acidente", "outro")
        if v not in opcoes:
            raise ValueError(f"Tipo deve ser um de: {opcoes}")
        return v

    @validator("data_resolucao")
    def validar_data_resolucao(cls, v, values):
        if v and values.get("data_ocorrencia") and v < values["data_ocorrencia"]:
            raise ValueError("Data de resolução não pode ser antes da data da ocorrência")
        return v

    @validator("dias_afastamento")
    def validar_dias_afastamento(cls, v):
        if v < 0:
            raise ValueError("Dias de afastamento não pode ser negativo")
        return v


class OcorrenciaCriar(OcorrenciaBase):
    pass


class OcorrenciaAtualizar(BaseModel):
    tipo:               Optional[str] = None
    descricao:          Optional[str] = None
    data_ocorrencia:    Optional[date] = None
    data_resolucao:     Optional[date] = None
    resultado_exame:    Optional[str] = None
    afeta_producao:     Optional[bool] = None
    dias_afastamento:   Optional[int] = None
    responsavel:        Optional[str] = None
    observacao:         Optional[str] = None


class OcorrenciaResposta(OcorrenciaBase):
    id:             int
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True