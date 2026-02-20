package com.example.skn20.repository;

import com.example.skn20.entity.FloorPlan;

import java.time.LocalDateTime;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface FloorPlanRepository extends JpaRepository<FloorPlan, Long> {
    @Query("SELECT COUNT(fp) FROM FloorPlan fp WHERE fp.createdAt > :date")
    long countRecentFloorPlans(@Param("date") LocalDateTime date);

    List<FloorPlan> findTop10ByUserIdOrderByCreatedAtDesc(Long userId);

    List<FloorPlan> findAllByOrderByCreatedAtDesc();
}
