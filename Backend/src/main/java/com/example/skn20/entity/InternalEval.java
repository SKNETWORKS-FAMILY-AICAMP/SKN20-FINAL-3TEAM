package com.example.skn20.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "InternalEval")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class InternalEval {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(columnDefinition = "text")
    private String keywords;
    
    @Column(columnDefinition = "text")
    private String document;
    
    // 임베딩 값 (VECTOR 자료형)
    // 512는 evaluation_docs_export.json의 임베딩 차원입니다.
    @Column(name = "embedding", columnDefinition = "vector(512)")
    private float[] embedding;
}
