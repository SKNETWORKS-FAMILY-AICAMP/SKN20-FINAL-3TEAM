package com.example.skn20.component;

import com.example.skn20.entity.LandChar;
import com.example.skn20.entity.Law;
import com.example.skn20.repository.LandCharRepository;
import com.example.skn20.repository.LawRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * CSV 데이터 초기화 컴포넌트
 * 서버 시작 시 토지특성정보와 법규조례 데이터를 DB에 로드
 * 중복 방지: 이미 데이터가 있으면 스킵
 */
@Slf4j
//@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private static final int BATCH_SIZE = 1000;

    private final LandCharRepository landCharRepository;
    private final LawRepository lawRepository;

    @Override
    public void run(String... args) throws Exception {
        log.info("=".repeat(60));
        log.info("데이터 초기화 시작");
        log.info("=".repeat(60));

        // 법규조례 로드
        loadLawData();

        // 토지특성정보 로드
        loadLandCharData();

        log.info("=".repeat(60));
        log.info("데이터 초기화 완료");
        log.info("=".repeat(60));
    }

    /**
     * 토지특성정보 CSV 로드
     */
    @Transactional
    public void loadLandCharData() {
        try {
            // 이미 데이터가 있으면 스킵
            long count = landCharRepository.count();
            if (count > 0) {
                log.info("토지특성정보 데이터가 이미 존재합니다. ({}건) - 스킵", count);
                return;
            }

            log.info("토지특성정보 데이터 로드 중...");
            ClassPathResource resource = new ClassPathResource("data/토지특성정보_혼합_final_2.csv");

            int loadedCount = 0;
            int skippedCount = 0;
            int lineNumber = 0;
            List<LandChar> batch = new ArrayList<>(BATCH_SIZE);

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // 헤더 스킵
                String headerLine = br.readLine();
                lineNumber++;
                log.debug("CSV 헤더: {}", headerLine);

                String line;
                while ((line = br.readLine()) != null) {
                    lineNumber++;
                    try {
                        String[] columns = parseCsvLine(line);
                        
                        if (columns.length < 14) {
                            log.warn("[라인 {}] 컬럼 수 부족: {} (최소 14개 필요)", lineNumber, columns.length);
                            skippedCount++;
                            continue;
                        }

                        // LandChar 엔티티 생성
                        LandChar landChar = LandChar.builder()
                                .legalDongCode(getValueOrNull(columns, 0))
                                .legalDongName(getValueOrNull(columns, 1))
                                .ledgerType(getValueOrNull(columns, 2))
                                .lotNumber(getValueOrNull(columns, 3))
                                .landCategory(getValueOrNull(columns, 4))
                                .landArea(parseFloat(getValueOrNull(columns, 5)))
                                .zone1(getValueOrNull(columns, 6))
                                .zone2(getValueOrNull(columns, 7))
                                .landUse(getValueOrNull(columns, 8))
                                .terrainHeight(getValueOrNull(columns, 9))
                                .terrainShape(getValueOrNull(columns, 10))
                                .roadAccess(getValueOrNull(columns, 11))
                                .queryKey(getValueOrNull(columns, 12))
                                .regionCode(getValueOrNull(columns, 13))
                                .build();

                        batch.add(landChar);
                        loadedCount++;

                        // 배치 단위로 저장
                        if (batch.size() >= BATCH_SIZE) {
                            landCharRepository.saveAll(batch);
                            batch.clear();
                            log.info("토지특성정보 로드 중... {}건 완료 (현재 라인: {})", loadedCount, lineNumber);
                        }

                    } catch (Exception e) {
                        if (skippedCount < 10) { // 처음 10개만 상세 로그
                            log.error("[라인 {}] 토지특성정보 처리 중 오류", lineNumber, e);
                        }
                        skippedCount++;
                    }
                }

                // 남은 데이터 저장
                if (!batch.isEmpty()) {
                    landCharRepository.saveAll(batch);
                    batch.clear();
                }
            }

            log.info("토지특성정보 로드 완료: {}건 저장, {}건 스킵", loadedCount, skippedCount);

        } catch (Exception e) {
            log.error("토지특성정보 로드 실패", e);
        }
    }

    /**
     * 법규조례 CSV 로드
     */
    @Transactional
    public void loadLawData() {
        try {
            // 이미 데이터가 있으면 스킵
            long count = lawRepository.count();
            if (count > 0) {
                log.info("법규조례 데이터가 이미 존재합니다. ({}건) - 스킵", count);
                return;
            }

            log.info("법규조례 데이터 로드 중...");
            ClassPathResource resource = new ClassPathResource("data/법규조례_final.csv");

            int loadedCount = 0;
            int skippedCount = 0;
            int lineNumber = 0;
            List<Law> batch = new ArrayList<>(BATCH_SIZE);

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // 헤더 스킵
                String headerLine = br.readLine();
                lineNumber++;
                log.debug("CSV 헤더: {}", headerLine);

                String line;
                while ((line = br.readLine()) != null) {
                    lineNumber++;
                    try {
                        String[] columns = parseCsvLine(line);
                        
                        if (columns.length < 6) {
                            log.warn("[라인 {}] 컬럼 수 부족: {} (최소 6개 필요)", lineNumber, columns.length);
                            skippedCount++;
                            continue;
                        }

                        // Law 엔티티 생성
                        Law law = Law.builder()
                                .regionCode(getValueOrNull(columns, 0))
                                .zoneDistrictName(getValueOrNull(columns, 1))
                                .lawName(getValueOrNull(columns, 2))
                                .landUseActivity(getValueOrNull(columns, 3))
                                .permissionStatus(getValueOrNull(columns, 4))
                                .conditionException(getValueOrNull(columns, 5))
                                .build();

                        batch.add(law);
                        loadedCount++;

                        // 배치 단위로 저장
                        if (batch.size() >= BATCH_SIZE) {
                            lawRepository.saveAll(batch);
                            batch.clear();
                            log.info("법규조례 로드 중... {}건 완료 (현재 라인: {})", loadedCount, lineNumber);
                        }

                    } catch (Exception e) {
                        if (skippedCount < 10) { // 처음 10개만 상세 로그
                            log.error("[라인 {}] 법규조례 처리 중 오류", lineNumber, e);
                        }
                        skippedCount++;
                    }
                }

                // 남은 데이터 저장
                if (!batch.isEmpty()) {
                    lawRepository.saveAll(batch);
                    batch.clear();
                }
            }

            log.info("법규조례 로드 완료: {}건 저장, {}건 스킵", loadedCount, skippedCount);

        } catch (Exception e) {
            log.error("법규조례 로드 실패", e);
        }
    }

    /**
     * CSV 라인 파싱 (콤마로 구분, 따옴표 처리)
     */
    private String[] parseCsvLine(String line) {
        // 간단한 CSV 파싱 (복잡한 경우 OpenCSV 등 라이브러리 사용 권장)
        return line.split(",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", -1);
    }

    /**
     * 안전하게 값 가져오기
     */
    private String getValueOrNull(String[] columns, int index) {
        if (index >= columns.length) {
            return null;
        }
        String value = columns[index].trim();
        // 따옴표 제거
        if (value.startsWith("\"") && value.endsWith("\"")) {
            value = value.substring(1, value.length() - 1);
        }
        return value.isEmpty() ? null : value;
    }

    /**
     * Float 파싱
     */
    private Float parseFloat(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        try {
            return Float.parseFloat(value);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
