from pydantic import BaseModel, field_validator, model_validator, Field
from datetime import date, datetime
from typing import Optional


class VacinaCampos(BaseModel):
    """
    Campos compartilhados de Vacina. Base estrutural usada tanto pela
    entrada (VacinaCriar) quanto pela saída (VacinaResposta).

    IMPORTANTE: o model_validator de datas NÃO está aqui — está em
    VacinaCriar. Motivo idêntico ao de Partos: VacinaResposta herda desta
    classe para serializar vacinas JÁ EXISTENTES no banco (incluindo
    legados), e um model_validator aqui quebraria o GET se houvesse
    qualquer registro com datas inconsistentes salvo antes desta regra
    existir.
    """
    animal_id:       int = Field(gt=0)
    nome_vacina:     str = Field(min_length=1, max_length=100)
    doenca_alvo:     Optional[str] = Field(default=None, max_length=100)
    data_aplicacao:  date
    proxima_dose:    Optional[date] = None
    lote:            Optional[str] = Field(default=None, max_length=50)
    validade_vacina: Optional[date] = None
    dose_aplicada:   Optional[str] = Field(default=None, max_length=50)
    via_aplicacao:   Optional[str] = Field(default=None, max_length=50)
    responsavel:     Optional[str] = Field(default=None, max_length=100)
    observacao:      Optional[str] = Field(default=None, max_length=500)


class VacinaCriar(VacinaCampos):
    """
    Usado SOMENTE na criação (POST). Validações de datas como field_validators
    individuais (não model_validator) para que cada erro aponte para o campo
    certo no loc[] do Pydantic — permitindo ao handler_validacao montar
    detalhes[] com o campo correto e ao frontend exibir o balão no campo certo.
    """

    @field_validator("data_aplicacao")
    @classmethod
    def validar_data_aplicacao_nao_futura(cls, v):
        if v > date.today():
            raise ValueError("Data de aplicação não pode ser no futuro.")
        return v

    @field_validator("proxima_dose")
    @classmethod
    def validar_proxima_dose(cls, v, info):
        # data_aplicacao está declarada antes de proxima_dose em VacinaCampos,
        # então já está disponível em info.data quando este validator roda.
        data_aplicacao = info.data.get("data_aplicacao")
        if v and data_aplicacao and v <= data_aplicacao:
            raise ValueError("Próxima dose deve ser depois da data de aplicação.")
        return v

    @field_validator("validade_vacina")
    @classmethod
    def validar_validade_vacina(cls, v, info):
        data_aplicacao = info.data.get("data_aplicacao")
        if v and data_aplicacao and v < data_aplicacao:
            raise ValueError("Não é possível aplicar uma vacina vencida.")
        return v


class VacinaAtualizar(BaseModel):
    """
    Usado na edição (PUT). Todos os campos opcionais.
    """
    nome_vacina:     Optional[str] = Field(default=None, min_length=1, max_length=100)
    doenca_alvo:     Optional[str] = Field(default=None, max_length=100)
    data_aplicacao:  Optional[date] = None
    proxima_dose:    Optional[date] = None
    lote:            Optional[str] = Field(default=None, max_length=50)
    validade_vacina: Optional[date] = None
    dose_aplicada:   Optional[str] = Field(default=None, max_length=50)
    via_aplicacao:   Optional[str] = Field(default=None, max_length=50)
    responsavel:     Optional[str] = Field(default=None, max_length=100)
    observacao:      Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validar_datas(self):
        if self.proxima_dose and self.data_aplicacao:
            if self.proxima_dose <= self.data_aplicacao:
                raise ValueError("Próxima dose deve ser depois da data de aplicação")
        if self.validade_vacina and self.data_aplicacao:
            if self.validade_vacina < self.data_aplicacao:
                raise ValueError("Vacina não pode ser aplicada após a data de validade")
        return self


class VacinaResposta(VacinaCampos):
    """
    Usado para SERIALIZAR vacinas já existentes (GET, retorno de POST/PUT).
    Herda apenas de VacinaCampos — nunca de VacinaCriar — para nunca
    aplicar validações de entrada a dados já salvos no banco.
    animal_nome e animal_foto_url são preenchidos pelo router a partir
    do relacionamento vacina.animal.
    """
    id:              int
    animal_nome:     Optional[str] = None
    animal_foto_url: Optional[str] = None
    criado_em:       Optional[datetime] = None
    atualizado_em:   Optional[datetime] = None

    class Config:
        from_attributes = True