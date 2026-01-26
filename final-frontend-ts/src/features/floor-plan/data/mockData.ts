// ============================================
// FloorPlan Feature - Mock Data
// ============================================

import type { FloorPlanUploadResponse, RoomInfo, StructureInfo, ObjectInfo } from '../types';

// Mock 방 데이터 (DB 구조 기반 - bbox는 JSON 문자열)
const mockRooms: RoomInfo[] = [
  { id: 1, spcname: "거실", ocrname: "Living Room", bbox: "[100, 100, 400, 300]", centroid: "250,200", area: 28.5, areapercent: 40 },
  { id: 2, spcname: "주방", ocrname: "Kitchen", bbox: "[400, 100, 550, 250]", centroid: "475,175", area: 12.3, areapercent: 17 },
  { id: 3, spcname: "침실1", ocrname: "Bedroom1", bbox: "[100, 300, 280, 480]", centroid: "190,390", area: 14.2, areapercent: 20 },
  { id: 4, spcname: "침실2", ocrname: "Bedroom2", bbox: "[280, 300, 450, 450]", centroid: "365,375", area: 11.8, areapercent: 17 },
  { id: 5, spcname: "화장실", ocrname: "Bathroom", bbox: "[450, 300, 550, 420]", centroid: "500,360", area: 4.5, areapercent: 6 },
];

// Mock 구조물 데이터 (문, 창문 등 - bbox는 JSON 문자열)
const mockStructures: StructureInfo[] = [
  { id: 101, name: "현관문", bbox: "[100, 180, 130, 220]", centroid: "115,200", area: "0.5" },
  { id: 102, name: "방문1", bbox: "[270, 290, 290, 340]", centroid: "280,315", area: "0.3" },
  { id: 103, name: "방문2", bbox: "[440, 340, 460, 390]", centroid: "450,365", area: "0.3" },
  { id: 104, name: "창문1", bbox: "[200, 100, 300, 110]", centroid: "250,105", area: "0.2" },
  { id: 105, name: "창문2", bbox: "[100, 380, 110, 450]", centroid: "105,415", area: "0.2" },
];

// Mock 객체 데이터 (가구, 설비 등 - bbox는 JSON 문자열)
const mockObjects: ObjectInfo[] = [
  { id: 201, name: "소파", bbox: "[150, 150, 280, 220]", centroid: "215,185" },
  { id: 202, name: "TV", bbox: "[320, 120, 380, 160]", centroid: "350,140" },
  { id: 203, name: "침대1", bbox: "[130, 340, 250, 450]", centroid: "190,395" },
  { id: 204, name: "침대2", bbox: "[300, 330, 420, 420]", centroid: "360,375" },
  { id: 205, name: "변기", bbox: "[470, 340, 520, 390]", centroid: "495,365" },
  { id: 206, name: "세면대", bbox: "[470, 310, 530, 340]", centroid: "500,325" },
];

// Mock 도면 분석 결과 (API 응답 형식)
export const mockFloorPlanResult: FloorPlanUploadResponse = {
  floorPlanId: 1,
  name: "APT_FP_SPA_001168733",
  imageUrl: "/mock-floorplan.png", // 실제로는 업로드된 이미지 사용
  rooms: mockRooms,
  structures: mockStructures,
  objects: mockObjects,
  totalArea: 71.3,
  roomCount: 5,
};
