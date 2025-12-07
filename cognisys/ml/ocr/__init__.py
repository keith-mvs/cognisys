"""
IFMOS ML - OCR Module
GPU-accelerated OCR for document processing
"""

from .gpu_ocr_engine import GPUOCREngine


def create_ocr_engine(use_gpu=True, languages=['en']):
    """
    Factory function to create OCR engine instance.

    Args:
        use_gpu: Whether to use GPU acceleration (default: True)
        languages: List of language codes (default: ['en'])

    Returns:
        GPUOCREngine instance
    """
    return GPUOCREngine(use_gpu=use_gpu, languages=languages)


__all__ = ['GPUOCREngine', 'create_ocr_engine']
