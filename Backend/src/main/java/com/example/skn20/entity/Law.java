package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 법률/규제 정보 엔티티
 * 용도지역별 법률, 토지 이용 행위 허가 여부, 조건 및 예외사항 등을 저장
 */
@Entity
@Table(name = "law")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Law {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "region_code", length = 50)
    private String regionCode; // 지역 코드 (시군구 코드)
    
    @Column(name = "zone_district_name", length = 200)
    private String zoneDistrictName; // 용도지역/지구명 (제1종일반주거지역 등)
    
    @Column(name = "law_name", length = 200)
    private String lawName; // 관련 법률명 (국토의 계획 및 이용에 관한 법률 등)
    
    @Column(name = "land_use_activity", columnDefinition = "TEXT")
    private String landUseActivity; // 토지 이용 행위 (건축, 개발 등)
    
    @Column(name = "permission_status", length = 50)
    private String permissionStatus; // 허가 상태 (허용, 불허, 조건부허용 등)
    
    @Column(name = "condition_exception", columnDefinition = "TEXT")
    private String conditionException; // 조건 및 예외사항 (상세 설명)
}
