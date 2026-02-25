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
public class MyFloorPlanResponse {
    private Long id;
    private String name;
    private LocalDateTime createdAt;
}
