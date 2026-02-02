package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 프론트엔드에서 "저장" 버튼 클릭 시 전달되는 요청 DTO
 * 프리뷰 단계에서 받았던 모든 데이터를 다시 전달받아 DB에 저장
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class FloorplanSaveRequest {
    
    // 기본 정보
    private String name;                  // 도면 이름
    private String imageUrl;              // 원본 이미지 URL
    private String topologyJson;          // topology.json 내용
    private String topologyImageUrl;      // 위상 그래프 이미지 URL
    
    // 분석 결과 데이터
    private Double windowlessRatio;
    private Boolean hasSpecialSpace;
    private Integer bayCount;
    private Double balconyRatio;
    private Double livingRoomRatio;
    private Double bathroomRatio;
    private Double kitchenRatio;
    private Integer roomCount;
    private String complianceGrade;
    private String ventilationQuality;
    private Boolean hasEtcSpace;
    private String structureType;
    private Integer bathroomCount;
    
    // 분석 설명 텍스트
    private String analysisDescription;
    
    // 임베딩 벡터
    private double[] embedding;
}
