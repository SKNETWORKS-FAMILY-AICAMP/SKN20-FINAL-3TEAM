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
public class ChatHistoryDetailResponse {
    private Long id;
    private String chatRoomName;
    private String userName;
    private String userEmail;
    private String question;
    private String answer;
    private LocalDateTime createdAt;
}
