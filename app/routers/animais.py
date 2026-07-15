from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import pegar_banco
from app.models.animal import Animal
from app.models.producao import Producao
from app.models.parto import Parto
from app.models.reproducao import Reproducao
from app.schemas.animais import AnimalCriar, AnimalResposta, AnimalAtualizar
from sqlalchemy.exc import IntegrityError
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.cloudinary_config import upload_foto_animal, deletar_foto_animal
from app.logger import logger_animais
from datetime import date
from typing import List
from PIL import Image
import io

roteador = APIRouter(
    prefix="/animais",
    tags=["Animais"]
)


def _tem_historico_vinculado(animal_id, banco):
    """
    True se o animal já tem QUALQUER registro real vinculado — produção,
    parto (como mãe) ou reprodução. Usado para impedir trocar o sexo de
    um animal que já tem histórico incompatível com essa troca (ex: uma
    fêmea com partos registrados virando "macho").

    Checa só existência (.first(), não .count()) — mais barato, já que só
    precisamos saber se existe pelo menos um registro, não quantos.
    """
    return (
        banco.query(Producao).filter(Producao.animal_id == animal_id).first() is not None
        or banco.query(Parto).filter(Parto.animal_id == animal_id).first() is not None
        or banco.query(Reproducao).filter(Reproducao.animal_id == animal_id).first() is not None
    )


def validar_animal(animal_data, usuario_id, banco, animal_id=None, sexo_antigo=None):
    if animal_data.nascimento and animal_data.nascimento > date.today():
        raise HTTPException(
            status_code=400,
            detail="Data de nascimento não pode ser no futuro."
        )
    brinco_duplicado = False
    if animal_data.brinco:
        query = banco.query(Animal).filter(
            Animal.brinco == animal_data.brinco,
            Animal.usuario_id == usuario_id
        )
        if animal_id:
            query = query.filter(Animal.id != animal_id)
        if query.first():
            brinco_duplicado = True

    nome_duplicado = False
    if animal_data.nome:
        query = banco.query(Animal).filter(
            func.lower(Animal.nome) == animal_data.nome.lower(),
            Animal.usuario_id == usuario_id
        )
        if animal_id:
            query = query.filter(Animal.id != animal_id)
        if query.first():
            nome_duplicado = True

    # Se os dois falharem juntos, devolve uma lista com os dois erros,
    # cada um já indicando o campo certo (mesmo formato usado pela
    # validação automática do Pydantic: [{campo, mensagem}]).
    if brinco_duplicado and nome_duplicado:
        raise HTTPException(
            status_code=400,
            detail=[
                {"campo": "brinco", "mensagem": "Já existe um animal com esse brinco cadastrado."},
                {"campo": "nome", "mensagem": "Já existe um animal com esse nome cadastrado."},
            ]
        )
    if brinco_duplicado:
        raise HTTPException(
            status_code=400,
            detail="Já existe um animal com esse brinco cadastrado."
        )
    if nome_duplicado:
        raise HTTPException(
            status_code=400,
            detail="Já existe um animal com esse nome cadastrado."
        )
    if animal_data.sexo == "M" and animal_data.producao_diaria_litros and animal_data.producao_diaria_litros > 0:
        raise HTTPException(
            status_code=400,
            detail="Apenas fêmeas podem ter produção de leite registrada."
        )
    if animal_data.sexo == "M" and animal_data.status_reprodutivo in ("vazia", "prenha", "em_cio", "em_lactacao", "seca"):
        raise HTTPException(
            status_code=400,
            detail="Status reprodutivo feminino não se aplica a machos."
        )

    # Só faz sentido checar histórico vinculado numa EDIÇÃO (animal_id
    # existe) onde o sexo está de fato mudando — na criação não há
    # histórico ainda, e se o sexo não mudou não há nada a proteger.
    if animal_id and sexo_antigo is not None and animal_data.sexo != sexo_antigo:
        if _tem_historico_vinculado(animal_id, banco):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível trocar o sexo deste animal: já existem "
                    "produções, partos ou reproduções registradas para ele. "
                    "Se foi um erro de cadastro sem histórico real, contate o suporte."
                )
            )


@roteador.get("/", response_model=List[AnimalResposta])
def listar_animais(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Animal).filter(Animal.usuario_id == usuario.id).all()
    except Exception:
        logger_animais.error(f"Erro ao listar animais | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animais. Tente novamente."
        )


@roteador.get("/ativos", response_model=List[AnimalResposta])
def listar_animais_ativos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo"
        ).all()
    except Exception:
        logger_animais.error(f"Erro ao listar animais ativos | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animais ativos. Tente novamente."
        )


@roteador.get("/em-lactacao", response_model=List[AnimalResposta])
def listar_animais_em_lactacao(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.status_reprodutivo == "em_lactacao"
        ).all()
    except Exception:
        logger_animais.error(f"Erro ao listar animais em lactação | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animais em lactação. Tente novamente."
        )


@roteador.get("/{animal_id}", response_model=AnimalResposta)
def buscar_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        return animal
    except HTTPException:
        raise
    except Exception:
        logger_animais.error(f"Erro ao buscar animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animal. Tente novamente."
        )


@roteador.post("/", response_model=AnimalResposta)
def criar_animal(
    animal: AnimalCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    validar_animal(animal, usuario.id, banco)
    try:
        novo_animal = Animal(**animal.model_dump(), usuario_id=usuario.id)
        banco.add(novo_animal)
        banco.commit()
        banco.refresh(novo_animal)
        logger_animais.info(f"Animal criado | {animal.nome} | usuário: {usuario.id}")
        return novo_animal
    except HTTPException:
        raise
    except IntegrityError:
        # Corrida entre duas requisições simultâneas com o mesmo brinco:
        # a checagem de duplicidade em validar_animal já rodou e passou,
        # mas o índice único do banco pegou a violação no commit. Deixa
        # propagar pro handler global (handler_integridade em erros.py),
        # que já sabe transformar isso num 409 com mensagem amigável —
        # não duplica essa lógica aqui.
        banco.rollback()
        raise
    except Exception:
        banco.rollback()
        logger_animais.error(f"Erro ao criar animal | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao cadastrar animal. Tente novamente."
        )


@roteador.put("/{animal_id}", response_model=AnimalResposta)
def atualizar_animal(
    animal_id: int,
    dados: AnimalAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")

        sexo_antigo = animal.sexo

        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(animal, campo, valor)

        validar_animal(animal, usuario.id, banco, animal_id=animal_id, sexo_antigo=sexo_antigo)

        banco.commit()
        banco.refresh(animal)
        logger_animais.info(f"Animal atualizado | id: {animal_id} | usuário: {usuario.id}")
        return animal
    except HTTPException:
        raise
    except IntegrityError:
        # Mesmo motivo do POST: deixa o handler global (handler_integridade)
        # cuidar da mensagem — evita duplicar a lógica de detecção aqui.
        banco.rollback()
        raise
    except Exception:
        banco.rollback()
        logger_animais.error(f"Erro ao atualizar animal | id: {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar animal. Tente novamente."
        )


@roteador.delete("/{animal_id}")
def deletar_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        animal.status = "inativo"
        banco.commit()
        logger_animais.info(f"Animal desativado | id: {animal_id} | usuário: {usuario.id}")
        return {"mensagem": f"Animal '{animal.nome}' desativado com sucesso. Histórico preservado."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_animais.error(f"Erro ao desativar animal | id: {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao desativar animal. Tente novamente."
        )


@roteador.post("/{animal_id}/foto", response_model=AnimalResposta)
def upload_foto(
    animal_id: int,
    foto: UploadFile = File(...),
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")

    tipos_permitidos = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if foto.content_type not in tipos_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido. Use JPG, PNG ou WEBP."
        )

    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")

        conteudo = foto.file.read()
        if len(conteudo) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Foto muito grande. Tamanho máximo: 5MB."
            )

        # O content_type do passo acima vem do cliente e pode ser falsificado
        # (é só um texto no cabeçalho da requisição) — aqui confere o conteúdo
        # real do arquivo, abrindo-o de fato como imagem.
        try:
            imagem_verificacao = Image.open(io.BytesIO(conteudo))
            imagem_verificacao.verify()
            imagem_formato = Image.open(io.BytesIO(conteudo)).format  # verify() invalida o objeto, reabre pra checar o formato
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Arquivo não é uma imagem válida."
            )
        if imagem_formato not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(
                status_code=400,
                detail="Formato inválido. Use JPG, PNG ou WEBP."
            )

        url = upload_foto_animal(conteudo, animal_id)
        animal.foto_url = url
        banco.commit()
        banco.refresh(animal)
        logger_animais.info(f"Foto do animal atualizada | id: {animal_id} | usuário: {usuario.id}")
        return animal
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_animais.error(f"Erro no upload de foto | animal: {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao fazer upload da foto. Tente novamente."
        )


@roteador.delete("/{animal_id}/foto")
def remover_foto(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        if not animal.foto_url:
            raise HTTPException(
                status_code=404,
                detail="Este animal não possui foto cadastrada."
            )
        deletar_foto_animal(animal_id)
        animal.foto_url = None
        banco.commit()
        logger_animais.info(f"Foto do animal removida | id: {animal_id} | usuário: {usuario.id}")
        return {"mensagem": "Foto removida com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_animais.error(f"Erro ao remover foto | animal: {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao remover foto. Tente novamente."
        )