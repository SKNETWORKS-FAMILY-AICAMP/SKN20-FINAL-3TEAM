package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Python 서버로부터 받는 4번 응답 (메타데이터 + 임베딩)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PythonMetadataResponse {
    
    private String documentId;
    
    // metadata 객체
    private Metadata metadata;
    
    // 분석 설명 텍스트
    private String document;
    
    // 임베딩 객체
    private Embedding embedding;
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Metadata {
        private String imageName;
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
    }
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Embedding {
        private Integer dimension;
        private double[] firstValues; // 전체 임베딩 배열
    }
}
