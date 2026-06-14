from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.animal import Animal
from app.models.parto import Parto
from app.schemas.animais import AnimalCriar, AnimalResposta, AnimalAtualizar
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.cloudinary_config import upload_foto_animal, deletar_foto_animal
from datetime import date
from typing import List

roteador = APIRouter(
    prefix="/animais",
    tags=["Animais"]
)


def validar_animal(animal_data, usuario_id, banco, animal_id=None):
    # Data de nascimento não pode ser no futuro
    if animal_data.nascimento and animal_data.nascimento > date.today():
        raise HTTPException(status_code=400, detail="Data de nascimento não pode ser no futuro")

    # Brinco único por produtor
    if animal_data.brinco:
        query = banco.query(Animal).filter(
            Animal.brinco == animal_data.brinco,
            Animal.usuario_id == usuario_id
        )
        if animal_id:
            query = query.filter(Animal.id != animal_id)
        if query.first():
            raise HTTPException(status_code=400, detail="Já existe um animal com esse brinco cadastrado")

    # Apenas fêmeas podem ter produção de leite
    if animal_data.sexo == "M" and animal_data.producao_diaria_litros and animal_data.producao_diaria_litros > 0:
        raise HTTPException(status_code=400, detail="Apenas fêmeas podem ter produção de leite registrada")

    # Apenas fêmeas podem ter status reprodutivo feminino
    if animal_data.sexo == "M" and animal_data.status_reprodutivo in ("vazia", "prenha", "em_cio", "em_lactacao", "seca"):
        raise HTTPException(status_code=400, detail="Status reprodutivo feminino não se aplica a machos")


@roteador.get("/", response_model=List[AnimalResposta])
def listar_animais(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Animal).filter(Animal.usuario_id == usuario.id).all()


@roteador.get("/ativos", response_model=List[AnimalResposta])
def listar_animais_ativos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Animal).filter(
        Animal.usuario_id == usuario.id,
        Animal.status == "ativo"
    ).all()


@roteador.get("/em-lactacao", response_model=List[AnimalResposta])
def listar_animais_em_lactacao(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Animal).filter(
        Animal.usuario_id == usuario.id,
        Animal.status == "ativo",
        Animal.status_reprodutivo == "em_lactacao"
    ).all()


@roteador.get("/{animal_id}", response_model=AnimalResposta)
def buscar_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    return animal


@roteador.post("/", response_model=AnimalResposta)
def criar_animal(
    animal: AnimalCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    validar_animal(animal, usuario.id, banco)
    novo_animal = Animal(**animal.model_dump(), usuario_id=usuario.id)
    banco.add(novo_animal)
    banco.commit()
    banco.refresh(novo_animal)
    return novo_animal


@roteador.put("/{animal_id}", response_model=AnimalResposta)
def atualizar_animal(
    animal_id: int,
    dados: AnimalAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")

    # Aplicar os novos dados antes de validar
    dados_atualizados = dados.model_dump(exclude_unset=True)
    for campo, valor in dados_atualizados.items():
        setattr(animal, campo, valor)

    validar_animal(animal, usuario.id, banco, animal_id=animal_id)

    banco.commit()
    banco.refresh(animal)
    return animal


@roteador.delete("/{animal_id}")
def deletar_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")

    # Não deletar — apenas marcar como inativo para preservar histórico
    animal.status = "inativo"
    banco.commit()
    return {"mensagem": f"Animal '{animal.nome}' desativado com sucesso. Histórico preservado."}


@roteador.post("/{animal_id}/foto", response_model=AnimalResposta)
def upload_foto(
    animal_id: int,
    foto: UploadFile = File(...),
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")

    # Validar tipo de arquivo
    tipos_permitidos = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if foto.content_type not in tipos_permitidos:
        raise HTTPException(status_code=400, detail="Formato inválido. Use JPG, PNG ou WEBP")

    # Validar tamanho (máx 5MB)
    conteudo = foto.file.read()
    if len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto muito grande. Tamanho máximo: 5MB")

    # Fazer upload para o Cloudinary
    url = upload_foto_animal(conteudo, animal_id)
    animal.foto_url = url
    banco.commit()
    banco.refresh(animal)
    return animal


@roteador.delete("/{animal_id}/foto")
def remover_foto(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    if not animal.foto_url:
        raise HTTPException(status_code=404, detail="Este animal não possui foto cadastrada")

    deletar_foto_animal(animal_id)
    animal.foto_url = None
    banco.commit()
    return {"mensagem": "Foto removida com sucesso"}