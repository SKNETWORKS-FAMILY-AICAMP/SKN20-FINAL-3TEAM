package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "room")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Room {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(length = 100)
    private String spcname;

    String ocrname;

    String bbox;

    String centroid;

    float area;

    float areapercent;

    @ManyToOne
    @JoinColumn(name = "floor_plan_id", nullable = false)
    private FloorPlan floorPlan; // 연관된 FloorPlan 엔티티

    
    
}
