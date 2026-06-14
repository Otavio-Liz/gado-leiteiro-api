import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


def upload_foto_animal(arquivo, animal_id: int) -> str:
    """
    Faz upload da foto do animal para o Cloudinary.
    Retorna a URL segura da imagem.
    """
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


def deletar_foto_animal(animal_id: int):
    """Remove a foto do animal do Cloudinary."""
    cloudinary.uploader.destroy(f"gado_leiteiro/animais/animal_{animal_id}")