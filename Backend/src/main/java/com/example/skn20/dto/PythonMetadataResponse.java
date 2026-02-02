package com.example.skn20.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * Python 서버로부터 받는 4번 응답 (메타데이터 + 임베딩)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PythonMetadataResponse {
    
    @JsonProperty("document_id")
    private String documentId;
    
    // metadata 객체 (Map으로 받음)
    private Map<String, Object> metadata;
    
    // 분석 설명 텍스트
    private String document;
    
    // 임베딩 벡터 전체 (1536차원)
    private double[] embedding;
}
