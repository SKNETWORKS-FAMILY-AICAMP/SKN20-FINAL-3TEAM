package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AdminFloorPlanResponse {
    private Long id;
    private String name;
    private String imageUrl;
    private UserSimpleDto user;
    private LocalDateTime createdAt;
    private Integer roomCount;  // FloorplanAnalysis에서 가져옴
    private String assessmentJson;  // 분석 결과 JSON
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class UserSimpleDto {
        private Long id;
        private String email;
        private String name;
        private String role;
    }
}
