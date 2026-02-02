"""
OCR 모델 래퍼 (YOLOv5 + CRNN)
- YOLOv5: 텍스트 영역 검출
- CRNN: 텍스트 인식
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import cv2
import numpy as np
import re
from typing import List, Dict, Any
from pathlib import Path
from torchvision.models import resnet18

from .base_model import BaseModel


class CRNN(nn.Module):
    """CRNN 모델 (CNN + RNN)"""

    def __init__(self, num_chars, resnet, rnn_hidden_size=256, dropout=0.1):
        super(CRNN, self).__init__()
        self.num_chars = num_chars
        self.rnn_hidden_size = rnn_hidden_size
        self.dropout = dropout

        # CNN Part 1
        resnet_modules = list(resnet.children())[:-3]
        self.cnn_p1 = nn.Sequential(*resnet_modules)

        # CNN Part 2
        self.cnn_p2 = nn.Sequential(
            nn.Conv2d(256, 256, kernel_size=(3, 6), stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True)
        )
        self.linear1 = nn.Linear(1024, 256)

        # RNN
        self.rnn1 = nn.GRU(
            input_size=rnn_hidden_size,
            hidden_size=rnn_hidden_size,
            bidirectional=True,
            batch_first=True
        )
        self.rnn2 = nn.GRU(
            input_size=rnn_hidden_size,
            hidden_size=rnn_hidden_size,
            bidirectional=True,
            batch_first=True
        )
        self.linear2 = nn.Linear(self.rnn_hidden_size * 2, num_chars)

    def forward(self, batch):
        batch = self.cnn_p1(batch)
        batch = self.cnn_p2(batch)
        batch = batch.permute(0, 3, 1, 2)
        batch_size = batch.size(0)
        T = batch.size(1)
        batch = batch.view(batch_size, T, -1)
        batch = self.linear1(batch)
        batch, hidden = self.rnn1(batch)
        feature_size = batch.size(2)
        batch = batch[:, :, :feature_size // 2] + batch[:, :, feature_size // 2:]
        batch, hidden = self.rnn2(batch)
        batch = self.linear2(batch)
        batch = batch.permute(1, 0, 2)
        return batch


def remove_duplicates(text: str) -> str:
    """중복 문자 제거"""
    if len(text) > 1:
        letters = [text[0]] + [
            letter for idx, letter in enumerate(text[1:], start=1)
            if text[idx] != text[idx - 1]
        ]
    elif len(text) == 1:
        letters = [text[0]]
    else:
        return ""
    return "".join(letters)


def correct_prediction(word: str, remove_word: str = '갱') -> str:
    """예측 결과 후처리 - 중복 제거"""
    parts = word.split("-")
    parts = [remove_duplicates(part) for part in parts]
    corrected_word = "".join(parts)
    corrected_word = corrected_word.replace(remove_word, '')
    return corrected_word


def correct_word(word: str) -> str:
    """OCR 결과 보정 - 정규표현식 기반"""
    word = re.sub(r'\s', '', word)
    word = re.sub(r'^ELEH홀$|^ELEV홀$|^ELE홀$|^ELV홀$|^ELV\.홀$|^ELEV\.홀$|^EL홀$|^ELE홀$|^ELEV홀$|^다LV홀$|^ELE.홀$|^ELEV.L$|^ELEV\.\.$', 'ELEV.홀', word)
    word = re.sub(r'^ELEHAL$|^ELE\.HAL$|^ELE\.HAL$|^ELE\.AL$|^ELEHL$|^ELEVHAL$|^ELEHAL$|^ELE.HALL$|^ELE.HL$|^EEV\./?스+$|^E\.H대스$|^EL.V크$', 'ELEV.HALL', word)
    word = re.sub(r'^ELEV\s도$|^ELE\s?도$|^ELE\s?홀$|^ELE홀$|^ELV홀$|^ELEV도$', 'ELEV.복도', word)
    word = re.sub(r'^가스룸$', '가스배관', word)
    word = re.sub(r'^[계|거|기][족|욕]실$', '가족실', word)
    word = re.sub(r'^가족부욕실$', '가족욕실', word)
    word = re.sub(r'^거구실$|^거단실$', '거실', word)
    word = re.sub(r'^거\w{2,}실$', '거실/침실', word)
    word = re.sub(r'^\w스룸$', '게스트룸', word)
    word = re.sub(r'^발용욕실$|^공욕실$|^공용실$', '공용욕실', word)
    word = re.sub(r'^기본더형$|^기공방$|^기본?실$|^기형$|^거형$|^기당$|^가\s?당$|^드형$|^평룸$', '기본형', word)
    word = re.sub(r'^다가스룸$', '다가구주택', word)
    word = re.sub(r'^다스$', '다락', word)
    word = re.sub(r'^다공방$', '다락방', word)
    word = re.sub(r'^다용실$|^다도실$', '다용도실', word)
    word = re.sub(r'^단위기니$|^단[위|외|코]대$|^단위실$|^발위대$|^단세대$|^발코대$|^단대$|^축대$', '단위세대', word)
    word = re.sub(r'^대피.*$|^대.*간$', '대피공간', word)
    word = re.sub(r'^주마당$|^옥당$', '뒷마당', word)
    word = re.sub(r'^드스+$', '드레', word)
    word = re.sub(r'^드레스스$|^드레스$|^드스룸$|^드레룸$', '드레스룸', word)
    word = re.sub(r'^펜인관$|^하인관$', '메인현관', word)
    word = re.sub(r'^발코.*$|^발/?기.*$|^발코/?스기?실$|^발코/?식실$|^발코스식기실$|^발코외스기$|^발코니[기|니|스|실|/]+$|^발코스니$|^발코/실$|^발코[스|식|실]+$|^발외니$|^부코[니|실]$|^실외니$|^발실$', '발코니', word)
    word = re.sub(r'^발니$|^니$', '방', word)
    word = re.sub(r'^보일니$|^부일니$|^보니$|^보일$', '보일러', word)
    word = re.sub(r'^부일러실$|^보일실$|^도러실$|^도라실$', '보일러실', word)
    word = re.sub(r'^보레스주방$|^보조[스|주]+방$|^보레스방$', '보조주방', word)
    word = re.sub(r'^부욕실$|^부부실$|^부실$', '부부욕실', word)
    word = re.sub(r'^부러실$', '부부침실', word)
    word = re.sub(r'^스당$', '식당', word)
    word = re.sub(r'^실기$', '실외기', word)
    word = re.sub(r'^기외기실$|^기피기실$|^실외실$|^부기실$|^실기실$', '실외기실', word)
    word = re.sub(r'^안실$|^안니$|^안코$', '안방', word)
    word = re.sub(r'^알파공?실$|^알파간$|^알파실$', '알파공간', word)
    word = re.sub(r'^욕니$|^화실$', '욕실', word)
    word = re.sub(r'^계녀방$|^주녀방$|^지당$', '자녀방', word)
    word = re.sub(r'^주및$', '주방및', word)
    word = re.sub(r'^주및식당$', '주방및식당', word)
    word = re.sub(r'^주방/식식당$|^주/식당$|^주방/?당$|^주식당$|^주방당$', '주방/식당', word)
    word = re.sub(r'^확장장$|^주장$', '주차장', word)
    word = re.sub(r'^주장형$', '주출입구', word)
    word = re.sub(r'^침고$', '창고', word)
    word = re.sub(r'^축당$|^욕척$|^축실$', '축척', word)
    word = re.sub(r'^침관$', '침실', word)
    word = re.sub(r'^테라[식|니|기]{1,2}$|^테스$|^테\w스$', '테라스', word)
    word = re.sub(r'^파우더실$|^파우룸$|^펜트룸$', '파우더룸', word)
    word = re.sub(r'^평면도[실|식]$|^평면도+$|^평면[실|니]$|^평[도|실|니]$|^평도[도|실]$|^평면$', '평면도', word)
    word = re.sub(r'^하향식난구$|^하향식피구$|^하향식입구$|^하향\w{2,}$', '하향식피난구', word)
    word = re.sub(r'^욕장실$', '화장실', word)
    word = re.sub(r'^화장방$|^화방$|^확형$|^확장$|^욕형$', '확장형', word)
    word = re.sub(r'^현[실|식]$|^현관.*$', '현관', word)
    return word


class OCRModel(BaseModel):
    """OCR 모델 (YOLOv5 + CRNN)"""

    def __init__(self, yolo_config, crnn_config, inference_config):
        super().__init__(yolo_config)
        self.crnn_config = crnn_config
        self.inference_config = inference_config
        self.yolo_path = inference_config.YOLO_PATH
        self.crnn = None
        self.idx2char = None
        self.remove_word = None

    def load_model(self) -> None:
        """YOLOv5 + CRNN 모델 로드"""
        # YOLOv5 로드
        self.model = torch.hub.load(
            str(self.yolo_path),
            'custom',
            str(self.config.model_path),
            source='local',
            _verbose=False
        )
        self.model.conf = self.config.conf_threshold
        self.model.iou = self.config.iou_threshold

        # Vocabulary 로드
        vocab_path = self.inference_config.VOCABULARY_PATH
        with open(vocab_path, 'r', encoding='utf-8') as f:
            vocabulary = list(f.read().strip())

        self.idx2char = {k: v for k, v in enumerate(vocabulary, start=0)}
        self.idx2char[len(self.idx2char)] = '@'
        num_chars = len(self.idx2char)

        # Remove word 로드
        remove_word_path = self.inference_config.REMOVE_WORD_PATH
        with open(remove_word_path, 'r', encoding='utf-8') as f:
            self.remove_word = f.read().strip()

        # CRNN 로드
        resnet = resnet18(pretrained=True)
        self.crnn = CRNN(num_chars, resnet, rnn_hidden_size=256)
        self.crnn.load_state_dict(torch.load(str(self.crnn_config.model_path), map_location=self.device))
        self.crnn = self.crnn.to(self.device)
        self.crnn.eval()

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """원본 이미지 전처리"""
        rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        bh, bw = rgb_img.shape[:2]
        return rgb_img[:bh // 32 * 32, :bw // 32 * 32, :]

    def inference(self, preprocessed_input: np.ndarray) -> List[Dict]:
        """YOLOv5 + CRNN 추론"""
        # 텍스트 영역 검출
        yolo_result = self.model(preprocessed_input, size=4960).pandas().xyxy[0]
        yolo_result[['xmin', 'ymin', 'xmax', 'ymax']] = \
            yolo_result[['xmin', 'ymin', 'xmax', 'ymax']].apply(np.ceil).astype(int)

        # 각 영역에 대해 CRNN으로 텍스트 인식
        ocr_results = []
        for _, row in yolo_result.iterrows():
            bbox = [int(row['xmin']), int(row['ymin']),
                    int(row['xmax']), int(row['ymax'])]

            # CRNN 입력 이미지 생성
            crnn_input = self._make_crnn_input(bbox, preprocessed_input)

            # CRNN 추론
            with torch.no_grad():
                text_logits = self.crnn(crnn_input.to(self.device))
                text_pred = self._decode_predictions(text_logits.cpu())
                corrected_text = correct_prediction(text_pred, self.remove_word)
                final_text = correct_word(corrected_text)

            ocr_results.append({
                'bbox': bbox,
                'confidence': float(row['confidence']),
                'text': final_text
            })

        return ocr_results

    def postprocess(self, raw_output: List[Dict], original_size: tuple) -> List[Dict]:
        """표준 annotation 형식으로 변환"""
        annotations = []

        for idx, item in enumerate(raw_output):
            bbox = item['bbox']
            annotation = {
                "id": idx,
                "category_id": 21,  # OCR
                "category_name": "OCR",
                "bbox": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
                "segmentation": [],
                "area": (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
                "confidence": item['confidence'],
                "iscrowd": 0,
                "attributes": {
                    "OCR": item['text']
                }
            }
            annotations.append(annotation)

        return annotations

    def _make_crnn_input(self, bbox: List[int], image: np.ndarray) -> torch.Tensor:
        """CRNN 입력 이미지 생성 (60x250)"""
        base_img = np.ones((60, 250, 3), dtype=np.uint8) * 255

        ix1 = np.clip(bbox[0] - 5, 0, image.shape[1])
        iy1 = np.clip(bbox[1] - 5, 0, image.shape[0])
        ix2 = np.clip(bbox[2] + 5, 0, image.shape[1])
        iy2 = np.clip(bbox[3] + 5, 0, image.shape[0])

        height = np.clip(iy2 - iy1, 0, 60)
        width = np.clip(ix2 - ix1, 0, 250)

        top = int(np.round((60 - height) / 2))

        cropped = image[iy1:iy2, ix1:ix2, :]
        cropped = cropped[:60, :250, :]
        h, w = cropped.shape[:2]

        base_img[top:top + h, 0:w, :] = cropped

        input_tensor = torch.from_numpy(
            base_img.transpose(2, 0, 1) / 255
        ).type(torch.FloatTensor).unsqueeze(0)

        return input_tensor

    def _decode_predictions(self, text_batch_logits: torch.Tensor) -> str:
        """CRNN 출력 디코딩"""
        text_batch_tokens = F.softmax(text_batch_logits, 2).argmax(2)
        text_batch_tokens = text_batch_tokens.numpy().T

        text = [self.idx2char[idx] for idx in text_batch_tokens[0]]
        return "".join(text)
