package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AdminStatsResponse {
    private Long userCount;        // 총 사용자 수
    private Long floorPlanCount;   // 총 도면 수
    private Long recentFloorPlan;  // 최근 7일 등록된 도면 수
    private Long totalChatCount;   // 총 챗봇 대화 수
    private Long recentChatCount;  // 최근 7일 챗봇 대화 수
    private Long chatRoomCount;    // 총 챗봇 방 수
}
