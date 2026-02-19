"""
진행률 추적 및 중단/재개 지원
"""

import json
from pathlib import Path
from typing import List, Set


class ProgressTracker:
    """
    작업 진행률 추적 및 중단/재개 지원

    JSON 파일로 완료된 항목을 기록하여 중단 후 재개 시
    이미 완료된 작업을 건너뛸 수 있음
    """

    def __init__(self, progress_file: Path):
        """
        Args:
            progress_file: 진행률을 저장할 JSON 파일 경로
        """
        self.progress_file = progress_file
        self.completed: Set[str] = set()
        self.failed: List[str] = []

        # 기존 진행률 로드
        self._load()

    def _load(self):
        """기존 진행률 파일 로드"""
        if self.progress_file.exists():
            try:
                data = json.loads(self.progress_file.read_text(encoding='utf-8'))
                self.completed = set(data.get('completed', []))
                self.failed = data.get('failed', [])

                if self.completed:
                    print(f"📦 기존 진행률 로드: {len(self.completed)}개 완료, {len(self.failed)}개 실패")
            except Exception as e:
                print(f"⚠️  진행률 파일 로드 실패: {e}")
                self.completed = set()
                self.failed = []

    def _save(self):
        """진행률 파일 저장"""
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'completed': sorted(list(self.completed)),
                'failed': self.failed
            }
            self.progress_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"⚠️  진행률 파일 저장 실패: {e}")

    def is_completed(self, item_id: str) -> bool:
        """
        항목이 이미 완료됐는지 확인

        Args:
            item_id: 항목 식별자 (예: 이미지 stem)

        Returns:
            이미 완료됐으면 True
        """
        return item_id in self.completed

    def mark_completed(self, item_id: str):
        """
        항목을 완료로 표시

        Args:
            item_id: 항목 식별자
        """
        self.completed.add(item_id)
        self._save()

    def mark_failed(self, item_id: str):
        """
        항목을 실패로 표시

        Args:
            item_id: 항목 식별자
        """
        if item_id not in self.failed:
            self.failed.append(item_id)
        self._save()

    def get_remaining(self, all_items: List[str]) -> List[str]:
        """
        완료되지 않은 항목 목록 반환

        Args:
            all_items: 전체 항목 목록

        Returns:
            완료되지 않은 항목 목록
        """
        return [item for item in all_items if item not in self.completed]

    def get_stats(self) -> dict:
        """
        진행률 통계 반환

        Returns:
            완료/실패 통계
        """
        return {
            'completed': len(self.completed),
            'failed': len(self.failed)
        }

    def reset(self):
        """진행률 초기화"""
        self.completed = set()
        self.failed = []
        self._save()
