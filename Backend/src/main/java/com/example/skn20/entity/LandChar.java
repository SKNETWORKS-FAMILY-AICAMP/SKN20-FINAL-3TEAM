package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 토지 특성 정보 엔티티
 * 법정동 코드, 지목, 면적, 용도지역 등 토지의 물리적/법적 특성 정보를 저장
 */
@Entity
@Table(name = "land_char")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class LandChar {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "legal_dong_code", columnDefinition = "TEXT")
    private String legalDongCode; // 법정동 코드 (예: 1168010100)
    
    @Column(name = "legal_dong_name", columnDefinition = "TEXT")
    private String legalDongName; // 법정동 이름 (예: 서울특별시 강남구 역삼동)
    
    @Column(name = "ledger_type", columnDefinition = "TEXT")
    private String ledgerType; // 대장 구분 (토지/임야)
    
    @Column(name = "lot_number", columnDefinition = "TEXT")
    private String lotNumber; // 지번 (예: 123-45)
    
    @Column(name = "land_category", columnDefinition = "TEXT")
    private String landCategory; // 지목 (대, 전, 답, 임야 등)
    
    @Column(name = "land_area")
    private Float landArea; // 토지 면적 (㎡)
    
    @Column(name = "zone1", columnDefinition = "TEXT")
    private String zone1; // 용도지역1 (주거지역, 상업지역 등)
    
    @Column(name = "zone2", columnDefinition = "TEXT")
    private String zone2; // 용도지역2 (세부 용도지역)
    
    @Column(name = "land_use", columnDefinition = "TEXT")
    private String landUse; // 토지 이용 현황
    
    @Column(name = "terrain_height", columnDefinition = "TEXT")
    private String terrainHeight; // 지형 높이 (고지, 평지, 저지 등)
    
    @Column(name = "terrain_shape", columnDefinition = "TEXT")
    private String terrainShape; // 지형 형상 (정방형, 사다리형 등)
    
    @Column(name = "road_access", columnDefinition = "TEXT")
    private String roadAccess; // 도로 접면 (광대, 중로, 세로 등)
    
    @Column(name = "address_text", columnDefinition = "TEXT")
    private String addressText; // 주소 텍스트 (법정동명 + 지번, "지번없음" 포함) - query_key 대체
    
    @Column(name = "region_code", columnDefinition = "TEXT")
    private String regionCode; // 지역 코드 (시군구 코드)
}
