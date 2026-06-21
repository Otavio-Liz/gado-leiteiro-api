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
#
# Separada em Campos/Criar/Resposta (mesmo padrão de Partos/Vacinas/Medicamentos):
# OcorrenciaResposta herda só de OcorrenciaCampos (sem validators de regra de
# negócio), nunca de OcorrenciaCriar — assim um registro legado (ex: tipo
# antigo, ou data_resolucao antes de data_ocorrencia por correção manual) não
# derruba o GET com 500.
#
# TIPOS_OCORRENCIA: lista única, usada pelos dois validators abaixo e também
# referenciada pelo router para validar o enum do banco em sincronia.

TIPOS_OCORRENCIA = ("doenca", "lesao", "exame", "acidente", "comportamento", "outro")


class OcorrenciaCampos(BaseModel):
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


class OcorrenciaCriar(OcorrenciaCampos):
    """
    Usado SOMENTE na criação (POST). Validações de data como field_validators
    individuais (não model_validator) para que cada erro aponte para o campo
    certo no loc[] do Pydantic.
    """

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v):
        if v not in TIPOS_OCORRENCIA:
            raise ValueError(f"Tipo deve ser um de: {TIPOS_OCORRENCIA}")
        return v

    @field_validator("dias_afastamento")
    @classmethod
    def validar_dias_afastamento(cls, v):
        if v < 0:
            raise ValueError("Dias de afastamento não pode ser negativo")
        return v

    @field_validator("data_ocorrencia")
    @classmethod
    def validar_data_nao_futura(cls, v):
        if v > date.today():
            raise ValueError("Data da ocorrência não pode ser no futuro.")
        return v

    @field_validator("data_resolucao")
    @classmethod
    def validar_data_resolucao(cls, v, info):
        # data_ocorrencia está declarada antes de data_resolucao em
        # OcorrenciaCampos, então já está disponível em info.data.
        data_ocorrencia = info.data.get("data_ocorrencia")
        if v and data_ocorrencia and v < data_ocorrencia:
            raise ValueError("Data de resolução não pode ser antes da data da ocorrência.")
        if v and v > date.today():
            raise ValueError("Data de resolução não pode ser no futuro.")
        return v


class OcorrenciaAtualizar(BaseModel):
    """
    Usado na edição (PUT). Todos os campos opcionais — por isso a validação
    cruzada de datas usa model_validator aqui (mesmo critério adotado em
    VacinaAtualizar): como ambos os campos podem não vir no corpo da
    requisição, um field_validator individual não teria como comparar os
    dois de forma confiável.
    """
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
        if v is not None and v not in TIPOS_OCORRENCIA:
            raise ValueError(f"Tipo deve ser um de: {TIPOS_OCORRENCIA}")
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
        if self.data_resolucao and self.data_resolucao > date.today():
            raise ValueError("Data de resolução não pode ser no futuro")
        return self


class OcorrenciaResposta(OcorrenciaCampos):
    """
    Usado para SERIALIZAR ocorrências já existentes (GET, retorno de
    POST/PUT). Herda apenas de OcorrenciaCampos — nunca de OcorrenciaCriar.

    animal_nome e resolvida são preenchidos pelo router (montar_resposta_ocorrencia):
    - animal_nome vem do relacionamento ocorrencia.animal.
    - resolvida é derivado de data_resolucao ser ou não nula — não existe
      coluna "resolvida" no banco, o status é sempre calculado a partir da
      data, para nunca haver duas fontes de verdade desincronizadas.
    """
    id:             int
    animal_nome:    Optional[str] = None
    resolvida:      bool = False
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True