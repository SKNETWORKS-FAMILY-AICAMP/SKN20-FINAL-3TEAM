package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonBackReference;
import com.fasterxml.jackson.annotation.JsonManagedReference;

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

    @OneToMany
    @JoinColumn(name = "STR_id")
    @JsonManagedReference
    private List<STR> strs;

    @OneToMany
    @JoinColumn(name = "OBJ_id")
    @JsonManagedReference
    private List<OBJ> objs;
    
    @ManyToOne
    @JoinColumn(name = "floorplan_id")
    @JsonBackReference
    private FloorPlan floorPlan;
    
}
