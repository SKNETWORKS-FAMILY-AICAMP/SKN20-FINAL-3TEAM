package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "floorplan")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorPlan {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    private User user; // 사용자 정보

    @Column(name = "created_at", nullable = false)
    private LocalDate createdAt; // 생성 일자
    
    @Column(length = 255)
    private String name;

    @Column(name = "image_url", length = 500)
    private String imageUrl;
    
    @Column(name = "assessment_json", columnDefinition = "TEXT")
    private String assessmentJson; // 3번: 요약, 평가 json (Python 전송용)
    
    @OneToOne(mappedBy = "floorPlan", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private FloorplanAnalysis analysis; // 4번: 메타데이터는 여기에 쪼개서 저장
}
