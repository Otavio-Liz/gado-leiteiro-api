from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.usuario import Usuario
from app.schemas.usuarios import UsuarioCreate
from app.security import verificar_senha, gerar_hash_senha
from app.auth import criar_token

roteador = APIRouter(prefix="/usuarios", tags=["Usuários"])

@roteador.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(pegar_banco)):
    usuario = db.query(Usuario).filter(Usuario.username == form.username).first()
    if not usuario or not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos"
        )
    token = criar_token({"sub": usuario.username})
    return {"access_token": token, "token_type": "bearer"}

@roteador.post("/cadastrar")
def cadastrar(dados: UsuarioCreate, db: Session = Depends(pegar_banco)):
    usuario_existente = db.query(Usuario).filter(Usuario.username == dados.username).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Usuário já existe")
    novo_usuario = Usuario(
        username=dados.username,
        senha_hash=gerar_hash_senha(dados.senha)
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return {"mensagem": "Usuário criado com sucesso!"}