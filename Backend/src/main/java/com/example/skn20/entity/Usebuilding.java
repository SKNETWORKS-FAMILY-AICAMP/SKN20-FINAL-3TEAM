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
@Table(name = "useBuilding")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Usebuilding {
	
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long Id;
    
    @Column(name = "category_name", columnDefinition = "TEXT")
    private String category_name;

    @Column(name = "facility_name", columnDefinition = "TEXT")
    private String facility_name;
    
    @Column(name = "description", columnDefinition = "TEXT")
    private String description;	

    @Column(name = "url", columnDefinition = "TEXT")
    private String url;
}
