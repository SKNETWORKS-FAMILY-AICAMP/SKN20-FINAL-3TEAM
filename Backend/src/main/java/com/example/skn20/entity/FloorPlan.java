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
    
    @Column(name = "topology_json", columnDefinition = "TEXT")
    private String topologyJson;
    
    @Column(name = "topology_image_url", length = 500)
    private String topologyImageUrl;
    
    @OneToOne(mappedBy = "floorPlan", cascade = CascadeType.ALL, orphanRemoval = true)
    private FloorplanAnalysis analysis;
}
