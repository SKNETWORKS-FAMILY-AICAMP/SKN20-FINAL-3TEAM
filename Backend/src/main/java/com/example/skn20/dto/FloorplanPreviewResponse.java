package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 프론트엔드로 반환되는 도면 분석 미리보기 응답 DTO
 * DB에 저장되기 전, Python 서버의 분석 결과를 프론트에 즉시 반환하기 위한 용도
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorplanPreviewResponse {
    
    // 기본 정보
    private String topologyJson;          // 1번: topology.json 내용
    private String topologyImageUrl;      // 2번: 위상 그래프 이미지 URL
    private String assessmentJson;        // 3번: 요약, 평가 json (topology_graph.json 전체)
    
    // 분석 결과 데이터 (프론트 표시용)
    private Double windowlessRatio;       // 무창실 비율
    private Boolean hasSpecialSpace;      // 특수 공간 존재 여부
    private Integer bayCount;             // 베이 개수
    private Double balconyRatio;          // 발코니 비율
    private Double livingRoomRatio;       // 거실 비율
    private Double bathroomRatio;         // 욕실 비율
    private Double kitchenRatio;          // 주방 비율
    private Integer roomCount;            // 방 개수
    private String complianceGrade;       // 법적 준수 등급
    private String ventilationQuality;    // 환기 품질
    private Boolean hasEtcSpace;          // 기타 공간 존재 여부
    private String structureType;         // 구조 타입
    private Integer bathroomCount;        // 욕실 개수
    
    // 분석 설명 텍스트
    private String analysisDescription;   // 상세 분석 설명
    
    // 임베딩 벡터 (프론트에서 저장 시 다시 전달할 데이터)
    private double[] embedding;           // 1536차원 벡터
}
