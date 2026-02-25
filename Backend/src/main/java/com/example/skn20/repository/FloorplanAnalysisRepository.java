package com.example.skn20.repository;

import com.example.skn20.entity.FloorplanAnalysis;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface FloorplanAnalysisRepository extends JpaRepository<FloorplanAnalysis, Long> {
    Optional<FloorplanAnalysis> findByFloorPlanId(Long floorPlanId);
}
