from pydantic import BaseModel, field_validator, model_validator, Field
from datetime import date, datetime
from typing import Optional


# ─── Reprodução ──────────────────────────────────────────────────────────────

class ReproducaoBase(BaseModel):
    animal_id:              int = Field(gt=0)
    data_cio:               Optional[date] = None
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = Field(default=None, max_length=100)
    partida_semen:          Optional[str] = Field(default=None, max_length=100)
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = Field(default=None, max_length=100)
    observacao:             Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_cobertura")
    @classmethod
    def validar_tipo_cobertura(cls, v):
        if v is not None:
            opcoes = ("inseminacao_artificial", "monta_natural", "transferencia_embriao")
            if v not in opcoes:
                raise ValueError(f"Tipo de cobertura deve ser um de: {opcoes}")
        return v

    @field_validator("resultado_diagnostico")
    @classmethod
    def validar_resultado(cls, v):
        if v is not None:
            opcoes = ("positivo", "negativo", "inconclusivo")
            if v not in opcoes:
                raise ValueError(f"Resultado deve ser um de: {opcoes}")
        return v

    @model_validator(mode="after")
    def validar_datas(self):
        if self.data_cobertura and self.data_cio and self.data_cobertura < self.data_cio:
            raise ValueError("Data de cobertura não pode ser antes do cio")
        if self.data_diagnostico and self.data_cobertura and self.data_diagnostico < self.data_cobertura:
            raise ValueError("Data do diagnóstico não pode ser antes da cobertura")
        return self


class ReproducaoCriar(ReproducaoBase):
    pass


class ReproducaoAtualizar(BaseModel):
    data_cio:               Optional[date] = None
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = Field(default=None, max_length=100)
    partida_semen:          Optional[str] = Field(default=None, max_length=100)
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = Field(default=None, max_length=100)
    observacao:             Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_cobertura")
    @classmethod
    def validar_tipo_cobertura(cls, v):
        if v is not None:
            opcoes = ("inseminacao_artificial", "monta_natural", "transferencia_embriao")
            if v not in opcoes:
                raise ValueError(f"Tipo de cobertura deve ser um de: {opcoes}")
        return v

    @field_validator("resultado_diagnostico")
    @classmethod
    def validar_resultado(cls, v):
        if v is not None:
            opcoes = ("positivo", "negativo", "inconclusivo")
            if v not in opcoes:
                raise ValueError(f"Resultado deve ser um de: {opcoes}")
        return v

    @model_validator(mode="after")
    def validar_datas(self):
        if self.data_cobertura and self.data_cio and self.data_cobertura < self.data_cio:
            raise ValueError("Data de cobertura não pode ser antes do cio")
        if self.data_diagnostico and self.data_cobertura and self.data_diagnostico < self.data_cobertura:
            raise ValueError("Data do diagnóstico não pode ser antes da cobertura")
        return self


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
    animal_id:          int = Field(gt=0)
    tipo:               str = "outro"
    descricao:          str = Field(min_length=1, max_length=500)
    data_ocorrencia:    date
    data_resolucao:     Optional[date] = None
    resultado_exame:    Optional[str] = Field(default=None, max_length=300)
    afeta_producao:     bool = False
    dias_afastamento:   int = 0
    responsavel:        Optional[str] = Field(default=None, max_length=100)
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v):
        opcoes = ("doenca", "exame", "acidente", "outro")
        if v not in opcoes:
            raise ValueError(f"Tipo deve ser um de: {opcoes}")
        return v

    @field_validator("dias_afastamento")
    @classmethod
    def validar_dias_afastamento(cls, v):
        if v < 0:
            raise ValueError("Dias de afastamento não pode ser negativo")
        return v

    @model_validator(mode="after")
    def validar_data_resolucao(self):
        if self.data_resolucao and self.data_ocorrencia and self.data_resolucao < self.data_ocorrencia:
            raise ValueError("Data de resolução não pode ser antes da data da ocorrência")
        return self


class OcorrenciaCriar(OcorrenciaBase):
    pass


class OcorrenciaAtualizar(BaseModel):
    tipo:               Optional[str] = None
    descricao:          Optional[str] = Field(default=None, min_length=1, max_length=500)
    data_ocorrencia:    Optional[date] = None
    data_resolucao:     Optional[date] = None
    resultado_exame:    Optional[str] = Field(default=None, max_length=300)
    afeta_producao:     Optional[bool] = None
    dias_afastamento:   Optional[int] = None
    responsavel:        Optional[str] = Field(default=None, max_length=100)
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v):
        if v is not None:
            opcoes = ("doenca", "exame", "acidente", "outro")
            if v not in opcoes:
                raise ValueError(f"Tipo deve ser um de: {opcoes}")
        return v

    @field_validator("dias_afastamento")
    @classmethod
    def validar_dias_afastamento(cls, v):
        if v is not None and v < 0:
            raise ValueError("Dias de afastamento não pode ser negativo")
        return v

    @model_validator(mode="after")
    def validar_data_resolucao(self):
        if self.data_resolucao and self.data_ocorrencia and self.data_resolucao < self.data_ocorrencia:
            raise ValueError("Data de resolução não pode ser antes da data da ocorrência")
        return self


class OcorrenciaResposta(OcorrenciaBase):
    id:             int
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True