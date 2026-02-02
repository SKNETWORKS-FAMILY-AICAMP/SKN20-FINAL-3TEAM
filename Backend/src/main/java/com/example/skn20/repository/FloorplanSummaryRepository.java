package com.example.skn20.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import com.example.skn20.entity.FloorplanAnalysis;

@Repository
public interface FloorplanSummaryRepository extends JpaRepository<FloorplanAnalysis, Long>{

}
