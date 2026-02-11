package com.example.skn20.repository;

import com.example.skn20.entity.LandChar;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 토지 특성 정보 Repository
 * 법정동 코드, 지역 코드, 주소 텍스트 등으로 토지 특성 정보를 조회
 */
@Repository
public interface LandCharRepository extends JpaRepository<LandChar, Long> {
    
    /**
     * 법정동 코드로 토지 특성 조회
     */
    List<LandChar> findByLegalDongCode(String legalDongCode);
    
    /**
     * 지역 코드로 토지 특성 조회
     */
    List<LandChar> findByRegionCode(String regionCode);
    
    /**
     * 주소 텍스트로 토지 특성 조회
     */
    Optional<LandChar> findByAddressText(String addressText);
    
    /**
     * 주소 텍스트 포함 검색
     */
    List<LandChar> findByAddressTextContaining(String addressText);
    
    /**
     * 법정동 코드와 지번으로 토지 특성 조회
     */
    Optional<LandChar> findByLegalDongCodeAndLotNumber(String legalDongCode, String lotNumber);
    
    /**
     * 용도지역1로 토지 특성 목록 조회
     */
    List<LandChar> findByZone1(String zone1);
    
    /**
     * 용도지역1과 용도지역2로 토지 특성 목록 조회
     */
    List<LandChar> findByZone1AndZone2(String zone1, String zone2);
    
    /**
     * 지목으로 토지 특성 목록 조회
     */
    List<LandChar> findByLandCategory(String landCategory);
    
    /**
     * 지역 코드와 용도지역1로 토지 특성 목록 조회
     */
    List<LandChar> findByRegionCodeAndZone1(String regionCode, String zone1);
}
