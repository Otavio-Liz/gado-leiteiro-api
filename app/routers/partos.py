from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.parto import Parto
from app.models.animal import Animal
from app.schemas.partos import PartoCriar, PartoResposta, PartoAtualizar
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_partos
from datetime import date, timedelta
from typing import List

roteador = APIRouter(
    prefix="/partos",
    tags=["Partos"]
)


def validar_parto(dados, banco, usuario_id, parto_id=None):
    animal = banco.query(Animal).filter(
        Animal.id == dados.animal_id,
        Animal.usuario_id == usuario_id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")
    if animal.sexo == "M":
        raise HTTPException(status_code=400, detail="Machos não podem ter partos registrados.")
    if animal.status not in ("ativo", "seco"):
        raise HTTPException(
            status_code=400,
            detail=f"Animal está '{animal.status}' e não pode ter partos registrados."
        )

    # Nota: a checagem de "data não pode ser no futuro" foi movida para
    # app/schemas/partos.py (field_validator de data_parto), pois é uma
    # regra pura de campo que não depende de consulta ao banco. Não
    # duplicar aqui.

    query = banco.query(Parto).filter(Parto.animal_id == dados.animal_id)
    if parto_id:
        query = query.filter(Parto.id != parto_id)
    partos_existentes = query.order_by(Parto.data_parto.desc()).all()

    for parto_existente in partos_existentes:
        diferenca = abs((dados.data_parto - parto_existente.data_parto).days)
        if diferenca < 270:
            raise HTTPException(
                status_code=400,
                detail=f"Intervalo mínimo entre partos é de 9 meses. Parto anterior em {parto_existente.data_parto}."
            )

    if dados.data_inicio_periodo_seco and dados.data_inicio_periodo_seco >= dados.data_parto:
        raise HTTPException(status_code=400, detail="Período seco deve ser antes do parto.")

    return animal


def validar_brinco_cria_disponivel(brinco_cria, banco, usuario_id):
    """
    Checa duplicidade de brinco_cria contra a tabela Animal, usando a mesma
    regra de unicidade de brinco já aplicada em validar_animal (animais.py).
    Só é chamada quando status_cria == "vivo" (cria vai se tornar um Animal).
    Existe também um índice único no banco (ix_animais_usuario_brinco) como
    segunda linha de defesa, caso esta checagem deixe passar por algum motivo.
    """
    existente = banco.query(Animal).filter(
        Animal.brinco == brinco_cria,
        Animal.usuario_id == usuario_id
    ).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail=f"Já existe um animal com o brinco '{brinco_cria}' cadastrado."
        )


def validar_dados_cria_viva(parto):
    """
    Se a cria nasceu viva, ela vai se tornar um Animal de verdade (ver
    criar_animal_a_partir_da_cria), e Animal exige brinco+sexo. Nome é
    opcional — se não informado, o Animal é criado com nome "Brinco {brinco}".
    """
    if parto.status_cria != "vivo":
        return

    erros = []
    if not parto.brinco_cria or not parto.brinco_cria.strip():
        erros.append({"campo": "brinco_cria", "mensagem": "Brinco da cria é obrigatório quando a cria está viva."})
    if not parto.sexo_cria:
        erros.append({"campo": "sexo_cria", "mensagem": "Sexo da cria é obrigatório quando a cria está viva."})

    if erros:
        raise HTTPException(status_code=400, detail=erros)


def montar_resposta_parto(parto):
    """
    Converte um objeto Parto (SQLAlchemy) em PartoResposta, preenchendo
    animal_nome e animal_foto_url a partir do relacionamento parto.animal
    (a mãe) — campos que não existem na tabela partos e por isso não vêm
    automaticamente via from_attributes.
    """
    resposta = PartoResposta.model_validate(parto)
    resposta.animal_nome = parto.animal.nome if parto.animal else None
    resposta.animal_foto_url = parto.animal.foto_url if parto.animal else None
    return resposta


def criar_animal_a_partir_da_cria(parto, animal_mae, usuario_id):
    """
    Monta (sem persistir ainda) o registro de Animal correspondente à cria
    nascida viva. Nome é opcional: se não informado, usa "Brinco {brinco}"
    como nome padrão, que o usuário pode editar depois em Animais.jsx.
    """
    nome = parto.nome_cria.strip() if parto.nome_cria and parto.nome_cria.strip() else f"Brinco {parto.brinco_cria}"
    return Animal(
        usuario_id=usuario_id,
        nome=nome,
        brinco=parto.brinco_cria,
        sexo=parto.sexo_cria,
        nascimento=parto.data_parto,
        nome_mae=animal_mae.nome,
        peso_kg=parto.peso_cria_kg,
        status="ativo",
        status_reprodutivo="nao_aplicavel",
        quantidade_partos=0,
    )


@roteador.get("/", response_model=List[PartoResposta])
def listar_partos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        partos = banco.query(Parto).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).all()
        return [montar_resposta_parto(p) for p in partos]
    except Exception:
        logger_partos.error(f"Erro ao listar partos | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar partos. Tente novamente."
        )


@roteador.get("/alertas-parto-proximo", response_model=List[dict])
def alertas_parto_proximo(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        animais = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.data_prevista_parto.between(hoje, limite)
        ).all()

        if not animais:
            return []

        return [
            {
                "animal_id": a.id,
                "animal_nome": a.nome,
                "animal_brinco": a.brinco,
                "data_prevista_parto": a.data_prevista_parto,
                "dias_restantes": (a.data_prevista_parto - hoje).days
            }
            for a in animais
        ]
    except Exception:
        logger_partos.error(f"Erro ao buscar alertas de parto | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar alertas de parto. Tente novamente."
        )


@roteador.get("/animal/{animal_id}", response_model=List[PartoResposta])
def listar_partos_por_animal(
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
        partos = banco.query(Parto).filter(
            Parto.animal_id == animal_id
        ).order_by(Parto.data_parto.desc()).all()
        return [montar_resposta_parto(p) for p in partos]
    except HTTPException:
        raise
    except Exception:
        logger_partos.error(f"Erro ao listar partos do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar partos do animal. Tente novamente."
        )


@roteador.post("/", response_model=PartoResposta)
def criar_parto(
    parto: PartoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        animal_mae = validar_parto(parto, banco, usuario.id)

        # Se a cria nasceu viva, ela se torna um Animal de verdade no
        # sistema. Primeiro confirma que os dados mínimos exigidos por
        # Animal estão presentes; só então checa duplicidade de brinco
        # (evita uma consulta ao banco desnecessária se já vai falhar
        # por dados incompletos).
        novo_animal_cria = None
        if parto.status_cria == "vivo":
            validar_dados_cria_viva(parto)
            validar_brinco_cria_disponivel(parto.brinco_cria, banco, usuario.id)
            novo_animal_cria = criar_animal_a_partir_da_cria(parto, animal_mae, usuario.id)

        carencia_encerra_em = parto.data_parto + timedelta(days=parto.dias_carencia_colostro)

        novo_parto = Parto(
            **parto.model_dump(),
            carencia_encerra_em=carencia_encerra_em
        )
        banco.add(novo_parto)

        if novo_animal_cria is not None:
            banco.add(novo_animal_cria)

        # Atualização automática dos dados reprodutivos da mãe ao parir.
        animal_mae.status_reprodutivo = "em_lactacao"
        animal_mae.data_prevista_parto = None
        animal_mae.dias_em_lactacao = 0
        animal_mae.quantidade_partos = (animal_mae.quantidade_partos or 0) + 1
        animal_mae.data_ultimo_parto = parto.data_parto

        # Um único commit: parto, animal-cria (se houver) e atualização
        # da mãe são salvos atomicamente. Se algo falhar antes deste
        # ponto, nada foi persistido ainda.
        banco.commit()
        banco.refresh(novo_parto)

        if novo_animal_cria is not None:
            logger_partos.info(
                f"Parto registrado com cria viva | animal_mae: {parto.animal_id} | "
                f"brinco_cria: {parto.brinco_cria} | usuário: {usuario.id}"
            )
        else:
            logger_partos.info(f"Parto registrado | animal: {parto.animal_id} | usuário: {usuario.id}")

        return montar_resposta_parto(novo_parto)
    except HTTPException:
        banco.rollback()
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao registrar parto | animal: {parto.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar parto. Tente novamente."
        )


@roteador.put("/{parto_id}", response_model=PartoResposta)
def atualizar_parto(
    parto_id: int,
    dados: PartoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if parto_id <= 0:
        raise HTTPException(status_code=400, detail="ID do parto inválido.")
    try:
        parto = banco.query(Parto).join(Animal).filter(
            Parto.id == parto_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not parto:
            raise HTTPException(status_code=404, detail="Parto não encontrado.")

        data_parto_nova = dados.data_parto if dados.data_parto is not None else parto.data_parto
        status_cria_novo = dados.status_cria if dados.status_cria is not None else parto.status_cria

        if data_parto_nova > date.today():
            raise HTTPException(
                status_code=400,
                detail="Data do parto não pode ser no futuro."
            )

        # Revalida dados da cria viva no PUT — no POST isso já acontecia
        # via validar_dados_cria_viva, mas no PUT não havia revalidação.
        # Sem isso, era possível editar um parto pra "cria viva" sem
        # informar brinco ou sexo, deixando o registro inconsistente.
        if status_cria_novo == "vivo":
            brinco_cria = dados.brinco_cria if dados.brinco_cria is not None else parto.brinco_cria
            sexo_cria = dados.sexo_cria if dados.sexo_cria is not None else parto.sexo_cria
            if not brinco_cria:
                raise HTTPException(
                    status_code=400,
                    detail="Brinco da cria é obrigatório quando a cria está viva."
                )
            if not sexo_cria:
                raise HTTPException(
                    status_code=400,
                    detail="Sexo da cria é obrigatório quando a cria está viva."
                )
            # Checa duplicidade de brinco (excluindo o próprio parto)
            brinco_existente = banco.query(Animal).filter(
                Animal.brinco == brinco_cria,
                Animal.usuario_id == usuario.id,
                Animal.id != parto.animal_cria_id if parto.animal_cria_id else True
            ).first()
            if brinco_existente:
                raise HTTPException(
                    status_code=400,
                    detail=f"Brinco '{brinco_cria}' já está em uso por outro animal."
                )

        dias_carencia = dados.dias_carencia_colostro if dados.dias_carencia_colostro is not None else parto.dias_carencia_colostro

        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(parto, campo, valor)

        # Recalcula carência após aplicar as mudanças — se a data do parto
        # ou os dias de carência mudaram, a data de encerramento precisa
        # ser atualizada pra continuar bloqueando produções corretamente.
        if dados.data_parto is not None or dados.dias_carencia_colostro is not None:
            parto.carencia_encerra_em = data_parto_nova + timedelta(days=dias_carencia)

        banco.commit()
        banco.refresh(parto)
        logger_partos.info(f"Parto atualizado | id: {parto_id} | usuário: {usuario.id}")
        return montar_resposta_parto(parto)
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao atualizar parto | id: {parto_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar parto. Tente novamente."
        )


@roteador.delete("/{parto_id}")
def deletar_parto(
    parto_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if parto_id <= 0:
        raise HTTPException(status_code=400, detail="ID do parto inválido.")
    try:
        parto = banco.query(Parto).join(Animal).filter(
            Parto.id == parto_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not parto:
            raise HTTPException(status_code=404, detail="Parto não encontrado.")

        mae = banco.query(Animal).filter(Animal.id == parto.animal_id).first()

        banco.delete(parto)
        banco.flush()

        if mae:
            # Recalcula quantidade_partos — conta partos restantes após a
            # exclusão. Sem isso, o contador ficava incrementado pra sempre
            # mesmo após o parto ser apagado.
            mae.quantidade_partos = banco.query(Parto).filter(
                Parto.animal_id == mae.id
            ).count()

            # Recalcula data_ultimo_parto — busca o parto mais recente que
            # sobrou depois da exclusão.
            ultimo_parto = banco.query(Parto).filter(
                Parto.animal_id == mae.id
            ).order_by(Parto.data_parto.desc()).first()
            mae.data_ultimo_parto = ultimo_parto.data_parto if ultimo_parto else None

            # Recalcula status_reprodutivo — sem isso, a mãe ficava em
            # "em_lactacao" pra sempre mesmo após o parto que gerou esse
            # status ser apagado. A regra é: se ainda há partos, mantém
            # em_lactacao; se não há mais nenhum parto, volta pra "vazia"
            # (a menos que haja uma reprodução ativa mais recente, que é
            # gerenciada pelo próprio router de reprodução).
            if mae.quantidade_partos > 0:
                # Ainda tem partos — mantém em lactação
                mae.status_reprodutivo = "em_lactacao"
            else:
                # Nenhum parto restante — volta pra vazia
                # (o router de reprodução pode sobrescrever isso se houver
                # reprodução ativa, mas aqui garantimos que o parto apagado
                # não deixa rastro no status da mãe)
                if mae.sexo == "F":
                    mae.status_reprodutivo = "vazia"
                else:
                    mae.status_reprodutivo = "nao_aplicavel"

        # Animal-cria permanece ativo (decisão de negócio: o usuário decide
        # se apaga o bezerro separadamente). Só desvincula o parto do
        # animal-cria pra não deixar referência órfã — o animal-cria
        # continua no sistema normalmente, mas sem o vínculo ao parto que
        # foi apagado.
        if parto.animal_cria_id:
            cria = banco.query(Animal).filter(
                Animal.id == parto.animal_cria_id
            ).first()
            if cria:
                # Nenhuma ação no animal-cria — permanece ativo.
                # Comentário aqui só pra deixar explícito que foi uma
                # decisão consciente, não esquecimento.
                pass

        banco.commit()
        logger_partos.info(f"Parto deletado | id: {parto_id} | usuário: {usuario.id}")
        return {"mensagem": "Parto removido com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao deletar parto | id: {parto_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover parto. Tente novamente."
        )