from pydantic import BaseModel, field_validator, Field
from datetime import date, datetime
from typing import Optional


class PartoCampos(BaseModel):
    """
    Campos compartilhados de Parto. Usada como base estrutural (nomes e
    tipos de campo) tanto pela entrada (PartoCriar) quanto pela saída
    (PartoResposta).

    IMPORTANTE: a regra "nome/brinco/sexo da cria são obrigatórios quando
    status_cria é vivo" NÃO está aqui, nem em PartoCriar — está no router
    (ver validar_dados_cria_viva em app/routers/partos.py), como uma
    função Python simples, em vez de field_validator do Pydantic. Isso é
    intencional: essa regra só deve valer para dados que estão sendo
    criados agora, nunca para a serialização de partos já existentes no
    banco (GET, ou retorno de POST/PUT). Se essa regra estivesse no
    schema (mesmo só em PartoCriar) e PartoResposta herdasse de uma
    classe que a contém, o FastAPI quebraria ao devolver QUALQUER parto
    legado que não satisfizesse essa regra — foi exatamente isso que
    causou o bug do GET /partos/ retornando 500 em uma versão anterior
    deste arquivo.
    """
    animal_id:                int = Field(gt=0)
    data_parto:               date
    tipo_parto:               str = "normal"
    status_cria:              str = "vivo"
    sexo_cria:                Optional[str] = None
    nome_cria:                Optional[str] = Field(default=None, max_length=100)
    brinco_cria:              Optional[str] = Field(default=None, max_length=50)
    peso_cria_kg:             Optional[int] = None
    dias_carencia_colostro:   int = 7
    data_inicio_periodo_seco: Optional[date] = None
    observacao:               Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_parto")
    @classmethod
    def validar_tipo_parto(cls, v):
        opcoes = ("normal", "cesariana", "distocico")
        if v not in opcoes:
            raise ValueError(f"Tipo de parto deve ser um de: {opcoes}")
        return v

    @field_validator("status_cria")
    @classmethod
    def validar_status_cria(cls, v):
        opcoes = ("vivo", "morto", "natimorto")
        if v not in opcoes:
            raise ValueError(f"Status da cria deve ser um de: {opcoes}")
        return v

    @field_validator("sexo_cria")
    @classmethod
    def validar_sexo_cria(cls, v):
        if v is not None and v not in ("F", "M"):
            raise ValueError("Sexo da cria deve ser 'F' ou 'M'")
        return v

    @field_validator("dias_carencia_colostro")
    @classmethod
    def validar_carencia(cls, v):
        if v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("peso_cria_kg")
    @classmethod
    def validar_peso_cria(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso da cria deve ser maior que zero")
        return v


class PartoCriar(PartoCampos):
    """
    Usado SOMENTE na criação (POST). A obrigatoriedade condicional de
    nome/brinco/sexo da cria (quando status_cria="vivo") é validada no
    router, não aqui — ver nota em PartoCampos.
    """

    @field_validator("data_parto")
    @classmethod
    def validar_data_parto_nao_futura(cls, v):
        if v > date.today():
            raise ValueError("Data do parto não pode ser no futuro.")
        return v


class PartoAtualizar(BaseModel):
    """
    Usado na edição (PUT). Todos os campos opcionais (atualização parcial).
    A criação do Animal-cria automática só ocorre em criar_parto (POST);
    atualizar_parto (PUT) não recria nem modifica o Animal já existente.
    """
    data_parto:               Optional[date] = None
    tipo_parto:               Optional[str] = None
    status_cria:              Optional[str] = None
    sexo_cria:                Optional[str] = None
    nome_cria:                Optional[str] = Field(default=None, max_length=100)
    brinco_cria:              Optional[str] = Field(default=None, max_length=50)
    peso_cria_kg:             Optional[int] = None
    dias_carencia_colostro:   Optional[int] = None
    data_inicio_periodo_seco: Optional[date] = None
    observacao:               Optional[str] = Field(default=None, max_length=500)

    @field_validator("data_parto")
    @classmethod
    def validar_data_parto_nao_futura(cls, v):
        if v is not None and v > date.today():
            raise ValueError("Data do parto não pode ser no futuro.")
        return v

    @field_validator("tipo_parto")
    @classmethod
    def validar_tipo_parto(cls, v):
        if v is not None:
            opcoes = ("normal", "cesariana", "distocico")
            if v not in opcoes:
                raise ValueError(f"Tipo de parto deve ser um de: {opcoes}")
        return v

    @field_validator("status_cria")
    @classmethod
    def validar_status_cria(cls, v):
        if v is not None:
            opcoes = ("vivo", "morto", "natimorto")
            if v not in opcoes:
                raise ValueError(f"Status da cria deve ser um de: {opcoes}")
        return v

    @field_validator("sexo_cria")
    @classmethod
    def validar_sexo_cria(cls, v):
        if v is not None and v not in ("F", "M"):
            raise ValueError("Sexo da cria deve ser 'F' ou 'M'")
        return v

    @field_validator("dias_carencia_colostro")
    @classmethod
    def validar_carencia(cls, v):
        if v is not None and v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("peso_cria_kg")
    @classmethod
    def validar_peso_cria(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso da cria deve ser maior que zero")
        return v


class PartoResposta(PartoCampos):
    """
    Usado para SERIALIZAR partos já existentes (GET, retorno de POST/PUT).
    Herda apenas de PartoCampos — nunca de PartoCriar — para nunca aplicar
    a regra de obrigatoriedade condicional a dados que já estão salvos.

    animal_nome e animal_foto_url não são colunas da tabela partos — são
    preenchidos manualmente pelo router (lendo Parto.animal, o relationship
    já existente com a mãe) antes de devolver a resposta. Sem isso, o
    Pydantic não teria de onde tirar esses valores ao usar from_attributes
    direto a partir do objeto Parto puro.
    """
    id:                  int
    animal_nome:          Optional[str] = None
    animal_foto_url:      Optional[str] = None
    carencia_encerra_em: Optional[date] = None
    criado_em:           Optional[datetime] = None
    atualizado_em:       Optional[datetime] = None

    class Config:
        from_attributes = True
