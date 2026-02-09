package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ActivityLogResponse {
    private Long id;
    private String type;        // "USER", "FLOORPLAN", "CHATROOM", "CHAT"
    private String userName;    // 사용자 이름
    private String userEmail;   // 사용자 이메일
    private String action;      // "회원가입", "도면 업로드", "챗봇 사용" 등
    private String details;     // 상세 정보
    private LocalDate createdAt; // 생성 날짜
}
