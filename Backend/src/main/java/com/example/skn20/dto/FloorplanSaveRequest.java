package com.example.skn20.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 프론트엔드에서 "저장" 버튼 클릭 시 전달되는 요청 DTO
 * 3번(assessmentJson)만 전달받아 Python으로 전송 후 4번을 받아 DB에 저장
 * 이미지는 MultipartFile로 별도 전달
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class FloorplanSaveRequest {
    
    // 기본 정보
    private String name;                  // 도면 이름
    
    // 3번: 요약, 평가 json (Python으로 전송할 데이터)
    private String assessmentJson;        // topology_graph.json 전체 (JSON string)
}
