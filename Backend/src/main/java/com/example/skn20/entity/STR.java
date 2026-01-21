package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "strs")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class STR {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(length = 100)
    private String name;

    private String bbox;

    private String centroid;

    private String area;

    @ManyToOne
    @JoinColumn(name = "room_id", nullable = false)
    private Room room; // 연관된 Room 엔티티
    
    
}
