"""
결과 통합 및 JSON 생성 모듈
- source_result.json: 모델별 원본 결과
- low_result.json: 단순 통합 (COCO 형식)
- topology_graph.json: 노드 기반 통합
"""

import json
import numpy as np
from itertools import combinations
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon, Point, MultiPolygon, GeometryCollection, LineString
from shapely.validation import make_valid
from shapely.ops import split

from .config import SPACE_SYNONYMS, SPACE_CLASSIFICATION, OUTSIDE_SPACES


class ResultAggregator:
    """추론 결과 통합 및 JSON 생성"""

    def __init__(self, config):
        self.config = config

    def _segmentation_to_polygon(self, segmentation: List) -> Optional[Polygon]:
        """segmentation 좌표를 shapely Polygon으로 변환"""
        if not segmentation or not segmentation[0]:
            return None

        coords = segmentation[0]
        if len(coords) < 6:  # 최소 3개 점 필요
            return None

        # [x1,y1,x2,y2,...] -> [(x1,y1),(x2,y2),...]
        vertices = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]

        try:
            polygon = Polygon(vertices)
            if not polygon.is_valid:
                polygon = make_valid(polygon)
            return polygon
        except Exception:
            return None

    def _get_polygon_centroid(self, segmentation: List, bbox: List) -> List[int]:
        """polygon centroid 계산 (실패시 bbox 중심점 반환)"""
        polygon = self._segmentation_to_polygon(segmentation)
        if polygon and not polygon.is_empty:
            centroid = polygon.centroid
            return [int(centroid.x), int(centroid.y)]
        # fallback to bbox centroid
        x, y, w, h = bbox
        return [int(x + w / 2), int(y + h / 2)]

    def _point_in_polygon(self, point: List[int], segmentation: List, bbox: List) -> bool:
        """점이 polygon 내부에 있는지 확인 (실패시 bbox로 판단)"""
        polygon = self._segmentation_to_polygon(segmentation)
        if polygon and not polygon.is_empty:
            return polygon.contains(Point(point[0], point[1]))
        # fallback to bbox check
        return self._point_in_bbox(point, bbox)

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (소문자, 공백 제거)"""
        return text.lower().replace(" ", "").replace("/", "")

    def _are_synonyms(self, text1: str, text2: str) -> bool:
        """두 텍스트가 동의어인지 확인"""
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)

        # 완전 일치
        if t1 == t2:
            return True

        # 동의어 사전에서 확인
        for group, synonyms in SPACE_SYNONYMS.items():
            normalized_synonyms = [self._normalize_text(s) for s in synonyms]
            # 두 텍스트가 같은 동의어 그룹에 속하는지 확인
            t1_in = any(t1 in s or s in t1 for s in normalized_synonyms)
            t2_in = any(t2 in s or s in t2 for s in normalized_synonyms)
            if t1_in and t2_in:
                return True

        return False

    def _get_space_type(self, label: str) -> str:
        """공간 라벨을 기반으로 공간 타입 분류 반환

        Args:
            label: 공간 라벨 (예: "거실", "침실", "주방" 등)

        Returns:
            공간 타입: "기타공간", "특화공간", "습식공간", "공통공간", "개인공간", "외부공간", "미분류"
        """
        normalized_label = self._normalize_text(label)

        # 외부 공간 체크
        for outside_space in OUTSIDE_SPACES:
            if self._normalize_text(outside_space) in normalized_label or normalized_label in self._normalize_text(outside_space):
                return "외부공간"

        # 동의어 사전에서 표준 공간명 찾기 (정확한 매칭 우선)
        standard_name = None

        # 1차: 정확한 매칭 시도
        for group, synonyms in SPACE_SYNONYMS.items():
            normalized_synonyms = [self._normalize_text(s) for s in synonyms]
            if normalized_label in normalized_synonyms:
                standard_name = group
                break

        # 2차: 정확한 매칭 실패 시 부분 매칭 시도
        if not standard_name:
            for group, synonyms in SPACE_SYNONYMS.items():
                normalized_synonyms = [self._normalize_text(s) for s in synonyms]
                if any(normalized_label in s or s in normalized_label for s in normalized_synonyms):
                    standard_name = group
                    break

        # 표준 공간명으로 공간 분류 체크
        search_label = standard_name if standard_name else label
        normalized_search = self._normalize_text(search_label)

        for space_type, space_list in SPACE_CLASSIFICATION.items():
            for space_name in space_list:
                normalized_space = self._normalize_text(space_name)
                if normalized_space in normalized_search or normalized_search in normalized_space:
                    return space_type

        return "미분류"

    def _is_outside_space(self, label: str) -> bool:
        """세대 외부 공간인지 확인"""
        normalized_label = self._normalize_text(label)
        for outside_space in OUTSIDE_SPACES:
            if self._normalize_text(outside_space) in normalized_label or normalized_label in self._normalize_text(outside_space):
                return True
        return False

    def _get_ocr_in_space_with_positions(self, space: Dict, ocr_results: List[Dict]) -> List[Dict]:
        """공간 내 OCR 텍스트와 위치 정보 반환"""
        results = []
        space_segmentation = space.get("segmentation", [])
        space_bbox = space["bbox"]

        for ocr in ocr_results:
            ocr_centroid = self._calculate_centroid(ocr["bbox"])
            if self._point_in_polygon(ocr_centroid, space_segmentation, space_bbox):
                text = ocr.get("attributes", {}).get("OCR", "")
                if text:
                    results.append({
                        "text": text,
                        "bbox": ocr["bbox"],
                        "centroid": ocr_centroid
                    })
        return results

    def _should_split_space(self, space: Dict, ocr_results: List[Dict]) -> Tuple[bool, List[Dict]]:
        """공간 분할 필요 여부 판단 - 동일/동의어 OCR이 2개 이상일 때"""
        ocr_in_space = self._get_ocr_in_space_with_positions(space, ocr_results)

        if len(ocr_in_space) < 2:
            return False, []

        # 동일/동의어 텍스트 그룹 찾기
        synonym_groups = []
        used = set()

        for i, ocr1 in enumerate(ocr_in_space):
            if i in used:
                continue
            group = [ocr1]
            used.add(i)

            for j, ocr2 in enumerate(ocr_in_space):
                if j in used:
                    continue
                if self._are_synonyms(ocr1["text"], ocr2["text"]):
                    group.append(ocr2)
                    used.add(j)

            if len(group) >= 2:
                synonym_groups.append(group)

        # 동의어 그룹이 있으면 분할 필요
        if synonym_groups:
            return True, synonym_groups[0]  # 첫 번째 그룹 반환

        return False, []

    def _find_splitting_wall(self, space: Dict, walls: List[Dict], ocr_positions: List[Dict]) -> Optional[Dict]:
        """공간을 분할할 수 있는 벽체 찾기"""
        space_polygon = self._segmentation_to_polygon(space.get("segmentation", []))
        if not space_polygon:
            return None

        # OCR 위치들 사이에 있는 벽체 찾기
        if len(ocr_positions) < 2:
            return None

        ocr1_centroid = ocr_positions[0]["centroid"]
        ocr2_centroid = ocr_positions[1]["centroid"]

        for wall in walls:
            if "벽체" not in wall.get("category_name", ""):
                continue

            wall_polygon = self._segmentation_to_polygon(wall.get("segmentation", []))
            if not wall_polygon:
                continue

            # 벽체가 공간과 교차하는지 확인
            if not space_polygon.intersects(wall_polygon):
                continue

            # 벽체가 두 OCR 사이에 있는지 확인 (벽체의 x 또는 y 좌표가 두 OCR 사이)
            wall_centroid = wall_polygon.centroid
            wx, wy = wall_centroid.x, wall_centroid.y

            # x축 기준 분할 체크
            if min(ocr1_centroid[0], ocr2_centroid[0]) < wx < max(ocr1_centroid[0], ocr2_centroid[0]):
                return wall

            # y축 기준 분할 체크
            if min(ocr1_centroid[1], ocr2_centroid[1]) < wy < max(ocr1_centroid[1], ocr2_centroid[1]):
                return wall

        return None

    def _split_space_by_line(self, space: Dict, split_line: LineString, space_id_prefix: str) -> List[Dict]:
        """분할선으로 공간을 분할하여 새로운 공간 리스트 반환"""
        space_polygon = self._segmentation_to_polygon(space.get("segmentation", []))

        if not space_polygon:
            print(f"[DEBUG] _split_space_by_line: No polygon for space {space_id_prefix}")
            return [space]

        try:
            # 분할선을 공간 경계를 넘어 확장
            extended_line = self._extend_line_through_polygon(split_line, space_polygon)
            print(f"[DEBUG] _split_space_by_line: split_line={list(split_line.coords)}")
            print(f"[DEBUG] _split_space_by_line: extended_line={list(extended_line.coords)}")

            # shapely split으로 공간 분할
            result = split(space_polygon, extended_line)
            print(f"[DEBUG] _split_space_by_line: result type={type(result).__name__}")

            if isinstance(result, GeometryCollection) and len(result.geoms) >= 2:
                print(f"[DEBUG] _split_space_by_line: {len(result.geoms)} geoms found")
                split_spaces = []
                for i, geom in enumerate(result.geoms):
                    print(f"[DEBUG]   geom[{i}]: type={type(geom).__name__}, area={geom.area if hasattr(geom, 'area') else 'N/A'}")
                    if not isinstance(geom, Polygon) or geom.area < 1000:
                        continue

                    new_space = space.copy()
                    coords = list(geom.exterior.coords)
                    flat_coords = []
                    for x, y in coords[:-1]:
                        flat_coords.extend([int(x), int(y)])

                    new_space["segmentation"] = [flat_coords]
                    bounds = geom.bounds
                    new_space["bbox"] = [
                        int(bounds[0]), int(bounds[1]),
                        int(bounds[2] - bounds[0]), int(bounds[3] - bounds[1])
                    ]
                    new_space["area"] = float(geom.area)
                    new_space["id"] = f"{space_id_prefix}_{i}"
                    split_spaces.append(new_space)

                print(f"[DEBUG] _split_space_by_line: {len(split_spaces)} valid spaces")
                if len(split_spaces) >= 2:
                    return split_spaces
            else:
                print(f"[DEBUG] _split_space_by_line: Not GeometryCollection or <2 geoms")
        except Exception as e:
            print(f"[DEBUG] _split_space_by_line: Exception: {e}")

        return [space]

    def _extend_line_through_polygon(self, line: LineString, polygon: Polygon) -> LineString:
        """분할선을 polygon 경계를 넘어 확장"""
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        coords = list(line.coords)

        if len(coords) < 2:
            return line

        p1, p2 = coords[0], coords[-1]

        # 방향 벡터 계산
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        # 대각선 길이만큼 확장
        diag = ((bounds[2] - bounds[0])**2 + (bounds[3] - bounds[1])**2)**0.5

        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return line

        length = (dx**2 + dy**2)**0.5
        scale = diag / length

        # 양 방향으로 확장
        new_p1 = (p1[0] - dx * scale, p1[1] - dy * scale)
        new_p2 = (p2[0] + dx * scale, p2[1] + dy * scale)

        return LineString([new_p1, new_p2])

    def _split_space_by_ocr_midpoint(self, space: Dict, ocr_positions: List[Dict]) -> List[Dict]:
        """두 OCR 위치의 중간점을 기준으로 공간 분할 (벽체 없을 때 fallback)"""
        if len(ocr_positions) < 2:
            return [space]

        space_polygon = self._segmentation_to_polygon(space.get("segmentation", []))
        if not space_polygon:
            return [space]

        # 두 OCR의 중심점
        ocr1_centroid = ocr_positions[0]["centroid"]
        ocr2_centroid = ocr_positions[1]["centroid"]

        # 중간점 계산
        mid_x = (ocr1_centroid[0] + ocr2_centroid[0]) / 2
        mid_y = (ocr1_centroid[1] + ocr2_centroid[1]) / 2

        # 두 OCR 사이의 방향 결정 (수평/수직)
        dx = abs(ocr2_centroid[0] - ocr1_centroid[0])
        dy = abs(ocr2_centroid[1] - ocr1_centroid[1])

        bounds = space_polygon.bounds

        if dx > dy:
            # 수평 방향으로 떨어져 있음 → 수직 분할선
            split_line = LineString([(mid_x, bounds[1] - 100), (mid_x, bounds[3] + 100)])
        else:
            # 수직 방향으로 떨어져 있음 → 수평 분할선
            split_line = LineString([(bounds[0] - 100, mid_y), (bounds[2] + 100, mid_y)])

        return self._split_space_by_line(space, split_line, space['id'])

    def _split_space_by_wall(self, space: Dict, wall: Dict) -> List[Dict]:
        """벽체로 공간을 분할하여 새로운 공간 리스트 반환"""
        space_polygon = self._segmentation_to_polygon(space.get("segmentation", []))
        wall_polygon = self._segmentation_to_polygon(wall.get("segmentation", []))

        if not space_polygon or not wall_polygon:
            return [space]

        try:
            # 벽체를 약간 확장하여 공간을 완전히 분할
            wall_buffered = wall_polygon.buffer(2)

            # 공간에서 벽체 영역 제거
            result = space_polygon.difference(wall_buffered)

            # 결과가 MultiPolygon이면 분할 성공
            if isinstance(result, MultiPolygon):
                split_spaces = []
                for i, geom in enumerate(result.geoms):
                    if geom.area < 1000:  # 너무 작은 조각은 무시
                        continue

                    # 새 공간 생성
                    new_space = space.copy()
                    coords = list(geom.exterior.coords)
                    flat_coords = []
                    for x, y in coords[:-1]:  # 마지막 점은 첫 점과 동일하므로 제외
                        flat_coords.extend([int(x), int(y)])

                    new_space["segmentation"] = [flat_coords]
                    bounds = geom.bounds
                    new_space["bbox"] = [
                        int(bounds[0]), int(bounds[1]),
                        int(bounds[2] - bounds[0]), int(bounds[3] - bounds[1])
                    ]
                    new_space["area"] = float(geom.area)
                    new_space["id"] = f"{space['id']}_{i}"
                    split_spaces.append(new_space)

                if len(split_spaces) >= 2:
                    return split_spaces

            # GeometryCollection 처리
            elif isinstance(result, GeometryCollection):
                split_spaces = []
                for i, geom in enumerate(result.geoms):
                    if not isinstance(geom, Polygon) or geom.area < 1000:
                        continue

                    new_space = space.copy()
                    coords = list(geom.exterior.coords)
                    flat_coords = []
                    for x, y in coords[:-1]:
                        flat_coords.extend([int(x), int(y)])

                    new_space["segmentation"] = [flat_coords]
                    bounds = geom.bounds
                    new_space["bbox"] = [
                        int(bounds[0]), int(bounds[1]),
                        int(bounds[2] - bounds[0]), int(bounds[3] - bounds[1])
                    ]
                    new_space["area"] = float(geom.area)
                    new_space["id"] = f"{space['id']}_{i}"
                    split_spaces.append(new_space)

                if len(split_spaces) >= 2:
                    return split_spaces

        except Exception:
            pass

        return [space]

    def _process_space_splitting(self, spa_results: List[Dict], str_results: List[Dict],
                                  ocr_results: List[Dict]) -> List[Dict]:
        """SPA 결과에서 분할이 필요한 공간을 처리"""
        processed_spaces = []
        walls = [s for s in str_results if "벽체" in s.get("category_name", "")]

        for space in spa_results:
            should_split, ocr_positions = self._should_split_space(space, ocr_results)

            if should_split and len(ocr_positions) >= 2:
                # 분할할 벽체 찾기
                splitting_wall = self._find_splitting_wall(space, walls, ocr_positions)

                if splitting_wall:
                    # 벽체로 공간 분할
                    split_spaces = self._split_space_by_wall(space, splitting_wall)
                    print(f"[DEBUG] Space {space['id']} split by WALL: {len(split_spaces)} parts")

                    # 벽체 분할 실패 시 (1개만 반환) OCR 중간점 fallback
                    if len(split_spaces) < 2:
                        print(f"[DEBUG] Space {space['id']} WALL split failed, trying OCR midpoint...")
                        split_spaces = self._split_space_by_ocr_midpoint(space, ocr_positions)
                        print(f"[DEBUG]   OCR midpoint result: {len(split_spaces)} parts")

                    processed_spaces.extend(split_spaces)
                else:
                    # 벽체 없으면 OCR 중간점 기준으로 분할 (fallback)
                    print(f"[DEBUG] Space {space['id']} no wall found, trying OCR midpoint...")
                    print(f"[DEBUG]   OCR positions: {[(o['text'], o['centroid']) for o in ocr_positions]}")
                    split_spaces = self._split_space_by_ocr_midpoint(space, ocr_positions)
                    print(f"[DEBUG]   Result: {len(split_spaces)} parts")
                    processed_spaces.extend(split_spaces)
            else:
                processed_spaces.append(space)

        return processed_spaces

    def aggregate(
        self,
        image_info: Dict,
        obj_results: List[Dict],
        ocr_results: List[Dict],
        str_results: List[Dict],
        spa_results: List[Dict],
        inference_times: Dict[str, float]
    ) -> Dict[str, Dict]:
        """모든 결과를 세 가지 JSON 형식으로 통합"""

        # source_result 생성
        source_result = self._create_source_result(
            image_info, obj_results, ocr_results,
            str_results, spa_results, inference_times
        )

        # low_result 생성
        low_result = self._create_low_result(
            image_info, obj_results, ocr_results,
            str_results, spa_results
        )

        # topology_graph 생성
        topology_graph = self._create_topology_graph(
            image_info, obj_results, ocr_results,
            str_results, spa_results
        )

        return {
            "source_result": source_result,
            "low_result": low_result,
            "topology_graph": topology_graph
        }

    def _create_source_result(
        self,
        image_info: Dict,
        obj_results: List[Dict],
        ocr_results: List[Dict],
        str_results: List[Dict],
        spa_results: List[Dict],
        inference_times: Dict[str, float]
    ) -> Dict:
        """모델별 원본 결과 생성"""
        return {
            "image_info": {
                "file_name": image_info["file_name"],
                "width": image_info["width"],
                "height": image_info["height"],
                "inference_time": datetime.now().isoformat()
            },
            "models": {
                "OBJ": {
                    "model_name": str(self.config.OBJ_CONFIG.model_path.name),
                    "inference_time_ms": inference_times.get("OBJ", 0),
                    "count": len(obj_results),
                    "annotations": obj_results
                },
                "OCR": {
                    "model_name": "YOLOV5 + CRNN",
                    "inference_time_ms": inference_times.get("OCR", 0),
                    "count": len(ocr_results),
                    "annotations": ocr_results
                },
                "STR": {
                    "model_name": str(self.config.STR_CONFIG.model_path.name),
                    "inference_time_ms": inference_times.get("STR", 0),
                    "count": len(str_results),
                    "annotations": str_results
                },
                "SPA": {
                    "model_name": str(self.config.SPA_CONFIG.model_path.name),
                    "inference_time_ms": inference_times.get("SPA", 0),
                    "count": len(spa_results),
                    "annotations": spa_results
                }
            }
        }

    def _create_low_result(
        self,
        image_info: Dict,
        obj_results: List[Dict],
        ocr_results: List[Dict],
        str_results: List[Dict],
        spa_results: List[Dict]
    ) -> Dict:
        """단순 통합 결과 생성 (COCO 형식)"""
        # 카테고리 리스트 생성
        categories = [
            {"id": cat_id, "name": cat_name}
            for cat_id, cat_name in self.config.CATEGORIES.items()
        ]

        # 모든 annotation 통합
        all_annotations = []
        annotation_id = 0

        for model_name, results in [
            ("OBJ", obj_results),
            ("OCR", ocr_results),
            ("STR", str_results),
            ("SPA", spa_results)
        ]:
            for ann in results:
                ann_copy = ann.copy()
                ann_copy["id"] = annotation_id
                ann_copy["image_id"] = 1
                ann_copy["source_model"] = model_name
                all_annotations.append(ann_copy)
                annotation_id += 1

        return {
            "categories": categories,
            "images": [
                {
                    "id": 1,
                    "width": image_info["width"],
                    "height": image_info["height"],
                    "file_name": image_info["file_name"]
                }
            ],
            "annotations": all_annotations
        }

    def _create_topology_graph(
        self,
        image_info: Dict,
        obj_results: List[Dict],
        ocr_results: List[Dict],
        str_results: List[Dict],
        spa_results: List[Dict]
    ) -> Dict:
        """노드별 통합 (공간 중심) 그래프 생성"""
        nodes = []
        edges = []

        # 공간 분할 처리 (동일 OCR이 2개 이상인 경우)
        processed_spa_results = self._process_space_splitting(
            spa_results, str_results, ocr_results
        )

        # 세대 내부 공간 면적 합계 계산 (area_ratio 기준)
        total_inside_area = 0
        for space in processed_spa_results:
            # 라벨 추출 (OCR 결과 활용)
            temp_ocr = self._find_ocr_in_space(space, ocr_results)
            temp_label = self._extract_label(space, temp_ocr)
            if not self._is_outside_space(temp_label):
                total_inside_area += space["area"]

        # 공간(SPA) 결과를 노드로 변환
        for idx, space in enumerate(processed_spa_results):
            # 공간 내 포함된 요소 찾기
            contained_objects = self._find_objects_in_space(space, obj_results)
            contained_ocr = self._find_ocr_in_space(space, ocr_results)
            contained_structures = self._find_structures_in_space(space, str_results)

            # 라벨 추출 (OCR 결과 또는 카테고리명)
            label = self._extract_label(space, contained_ocr)

            # 중심점 계산 (polygon centroid 사용)
            centroid = self._get_polygon_centroid(
                space.get("segmentation", []),
                space["bbox"]
            )

            # 공간 타입 분류
            space_type = self._get_space_type(label)

            # 외부 공간 여부 확인
            is_outside = self._is_outside_space(label)

            # area_ratio 계산 (내부 공간만, 외부 공간은 null)
            if is_outside:
                area_ratio = None
            else:
                area_ratio = round(space["area"] / total_inside_area, 4) if total_inside_area > 0 else 0

            node = {
                "node_id": f"space_{idx}",
                "node_type": "space",
                "category_id": space["category_id"],
                "category_name": space["category_name"],
                "label": label,
                "space_type": space_type,
                "is_outside": is_outside,
                "bbox": space["bbox"],
                "segmentation": space.get("segmentation", []),
                "area": space["area"],
                "area_ratio": area_ratio,
                "centroid": centroid,
                "contains": {
                    "objects": contained_objects,
                    "ocr_labels": contained_ocr,
                    "structures": contained_structures
                }
            }
            nodes.append(node)

        # 공간 간 연결 관계 분석 (문을 통한 연결)
        edges = self._analyze_connections(nodes, str_results)

        # 통계 계산
        statistics = self._calculate_statistics(nodes, spa_results, image_info)

        return {
            "image_info": {
                "file_name": image_info["file_name"],
                "width": image_info["width"],
                "height": image_info["height"]
            },
            "nodes": nodes,
            "edges": edges,
            "statistics": statistics
        }

    def _extract_label(self, space: Dict, ocr_labels: List[str]) -> str:
        """공간 라벨 추출"""
        if ocr_labels:
            return ocr_labels[0]  # 첫 번째 OCR 결과 사용
        # 카테고리명에서 추출
        return space["category_name"].replace("공간_", "")

    def _calculate_centroid(self, bbox: List) -> List[int]:
        """bbox 중심점 계산"""
        x, y, w, h = bbox
        return [int(x + w / 2), int(y + h / 2)]

    def _point_in_bbox(self, point: List[int], bbox: List) -> bool:
        """점이 bbox 내부에 있는지 확인"""
        px, py = point
        x, y, w, h = bbox
        return x <= px <= x + w and y <= py <= y + h

    def _bbox_intersects(self, bbox1: List, bbox2: List) -> bool:
        """두 bbox가 교차하는지 확인"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        return not (
            x1 + w1 < x2 or
            x2 + w2 < x1 or
            y1 + h1 < y2 or
            y2 + h2 < y1
        )

    def _find_objects_in_space(self, space: Dict, objects: List[Dict]) -> List[Dict]:
        """공간 내 객체 검색 (polygon 기반)"""
        contained = []
        space_segmentation = space.get("segmentation", [])
        space_bbox = space["bbox"]

        for obj in objects:
            obj_centroid = self._calculate_centroid(obj["bbox"])
            if self._point_in_polygon(obj_centroid, space_segmentation, space_bbox):
                contained.append({
                    "object_id": f"obj_{obj['id']}",
                    "category_id": obj["category_id"],
                    "category_name": obj["category_name"],
                    "bbox": obj["bbox"]
                })

        return contained

    def _find_ocr_in_space(self, space: Dict, ocr_results: List[Dict]) -> List[str]:
        """공간 내 OCR 텍스트 검색 (polygon 기반)"""
        labels = []
        space_segmentation = space.get("segmentation", [])
        space_bbox = space["bbox"]

        for ocr in ocr_results:
            ocr_centroid = self._calculate_centroid(ocr["bbox"])
            if self._point_in_polygon(ocr_centroid, space_segmentation, space_bbox):
                text = ocr.get("attributes", {}).get("OCR", "")
                if text:
                    labels.append(text)

        return labels

    def _polygon_intersects(self, segmentation1: List, bbox1: List,
                              segmentation2: List, bbox2: List) -> bool:
        """두 polygon이 교차하는지 확인 (실패시 bbox로 판단)"""
        poly1 = self._segmentation_to_polygon(segmentation1)
        poly2 = self._segmentation_to_polygon(segmentation2)

        if poly1 and poly2 and not poly1.is_empty and not poly2.is_empty:
            return poly1.intersects(poly2)
        # fallback to bbox intersection
        return self._bbox_intersects(bbox1, bbox2)

    def _find_structures_in_space(self, space: Dict, structures: List[Dict]) -> Dict:
        """공간 경계의 구조물 검색 (polygon 기반)"""
        result = {"doors": [], "windows": [], "walls": []}
        space_segmentation = space.get("segmentation", [])
        space_bbox = space["bbox"]

        for struct in structures:
            struct_segmentation = struct.get("segmentation", [])
            struct_bbox = struct["bbox"]

            # 공간 경계와 교차하는 구조물 검색 (polygon 기반)
            if self._polygon_intersects(space_segmentation, space_bbox,
                                        struct_segmentation, struct_bbox):
                cat_name = struct["category_name"]

                if "출입문" in cat_name:
                    result["doors"].append({
                        "structure_id": f"str_{struct['id']}",
                        "type": struct.get("attributes", {}).get("subcat", "기타문"),
                        "bbox": struct["bbox"]
                    })
                elif "창호" in cat_name:
                    result["windows"].append({
                        "structure_id": f"str_{struct['id']}",
                        "type": struct.get("attributes", {}).get("subcat", "기타창"),
                        "bbox": struct["bbox"]
                    })

        return result

    def _split_structure_by_spaces(self, structure: Dict, connected_nodes: List[Dict],
                                      walls: List[Dict]) -> List[Tuple[Polygon, List[str]]]:
        """
        구조물(문/창문)을 공간 경계 기준으로 분할하여 각 조각과 연결된 공간 목록 반환.
        Returns: [(분할된_polygon, [연결된_space_id들]), ...]
        """
        struct_polygon = self._segmentation_to_polygon(structure.get("segmentation", []))
        if not struct_polygon:
            return []

        # 벽체들의 union 생성
        wall_union = None
        for wall in walls:
            wall_poly = self._segmentation_to_polygon(wall.get("segmentation", []))
            if wall_poly:
                if wall_union is None:
                    wall_union = wall_poly.buffer(1)
                else:
                    wall_union = wall_union.union(wall_poly.buffer(1))

        # 구조물을 벽체로 분할 시도
        split_parts = [struct_polygon]
        if wall_union:
            try:
                result = struct_polygon.difference(wall_union)
                if isinstance(result, MultiPolygon):
                    split_parts = [g for g in result.geoms if g.area > 10]
                elif isinstance(result, GeometryCollection):
                    split_parts = [g for g in result.geoms if isinstance(g, Polygon) and g.area > 10]
                elif isinstance(result, Polygon) and result.area > 10:
                    split_parts = [result]
            except Exception:
                pass

        # 각 분할된 조각이 어떤 공간들과 교차하는지 확인
        result_parts = []
        for part in split_parts:
            connected_space_ids = []
            for node in connected_nodes:
                node_poly = self._segmentation_to_polygon(node.get("segmentation", []))
                if node_poly and part.intersects(node_poly):
                    connected_space_ids.append(node["node_id"])
            if connected_space_ids:
                result_parts.append((part, connected_space_ids))

        return result_parts

    def _is_bedroom(self, node: Dict) -> bool:
        """노드가 침실인지 확인 (동의어 포함)"""
        label = node.get("label", "")
        category_name = node.get("category_name", "")

        # category_name이 침실인 경우
        if category_name == "공간_침실":
            return True

        # label이 침실 동의어인 경우
        normalized_label = self._normalize_text(label)
        bedroom_synonyms = SPACE_SYNONYMS.get("침실", [])
        for synonym in bedroom_synonyms:
            if self._normalize_text(synonym) in normalized_label or normalized_label in self._normalize_text(synonym):
                return True

        return False

    def _analyze_connections(self, nodes: List[Dict], structures: List[Dict]) -> List[Dict]:
        """공간 간 연결 관계 분석 (polygon 기반) - 문, 창문, 열린 공간 연결"""
        edges = []
        edge_pairs = set()  # (source, target) 쌍 중복 방지

        # node_id로 node를 빠르게 찾기 위한 딕셔너리
        node_map = {node["node_id"]: node for node in nodes}
        wall_structures = [s for s in structures if "벽체" in s.get("category_name", "")]

        # 1. 출입문(door) 연결
        door_structures = [s for s in structures if "출입문" in s.get("category_name", "")]
        for door in door_structures:
            door_segmentation = door.get("segmentation", [])
            door_bbox = door["bbox"]
            connected_spaces = []
            connected_nodes_list = []

            for node in nodes:
                node_segmentation = node.get("segmentation", [])
                node_bbox = node["bbox"]

                if self._polygon_intersects(node_segmentation, node_bbox,
                                           door_segmentation, door_bbox):
                    connected_spaces.append(node["node_id"])
                    connected_nodes_list.append(node)

            # 3개 이상의 공간과 교차하면 문을 분할하여 처리
            if len(connected_spaces) >= 3:
                split_parts = self._split_structure_by_spaces(door, connected_nodes_list, wall_structures)

                edges_created = False
                for part_poly, part_spaces in split_parts:
                    # 분할된 조각이 정확히 2개 공간과 연결될 때만 edge 생성
                    if len(part_spaces) == 2:
                        space_a, space_b = part_spaces
                        pair = tuple(sorted([space_a, space_b]))
                        if pair not in edge_pairs:
                            # 두 공간이 인접한지 확인
                            node_a = node_map.get(space_a)
                            node_b = node_map.get(space_b)
                            if node_a and node_b:
                                # 3개+ 공간 교차 시 침실-침실 연결 제외
                                if self._is_bedroom(node_a) and self._is_bedroom(node_b):
                                    continue

                                poly_a = self._segmentation_to_polygon(node_a.get("segmentation", []))
                                poly_b = self._segmentation_to_polygon(node_b.get("segmentation", []))
                                if poly_a and poly_b:
                                    if poly_a.touches(poly_b) or poly_a.buffer(5).intersects(poly_b.buffer(5)):
                                        edge_pairs.add(pair)
                                        edges.append({
                                            "edge_id": f"edge_{len(edges)}",
                                            "source_node": space_a,
                                            "target_node": space_b,
                                            "connection_type": "door",
                                            "connection_id": f"str_{door['id']}"
                                        })
                                        edges_created = True

                # 분할 실패 시 fallback: 인접한 공간 쌍만 연결
                if not edges_created:
                    for space_a, space_b in combinations(connected_spaces, 2):
                        pair = tuple(sorted([space_a, space_b]))
                        if pair in edge_pairs:
                            continue

                        node_a = node_map.get(space_a)
                        node_b = node_map.get(space_b)
                        if not node_a or not node_b:
                            continue

                        # 3개+ 공간 교차 시 침실-침실 연결 제외
                        if self._is_bedroom(node_a) and self._is_bedroom(node_b):
                            continue

                        poly_a = self._segmentation_to_polygon(node_a.get("segmentation", []))
                        poly_b = self._segmentation_to_polygon(node_b.get("segmentation", []))
                        if not poly_a or not poly_b:
                            continue

                        # 두 공간이 인접하는지만 확인
                        if poly_a.touches(poly_b) or poly_a.buffer(5).intersects(poly_b.buffer(5)):
                            edge_pairs.add(pair)
                            edges.append({
                                "edge_id": f"edge_{len(edges)}",
                                "source_node": space_a,
                                "target_node": space_b,
                                "connection_type": "door",
                                "connection_id": f"str_{door['id']}"
                            })
            # 정확히 2개 공간과 교차하면 인접성 검사 없이 edge 생성
            elif len(connected_spaces) == 2:
                space_a, space_b = connected_spaces
                pair = tuple(sorted([space_a, space_b]))
                if pair not in edge_pairs:
                    edge_pairs.add(pair)
                    edges.append({
                        "edge_id": f"edge_{len(edges)}",
                        "source_node": space_a,
                        "target_node": space_b,
                        "connection_type": "door",
                        "connection_id": f"str_{door['id']}"
                    })
            # 3개 이상과 교차하지만 분할 실패한 경우 (fallback에서 처리됨)
            # 여기서는 추가 처리 없음

        # 2. 창호(window) 연결
        window_structures = [s for s in structures if "창호" in s.get("category_name", "")]
        for window in window_structures:
            window_segmentation = window.get("segmentation", [])
            window_bbox = window["bbox"]
            connected_spaces = []
            connected_nodes_list = []

            for node in nodes:
                node_segmentation = node.get("segmentation", [])
                node_bbox = node["bbox"]

                if self._polygon_intersects(node_segmentation, node_bbox,
                                           window_segmentation, window_bbox):
                    connected_spaces.append(node["node_id"])
                    connected_nodes_list.append(node)

            # 3개 이상의 공간과 교차하면 창문을 분할하여 처리
            if len(connected_spaces) >= 3:
                split_parts = self._split_structure_by_spaces(window, connected_nodes_list, wall_structures)

                edges_created = False
                for part_poly, part_spaces in split_parts:
                    if len(part_spaces) == 2:
                        space_a, space_b = part_spaces
                        pair = tuple(sorted([space_a, space_b]))
                        if pair not in edge_pairs:
                            node_a = node_map.get(space_a)
                            node_b = node_map.get(space_b)
                            if node_a and node_b:
                                poly_a = self._segmentation_to_polygon(node_a.get("segmentation", []))
                                poly_b = self._segmentation_to_polygon(node_b.get("segmentation", []))
                                if poly_a and poly_b:
                                    if poly_a.touches(poly_b) or poly_a.buffer(5).intersects(poly_b.buffer(5)):
                                        edge_pairs.add(pair)
                                        edges.append({
                                            "edge_id": f"edge_{len(edges)}",
                                            "source_node": space_a,
                                            "target_node": space_b,
                                            "connection_type": "window",
                                            "connection_id": f"str_{window['id']}"
                                        })
                                        edges_created = True

                # 분할 실패 시 fallback: 인접한 공간 쌍만 연결 (기존 로직과 동일)
                if not edges_created:
                    for space_a, space_b in combinations(connected_spaces, 2):
                        pair = tuple(sorted([space_a, space_b]))
                        if pair in edge_pairs:
                            continue

                        node_a = node_map.get(space_a)
                        node_b = node_map.get(space_b)
                        if not node_a or not node_b:
                            continue

                        poly_a = self._segmentation_to_polygon(node_a.get("segmentation", []))
                        poly_b = self._segmentation_to_polygon(node_b.get("segmentation", []))
                        if not poly_a or not poly_b:
                            continue

                        # 두 공간이 인접하는지만 확인 (기존 로직과 동일)
                        if poly_a.touches(poly_b) or poly_a.buffer(5).intersects(poly_b.buffer(5)):
                            edge_pairs.add(pair)
                            edges.append({
                                "edge_id": f"edge_{len(edges)}",
                                "source_node": space_a,
                                "target_node": space_b,
                                "connection_type": "window",
                                "connection_id": f"str_{window['id']}"
                            })
            # 정확히 2개 공간과 교차하면 인접성 검사 없이 edge 생성
            elif len(connected_spaces) == 2:
                space_a, space_b = connected_spaces
                pair = tuple(sorted([space_a, space_b]))
                if pair not in edge_pairs:
                    edge_pairs.add(pair)
                    edges.append({
                        "edge_id": f"edge_{len(edges)}",
                        "source_node": space_a,
                        "target_node": space_b,
                        "connection_type": "window",
                        "connection_id": f"str_{window['id']}"
                    })

        # 3. 열린 공간(open) 연결 - 벽/문/창문 없이 직접 인접한 공간
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes):
                if i >= j:
                    continue

                pair = tuple(sorted([node1["node_id"], node2["node_id"]]))
                if pair in edge_pairs:
                    continue  # 이미 door/window로 연결된 경우 스킵

                # 두 공간의 polygon이 직접 인접하는지 확인 (경계가 접촉)
                poly1 = self._segmentation_to_polygon(node1.get("segmentation", []))
                poly2 = self._segmentation_to_polygon(node2.get("segmentation", []))

                if not poly1 or not poly2:
                    continue

                # touches() - 경계가 접촉하지만 내부가 겹치지 않음
                # intersects() with small buffer - 아주 가까이 인접한 경우
                if poly1.touches(poly2) or poly1.buffer(5).intersects(poly2.buffer(5)):
                    # 중간에 벽이 있는지 확인
                    has_wall_between = False
                    for wall in wall_structures:
                        wall_poly = self._segmentation_to_polygon(wall.get("segmentation", []))
                        if not wall_poly:
                            continue

                        # 두 공간의 중심을 연결하는 선이 벽과 교차하는지 확인
                        line = LineString([poly1.centroid, poly2.centroid])
                        if wall_poly.intersects(line):
                            has_wall_between = True
                            break

                    if not has_wall_between:
                        edge_pairs.add(pair)
                        edges.append({
                            "edge_id": f"edge_{len(edges)}",
                            "source_node": node1["node_id"],
                            "target_node": node2["node_id"],
                            "connection_type": "open",
                            "connection_id": None
                        })

        return edges

    def _calculate_statistics(
        self,
        nodes: List[Dict],
        spa_results: List[Dict],
        image_info: Dict
    ) -> Dict:
        """통계 정보 계산"""
        total_space_area = sum(n["area"] for n in nodes)
        total_inside_area = sum(n["area"] for n in nodes if not n.get("is_outside", False))

        # 공간 카테고리별 카운트
        room_categories = ["공간_침실"]
        bathroom_categories = ["공간_화장실"]
        balcony_categories = ["공간_발코니"]

        room_count = sum(1 for n in nodes if n["category_name"] in room_categories)
        bathroom_count = sum(1 for n in nodes if n["category_name"] in bathroom_categories)
        balcony_count = sum(1 for n in nodes if n["category_name"] in balcony_categories)

        # 공간 타입별 카운트 (SPACE_CLASSIFICATION 기준)
        space_type_count = {
            "기타공간": 0,
            "특화공간": 0,
            "습식공간": 0,
            "공통공간": 0,
            "개인공간": 0,
            "외부공간": 0,
            "미분류": 0
        }
        for node in nodes:
            space_type = node.get("space_type", "미분류")
            if space_type in space_type_count:
                space_type_count[space_type] += 1
            else:
                space_type_count["미분류"] += 1

        # 외부 공간 제외한 내부 공간 수
        inside_space_count = len([n for n in nodes if not n.get("is_outside", False)])

        # 발코니 면적 비율 계산
        balcony_area = sum(n["area"] for n in nodes if n["category_name"] in balcony_categories)
        balcony_ratio = (balcony_area / total_inside_area * 100) if total_inside_area > 0 else 0.0

        # 창 없는 공간 비율 계산 (내부 공간 기준, "기타" 라벨 제외)
        inside_nodes = [n for n in nodes if not n.get("is_outside", False)]
        # "기타" 라벨 제외한 공간만 계산
        valid_nodes = [n for n in inside_nodes if n.get("label", "") != "기타"]
        windowless_count = sum(
            1 for n in valid_nodes
            if not n.get("contains", {}).get("structures", {}).get("windows", [])
        )
        valid_space_count = len(valid_nodes)
        windowless_ratio = (windowless_count / valid_space_count * 100) if valid_space_count > 0 else 0.0

        return {
            "total_image_area": image_info["width"] * image_info["height"],
            "total_space_area": total_space_area,
            "total_inside_area": total_inside_area,
            "space_count": len(nodes),
            "inside_space_count": inside_space_count,
            "room_count": room_count,
            "bathroom_count": bathroom_count,
            "balcony_count": balcony_count,
            "bay_count": self._calculate_bay_count(nodes),
            "space_type_count": space_type_count,
            "structure_type": self._detect_structure_type(nodes),
            "balcony_ratio": round(balcony_ratio, 4),
            "windowless_ratio": round(windowless_ratio, 4)
        }

    def _detect_structure_type(self, nodes: List[Dict]) -> str:
        """구조 유형 판단 (맞통풍 기준)

        판상형: 맞통풍 가능 (거실↔주방 창문 180° 반대)
        타워형: 맞통풍 불가 + (이면개방 OR 주방 창문 없음 OR 같은 방향)
        혼합형: 맞통풍 불가 + 90° 직각 (Edge Case)

        Args:
            nodes: 공간 노드 리스트

        Returns:
            "판상형", "타워형", "혼합형" 중 하나
        """
        # 1. 거실 찾기
        living_rooms = [n for n in nodes if n["category_name"] == "공간_거실"]
        if not living_rooms:
            return "혼합형"  # 거실 없음 → 판단 불가

        living_room = living_rooms[0]

        # 2. 거실 이면개방 체크 (창문이 직각 방향에 2개 이상)
        living_directions = self._get_all_window_directions(living_room)
        if self._has_perpendicular_windows(living_directions):
            return "타워형"  # 이면개방 → 타워형

        # 3. 거실 주요 창문 방향
        living_direction = self._get_space_window_direction(living_room)
        if not living_direction:
            return "혼합형"  # 거실 창문 없음 → 판단 불가

        # 4. 주방 찾기 (주방및식당 우선)
        kitchens = [n for n in nodes if n["category_name"] in ["공간_주방및식당", "공간_주방"]]
        if not kitchens:
            return "혼합형"  # 주방 없음 → 판단 불가

        kitchen = kitchens[0]
        kitchen_direction = self._get_space_window_direction(kitchen)

        # 5. 맞통풍 판정
        if not kitchen_direction:
            return "타워형"  # 주방 창문 없음 → 맞통풍 불가

        if self._is_opposite_direction(living_direction, kitchen_direction):
            return "판상형"  # 180° 반대 → 맞통풍 가능

        if self._is_perpendicular_direction(living_direction, kitchen_direction):
            return "혼합형"  # 90° 직각 → Edge Case

        if living_direction == kitchen_direction:
            return "타워형"  # 같은 방향 → 맞통풍 불가

        return "혼합형"  # 기타 케이스

    def _get_window_direction(self, window: Dict, space: Dict) -> str:
        """창문이 공간에서 어느 방향(외부)을 바라보는지 계산

        Args:
            window: 창문 정보 (bbox 포함)
            space: 공간 노드 정보 (centroid, bbox 포함)

        Returns:
            방향 문자열: "north", "south", "east", "west"
        """
        window_bbox = window["bbox"]
        wx, wy, ww, wh = window_bbox
        window_cx = wx + ww / 2
        window_cy = wy + wh / 2

        space_centroid = space["centroid"]
        space_cx, space_cy = space_centroid

        # 창문과 공간 중심점 사이의 방향 벡터
        dx = window_cx - space_cx
        dy = window_cy - space_cy

        # 창문이 가로로 긴지 세로로 긴지 확인
        is_horizontal = ww > wh

        if is_horizontal:
            # 가로 창문: 남쪽 또는 북쪽
            if dy > 0:
                return "south"  # 창문이 공간 중심보다 아래에 있음 → 남향
            else:
                return "north"  # 창문이 공간 중심보다 위에 있음 → 북향
        else:
            # 세로 창문: 동쪽 또는 서쪽
            if dx > 0:
                return "east"   # 창문이 공간 중심보다 오른쪽에 있음 → 동향
            else:
                return "west"   # 창문이 공간 중심보다 왼쪽에 있음 → 서향

    def _is_opposite_direction(self, dir1: str, dir2: str) -> bool:
        """두 방향이 180° 반대인지 확인 (맞통풍 가능)

        Args:
            dir1: 첫 번째 방향 ("north"/"south"/"east"/"west")
            dir2: 두 번째 방향

        Returns:
            180° 반대이면 True
        """
        opposite_map = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east"
        }
        return opposite_map.get(dir1) == dir2

    def _is_perpendicular_direction(self, dir1: str, dir2: str) -> bool:
        """두 방향이 90° 직각인지 확인

        Args:
            dir1: 첫 번째 방향
            dir2: 두 번째 방향

        Returns:
            90° 직각이면 True
        """
        horizontal = {"east", "west"}
        vertical = {"north", "south"}
        return (dir1 in horizontal and dir2 in vertical) or \
               (dir1 in vertical and dir2 in horizontal)

    def _get_space_window_direction(self, space: Dict) -> Optional[str]:
        """공간의 주요 창문 방향 반환

        Args:
            space: 공간 노드 (contains.windows 포함)

        Returns:
            방향 문자열 ("north"/"south"/"east"/"west") 또는 None (창문 없음)
        """
        windows = space.get("contains", {}).get("structures", {}).get("windows", [])
        if not windows:
            return None

        # 가장 큰 창문 선택 (너비 또는 높이 중 큰 값 기준)
        main_window = max(windows, key=lambda w: max(w["bbox"][2], w["bbox"][3]))
        return self._get_window_direction(main_window, space)

    def _get_all_window_directions(self, space: Dict) -> List[str]:
        """공간의 모든 창문 방향 반환 (이면개방 판별용)

        Args:
            space: 공간 노드

        Returns:
            모든 창문의 방향 리스트
        """
        windows = space.get("contains", {}).get("structures", {}).get("windows", [])
        if not windows:
            return []

        directions = []
        for window in windows:
            direction = self._get_window_direction(window, space)
            directions.append(direction)
        return directions

    def _has_perpendicular_windows(self, directions: List[str]) -> bool:
        """창문들이 직각 방향에 있는지 확인 (이면개방)

        Args:
            directions: 창문 방향 리스트

        Returns:
            직각 방향 창문이 있으면 True (이면개방)
        """
        if len(directions) < 2:
            return False

        unique_directions = set(directions)
        horizontal = {"east", "west"}
        vertical = {"north", "south"}

        has_horizontal = bool(unique_directions & horizontal)
        has_vertical = bool(unique_directions & vertical)

        return has_horizontal and has_vertical

    def _calculate_bay_count(self, nodes: List[Dict]) -> int:
        """Bay 수 계산

        Bay 수 = 거실 창문과 같은 방향을 바라보는 침실 수 + 거실 수

        1. 거실의 창문 중 가장 긴 너비의 창문 방향을 "남쪽"으로 정의
        2. 침실 중 같은 방향의 창문을 가진 침실 수를 셈
        """
        # 거실 찾기
        living_rooms = [n for n in nodes if n["category_name"] == "공간_거실"]
        if not living_rooms:
            return 0

        # 침실 찾기
        bedrooms = [n for n in nodes if n["category_name"] == "공간_침실"]

        # 거실이 1개인 경우만 처리 (여러 개인 경우 추후 확장)
        if len(living_rooms) != 1:
            # 거실이 여러 개인 경우 단순히 거실 수 반환
            return len(living_rooms)

        living_room = living_rooms[0]
        living_windows = living_room.get("contains", {}).get("structures", {}).get("windows", [])

        if not living_windows:
            # 거실에 창문이 없으면 거실 수만 반환
            return len(living_rooms)

        # 거실 창문 중 가장 긴 너비의 창문 찾기
        if len(living_windows) == 1:
            main_window = living_windows[0]
        else:
            # 가장 긴 너비의 창문 선택
            main_window = max(living_windows, key=lambda w: w["bbox"][2])  # bbox[2] = width

        # 거실의 기준 방향 결정
        south_direction = self._get_window_direction(main_window, living_room)

        # 같은 방향의 창문을 가진 침실 수 계산
        matching_bedrooms = 0
        for bedroom in bedrooms:
            bedroom_windows = bedroom.get("contains", {}).get("structures", {}).get("windows", [])
            if not bedroom_windows:
                continue

            # 침실의 가장 긴 창문 방향 확인
            if len(bedroom_windows) == 1:
                bedroom_main_window = bedroom_windows[0]
            else:
                bedroom_main_window = max(bedroom_windows, key=lambda w: w["bbox"][2])

            bedroom_direction = self._get_window_direction(bedroom_main_window, bedroom)

            if bedroom_direction == south_direction:
                matching_bedrooms += 1

        # Bay 수 = 같은 방향 침실 수 + 거실 수
        return matching_bedrooms + len(living_rooms)

    def save_results(
        self,
        results: Dict[str, Dict],
        output_path: Path,
        file_stem: str
    ) -> Dict[str, Path]:
        """결과를 파일로 저장 (이미지별 폴더 구조)"""
        saved_paths = {}

        # 이미지별 출력 폴더 생성
        image_output_dir = output_path / file_stem
        image_output_dir.mkdir(parents=True, exist_ok=True)

        for result_type, data in results.items():
            file_path = image_output_dir / f"{result_type}.json"

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            saved_paths[result_type] = file_path

        return saved_paths
