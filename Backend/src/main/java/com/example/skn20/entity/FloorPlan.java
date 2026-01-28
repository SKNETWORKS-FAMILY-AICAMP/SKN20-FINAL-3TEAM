package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonManagedReference;

@Entity
@Table(name = "floor_plans")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FloorPlan {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(length = 100)
    private String name;

    private String imageUrl;
    
    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    private User user; // 사용자 정보

    @Column(name = "created_at", nullable = false)
    private LocalDate createdAt; // 생성 일자

    @OneToMany
    @JoinColumn(name = "floor_plan_id")
    @JsonManagedReference
    private List<Room> rooms;
    
}
