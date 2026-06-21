import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import HTTPException, status
import os

load_dotenv(override=True)

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    raise RuntimeError("Credenciais do Cloudinary não definidas no ambiente.")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)


def upload_foto_animal(conteudo: bytes, animal_id: int) -> str:
    try:
        resultado = cloudinary.uploader.upload(
            conteudo,
            folder="gado_leiteiro/animais",
            public_id=f"animal_{animal_id}",
            overwrite=True,
        )
        return resultado["secure_url"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao fazer upload da imagem: {str(e)}"
        )


def deletar_foto_animal(animal_id: int) -> None:
    try:
        cloudinary.uploader.destroy(f"gado_leiteiro/animais/animal_{animal_id}")
    except Exception:
        pass
