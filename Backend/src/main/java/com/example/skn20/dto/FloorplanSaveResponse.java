package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

/**
 * 도면 저장 성공 후 반환되는 응답 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorplanSaveResponse {
    
    private Long floorplanId;              // 저장된 FloorPlan ID
    private Long analysisId;               // 저장된 FloorplanAnalysis ID
    private String name;                   // 도면 이름
    private LocalDate createdAt;           // 생성 일자
    private String message;                // 성공 메시지
}
