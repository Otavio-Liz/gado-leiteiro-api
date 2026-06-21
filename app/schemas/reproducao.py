from pydantic import BaseModel, field_validator, model_validator, Field
from datetime import date, datetime
from typing import Optional


# ─── Reprodução ──────────────────────────────────────────────────────────────
#
# Mesmo padrão de Ocorrência: separada em Campos/Criar/Atualizar/Resposta.
# ReproducaoResposta herda só de ReproducaoCampos (nunca de ReproducaoCriar),
# para um registro legado não derrubar o GET com 500.

TIPOS_COBERTURA = ("inseminacao_artificial", "monta_natural", "transferencia_embriao")
RESULTADOS_DIAGNOSTICO = ("positivo", "negativo", "inconclusivo")


class ReproducaoCampos(BaseModel):
    animal_id:              int = Field(gt=0)
    data_cio:               Optional[date] = None
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = Field(default=None, max_length=100)
    partida_semen:          Optional[str] = Field(default=None, max_length=60)
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = Field(default=None, max_length=80)
    observacao:             Optional[str] = Field(default=None, max_length=500)


class ReproducaoCriar(ReproducaoCampos):
    """
    Usado SOMENTE na criação (POST). Validações de data como field_validators
    individuais (não model_validator), cada um apontando pro campo certo.
    data_cio/data_cobertura/data_diagnostico são validadas em cascata porque
    estão declaradas nessa ordem em ReproducaoCampos — cada uma já está
    disponível em info.data quando a próxima roda.
    """

    @field_validator("tipo_cobertura")
    @classmethod
    def validar_tipo_cobertura(cls, v):
        if v is not None and v not in TIPOS_COBERTURA:
            raise ValueError(f"Tipo de cobertura deve ser um de: {TIPOS_COBERTURA}")
        return v

    @field_validator("resultado_diagnostico")
    @classmethod
    def validar_resultado(cls, v):
        if v is not None and v not in RESULTADOS_DIAGNOSTICO:
            raise ValueError(f"Resultado deve ser um de: {RESULTADOS_DIAGNOSTICO}")
        return v

    @field_validator("data_cio")
    @classmethod
    def validar_data_cio(cls, v):
        if v and v > date.today():
            raise ValueError("Data do cio não pode ser no futuro.")
        return v

    @field_validator("data_cobertura")
    @classmethod
    def validar_data_cobertura(cls, v, info):
        if v and v > date.today():
            raise ValueError("Data de cobertura não pode ser no futuro.")
        data_cio = info.data.get("data_cio")
        if v and data_cio and v < data_cio:
            raise ValueError("Data de cobertura não pode ser antes do cio.")
        return v

    @field_validator("data_diagnostico")
    @classmethod
    def validar_data_diagnostico(cls, v, info):
        if v and v > date.today():
            raise ValueError("Data do diagnóstico não pode ser no futuro.")
        data_cobertura = info.data.get("data_cobertura")
        if v and data_cobertura and v < data_cobertura:
            raise ValueError("Data do diagnóstico não pode ser antes da cobertura.")
        return v


class ReproducaoAtualizar(BaseModel):
    """
    Usado na edição (PUT). Todos os campos opcionais — validação cruzada de
    datas com model_validator aqui (mesmo critério de OcorrenciaAtualizar):
    como qualquer campo pode não vir no corpo da requisição, um field_validator
    individual não teria como comparar de forma confiável.
    """
    data_cio:               Optional[date] = None
    tipo_cobertura:         Optional[str] = None
    data_cobertura:         Optional[date] = None
    touro_reprodutor:       Optional[str] = Field(default=None, max_length=100)
    partida_semen:          Optional[str] = Field(default=None, max_length=60)
    data_diagnostico:       Optional[date] = None
    resultado_diagnostico:  Optional[str] = None
    metodo_diagnostico:     Optional[str] = Field(default=None, max_length=80)
    observacao:             Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_cobertura")
    @classmethod
    def validar_tipo_cobertura(cls, v):
        if v is not None and v not in TIPOS_COBERTURA:
            raise ValueError(f"Tipo de cobertura deve ser um de: {TIPOS_COBERTURA}")
        return v

    @field_validator("resultado_diagnostico")
    @classmethod
    def validar_resultado(cls, v):
        if v is not None and v not in RESULTADOS_DIAGNOSTICO:
            raise ValueError(f"Resultado deve ser um de: {RESULTADOS_DIAGNOSTICO}")
        return v

    @model_validator(mode="after")
    def validar_datas(self):
        hoje = date.today()
        if self.data_cio and self.data_cio > hoje:
            raise ValueError("Data do cio não pode ser no futuro")
        if self.data_cobertura and self.data_cobertura > hoje:
            raise ValueError("Data de cobertura não pode ser no futuro")
        if self.data_cobertura and self.data_cio and self.data_cobertura < self.data_cio:
            raise ValueError("Data de cobertura não pode ser antes do cio")
        if self.data_diagnostico and self.data_diagnostico > hoje:
            raise ValueError("Data do diagnóstico não pode ser no futuro")
        if self.data_diagnostico and self.data_cobertura and self.data_diagnostico < self.data_cobertura:
            raise ValueError("Data do diagnóstico não pode ser antes da cobertura")
        return self


class ReproducaoResposta(ReproducaoCampos):
    """
    animal_nome é preenchido pelo router (montar_resposta_reproducao).
    data_prevista_parto e data_inicio_periodo_seco são calculados pelo
    backend a partir de data_cobertura (283 e 223 dias) — nunca recebidos
    como entrada, só retornados.
    """
    id:                         int
    animal_nome:                Optional[str] = None
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