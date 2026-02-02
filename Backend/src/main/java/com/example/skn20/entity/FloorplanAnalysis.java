package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "floorplan_analysis")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorplanAnalysis {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @OneToOne
    @JoinColumn(name = "floorplan_id", nullable = false, unique = true)
    private FloorPlan floorPlan;
    
    // 분석 항목들
    @Column(name = "windowless_ratio")
    private Double windowlessRatio;
    
    @Column(name = "has_special_space")
    private Boolean hasSpecialSpace;
    
    @Column(name = "bay_count")
    private Integer bayCount;
    
    @Column(name = "balcony_ratio")
    private Double balconyRatio;
    
    @Column(name = "living_room_ratio")
    private Double livingRoomRatio;
    
    @Column(name = "bathroom_ratio")
    private Double bathroomRatio;
    
    @Column(name = "kitchen_ratio")
    private Double kitchenRatio;
    
    @Column(name = "room_count")
    private Integer roomCount;
    
    @Column(name = "compliance_grade", length = 50)
    private String complianceGrade;
    
    @Column(name = "ventilation_quality", length = 50)
    private String ventilationQuality;
    
    @Column(name = "has_etc_space")
    private Boolean hasEtcSpace;
    
    @Column(name = "structure_type", length = 50)
    private String structureType;
    
    @Column(name = "bathroom_count")
    private Integer bathroomCount;
    
    // 임베딩 값 (VECTOR 자료형) - PostgreSQL pgvector 사용
    // 1536은 OpenAI embedding-3-small 모델 기준
    @Column(name = "embedding", columnDefinition = "vector(1536)")
    private double[] embedding;
}
