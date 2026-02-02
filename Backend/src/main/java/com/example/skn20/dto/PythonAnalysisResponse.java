package com.example.skn20.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Python CV 서버로부터 받는 분석 결과 응답 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PythonAnalysisResponse {
    
    @JsonProperty("topology_json")
    private String topologyJson;
    
    @JsonProperty("topology_image_url")
    private String topologyImageUrl;
    
    // 분석 결과 데이터
    @JsonProperty("windowless_ratio")
    private Double windowlessRatio;
    
    @JsonProperty("has_special_space")
    private Boolean hasSpecialSpace;
    
    @JsonProperty("bay_count")
    private Integer bayCount;
    
    @JsonProperty("balcony_ratio")
    private Double balconyRatio;
    
    @JsonProperty("living_room_ratio")
    private Double livingRoomRatio;
    
    @JsonProperty("bathroom_ratio")
    private Double bathroomRatio;
    
    @JsonProperty("kitchen_ratio")
    private Double kitchenRatio;
    
    @JsonProperty("room_count")
    private Integer roomCount;
    
    @JsonProperty("compliance_grade")
    private String complianceGrade;
    
    @JsonProperty("ventilation_quality")
    private String ventilationQuality;
    
    @JsonProperty("has_etc_space")
    private Boolean hasEtcSpace;
    
    @JsonProperty("structure_type")
    private String structureType;
    
    @JsonProperty("bathroom_count")
    private Integer bathroomCount;
    
    @JsonProperty("analysis_description")
    private String analysisDescription;
    
    @JsonProperty("embedding")
    private double[] embedding;
}
