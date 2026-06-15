import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import HTTPException, status
import os

load_dotenv()

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

TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TAMANHO_MAXIMO_MB = 5


def validar_arquivo(arquivo) -> None:
    """Valida tipo e tamanho do arquivo antes do upload."""
    if hasattr(arquivo, "content_type") and arquivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de arquivo não permitido. Use JPEG, PNG ou WebP."
        )
    if hasattr(arquivo, "size") and arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo muito grande. Tamanho máximo: {TAMANHO_MAXIMO_MB}MB."
        )


def upload_foto_animal(arquivo, animal_id: int) -> str:
    """
    Faz upload da foto do animal para o Cloudinary.
    Retorna a URL segura da imagem.
    """
    validar_arquivo(arquivo)

    try:
        resultado = cloudinary.uploader.upload(
            arquivo,
            folder="gado_leiteiro/animais",
            public_id=f"animal_{animal_id}",
            overwrite=True,
            transformation=[
                {"width": 800, "height": 600, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]
        )
        return resultado["secure_url"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao fazer upload da imagem. Tente novamente."
        )


def deletar_foto_animal(animal_id: int) -> None:
    """Remove a foto do animal do Cloudinary."""
    try:
        cloudinary.uploader.destroy(f"gado_leiteiro/animais/animal_{animal_id}")
    except Exception:
        pass  # Se a foto não existir, ignora silenciosamente