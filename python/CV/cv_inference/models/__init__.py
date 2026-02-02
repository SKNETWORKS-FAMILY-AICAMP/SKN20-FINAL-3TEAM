"""
CV 모델 래퍼 모듈
"""

from .base_model import BaseModel
from .obj_model import OBJModel
from .ocr_model import OCRModel
from .str_model import STRModel
from .spa_model import SPAModel

__all__ = ['BaseModel', 'OBJModel', 'OCRModel', 'STRModel', 'SPAModel']
