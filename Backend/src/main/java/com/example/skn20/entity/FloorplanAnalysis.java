package com.example.skn20.entity;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "floorplanSummary")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorplanSummary {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @OneToOne
    @JoinColumn(name = "floorplan_id", nullable = true)
    private FloorPlan floorPlan;
    
    private String eval;
    
    // 임베딩 값 (VECTOR 자료형)
    // 1536은 OpenAI embedding-3-small 모델 기준입니다.
    @Column(name = "embedding", columnDefinition = "vector(1536)")
    private float[] embedding;
}
