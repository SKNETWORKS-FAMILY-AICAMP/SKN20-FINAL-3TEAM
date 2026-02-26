package com.example.skn20.repository;

import com.example.skn20.entity.FloorplanAnalysis;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface FloorplanAnalysisRepository extends JpaRepository<FloorplanAnalysis, Long> {
    Optional<FloorplanAnalysis> findByFloorPlanId(Long floorPlanId);

    @Query("SELECT fa FROM FloorplanAnalysis fa WHERE fa.floorPlan.id IN :ids")
    List<FloorplanAnalysis> findByFloorPlanIdIn(@Param("ids") List<Long> ids);
}
