from django.core.exceptions import ValidationError


def validate_image_file(image):
    """Validate uploaded image file size and content type."""
    max_size = 5 * 1024 * 1024  # 5 MB
    allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

    if image.size > max_size:
        raise ValidationError(
            f'La imagen no debe superar {max_size // (1024 * 1024)} MB. '
            f'Tamaño actual: {image.size / (1024 * 1024):.1f} MB.'
        )
    if hasattr(image, 'content_type') and image.content_type not in allowed_types:
        raise ValidationError(
            f'Formato de imagen no soportado: {image.content_type}. '
            f'Formatos permitidos: JPEG, PNG, WebP, GIF.'
        )
