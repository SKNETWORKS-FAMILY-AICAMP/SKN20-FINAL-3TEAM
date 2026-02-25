package com.example.skn20.repository;

import com.example.skn20.entity.FloorPlan;

import java.time.LocalDateTime;
import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface FloorPlanRepository extends JpaRepository<FloorPlan, Long>,
                                              JpaSpecificationExecutor<FloorPlan> {
    @Query("SELECT COUNT(fp) FROM FloorPlan fp WHERE fp.createdAt > :date")
    long countRecentFloorPlans(@Param("date") LocalDateTime date);

    List<FloorPlan> findTop10ByUserIdOrderByCreatedAtDesc(Long userId);

    List<FloorPlan> findAllByOrderByCreatedAtDesc();

    @Query(value = "SELECT fp FROM FloorPlan fp JOIN FETCH fp.user LEFT JOIN FETCH fp.analysis",
           countQuery = "SELECT COUNT(fp) FROM FloorPlan fp")
    Page<FloorPlan> findAllWithUserAndAnalysis(Pageable pageable);
}
