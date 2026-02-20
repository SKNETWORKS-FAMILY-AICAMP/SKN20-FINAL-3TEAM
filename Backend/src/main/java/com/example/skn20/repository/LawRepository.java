package com.example.skn20.repository;

import com.example.skn20.entity.Law;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 법률/규제 정보 Repository
 * 지역 코드, 용도지역, 가능여부 카테고리 등으로 법률/규제 정보를 조회
 */
@Repository
public interface LawRepository extends JpaRepository<Law, Long> {
    
    /**
     * 지역 코드로 법률/규제 정보 조회
     */
    List<Law> findByRegionCode(String regionCode);
    
    /**
     * 용도지역/지구명으로 법률/규제 정보 조회
     */
    List<Law> findByZoneDistrictName(String zoneDistrictName);
    
    /**
     * 지역 코드와 용도지역/지구명으로 법률/규제 정보 조회
     */
    List<Law> findByRegionCodeAndZoneDistrictName(String regionCode, String zoneDistrictName);
    
    /**
     * 가능여부 카테고리로 법률/규제 정보 조회 (가능/불가/조건부/알수없음)
     */
    List<Law> findByPermissionCategory(String permissionCategory);
    
    /**
     * 지역 코드와 가능여부 카테고리로 법률/규제 정보 조회
     */
    List<Law> findByRegionCodeAndPermissionCategory(String regionCode, String permissionCategory);
    
    /**
     * 지역명으로 법률/규제 정보 조회
     */
    List<Law> findByRegionName(String regionName);
    
    /**
     * 지역명 포함 검색
     */
    List<Law> findByRegionNameContaining(String regionName);
    
    /**
     * 법률명으로 법률/규제 정보 조회
     */
    List<Law> findByLawName(String lawName);
    
    /**
     * 용도지역/지구명과 토지 이용 행위로 법률/규제 정보 조회
     */
    List<Law> findByZoneDistrictNameAndLandUseActivityContaining(String zoneDistrictName, String landUseActivity);
}
