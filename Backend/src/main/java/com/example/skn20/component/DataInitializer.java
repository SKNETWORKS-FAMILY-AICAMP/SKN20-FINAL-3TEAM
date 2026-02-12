package com.example.skn20.component;

import com.example.skn20.entity.InternalEval;
import com.example.skn20.entity.LandChar;
import com.example.skn20.entity.Law;
import com.example.skn20.entity.Usebuilding;
import com.example.skn20.repository.InternalEvalRepository;
import com.example.skn20.repository.LandCharRepository;
import com.example.skn20.repository.LawRepository;
import com.example.skn20.repository.UsebuildingRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.opencsv.CSVReader;
import com.opencsv.exceptions.CsvException;
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
@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private static final int BATCH_SIZE = 1000;

    private final LandCharRepository landCharRepository;
    private final LawRepository lawRepository;
    private final InternalEvalRepository internalEvalRepository;
    private final UsebuildingRepository usebuildingRepository;
    private final ObjectMapper objectMapper;

    @Override
    public void run(String... args) throws Exception {
        log.info("=".repeat(60));
        log.info("데이터 초기화 시작");
        log.info("=".repeat(60));
        
        // 사내 평가 문서 로드
        loadInternalEvalData();
        
        // 건축물용도 정의 로드
        loadUsebuildingData();

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
            ClassPathResource resource = new ClassPathResource("data/토지특성정보_전처리완료.csv");

            int loadedCount = 0;
            int skippedCount = 0;
            int lineNumber = 0;
            List<LandChar> batch = new ArrayList<>(BATCH_SIZE);

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // 헤더 파싱하여 컬럼 인덱스 찾기
                String headerLine = br.readLine();
                lineNumber++;
                log.debug("CSV 헤더: {}", headerLine);
                
                String[] headers = parseCsvLine(headerLine);
                int legalDongCodeIdx = findColumnIndex(headers, "법정동코드", "legal_dong_code");
                int legalDongNameIdx = findColumnIndex(headers, "법정동명", "legal_dong_name");
                int ledgerTypeIdx = findColumnIndex(headers, "대장구분명", "ledger_type");
                int lotNumberIdx = findColumnIndex(headers, "지번", "lot_number");
                int landCategoryIdx = findColumnIndex(headers, "지목명", "land_category");
                int landAreaIdx = findColumnIndex(headers, "토지면적", "land_area");
                int zone1Idx = findColumnIndex(headers, "용도지역명1", "zone1");
                int zone2Idx = findColumnIndex(headers, "용도지역명2", "zone2");
                int landUseIdx = findColumnIndex(headers, "토지이용상황", "land_use");
                int terrainHeightIdx = findColumnIndex(headers, "지형높이", "terrain_height");
                int terrainShapeIdx = findColumnIndex(headers, "지형형상", "terrain_shape");
                int roadAccessIdx = findColumnIndex(headers, "도로접면", "road_access");
                int addressTextIdx = findColumnIndex(headers, "주소_텍스트", "address_text");
                int regionCodeIdx = findColumnIndex(headers, "구분코드", "region_code");
                
                log.info("컬럼 매핑: 법정동코드={}, 법정동명={}, 대장구분명={}, 지번={}, 지목명={}, 토지면적={}, 용도지역명1={}, 용도지역명2={}, 토지이용상황={}, 지형높이={}, 지형형상={}, 도로접면={}, 주소_텍스트={}, 구분코드={}", 
                    legalDongCodeIdx, legalDongNameIdx, ledgerTypeIdx, lotNumberIdx, landCategoryIdx, landAreaIdx, zone1Idx, zone2Idx, landUseIdx, terrainHeightIdx, terrainShapeIdx, roadAccessIdx, addressTextIdx, regionCodeIdx);

                String line;
                while ((line = br.readLine()) != null) {
                    lineNumber++;
                    try {
                        String[] columns = parseCsvLine(line);
                        
                        // 최소한 필수 컬럼이 있는지 확인 (유효성 체크만)
                        if (columns.length < 5) {
                            log.warn("[라인 {}] 컬럼 수 부족: {}", lineNumber, columns.length);
                            skippedCount++;
                            continue;
                        }

                        // LandChar 엔티티 생성
                        LandChar landChar = LandChar.builder()
                                .legalDongCode(getValueOrNull(columns, legalDongCodeIdx))
                                .legalDongName(getValueOrNull(columns, legalDongNameIdx))
                                .ledgerType(getValueOrNull(columns, ledgerTypeIdx))
                                .lotNumber(getValueOrNull(columns, lotNumberIdx))
                                .landCategory(getValueOrNull(columns, landCategoryIdx))
                                .landArea(parseFloat(getValueOrNull(columns, landAreaIdx)))
                                .zone1(getValueOrNull(columns, zone1Idx))
                                .zone2(getValueOrNull(columns, zone2Idx))
                                .landUse(getValueOrNull(columns, landUseIdx))
                                .terrainHeight(getValueOrNull(columns, terrainHeightIdx))
                                .terrainShape(getValueOrNull(columns, terrainShapeIdx))
                                .roadAccess(getValueOrNull(columns, roadAccessIdx))
                                .addressText(getValueOrNull(columns, addressTextIdx))
                                .regionCode(getValueOrNull(columns, regionCodeIdx))
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
            ClassPathResource resource = new ClassPathResource("data/법규조례_전처리완료.csv");

            int loadedCount = 0;
            int skippedCount = 0;
            int lineNumber = 0;
            List<Law> batch = new ArrayList<>(BATCH_SIZE);

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // 헤더 파싱하여 컬럼 인덱스 찾기
                String headerLine = br.readLine();
                lineNumber++;
                log.debug("CSV 헤더: {}", headerLine);
                
                String[] headers = parseCsvLine(headerLine);
                int regionCodeIdx = findColumnIndex(headers, "구분코드", "region_code");
                int regionNameIdx = findColumnIndex(headers, "지역명", "region_name");
                int lawNameIdx = findColumnIndex(headers, "법률명", "law_name");
                int zoneDistrictNameIdx = findColumnIndex(headers, "용도지역지구명", "zone_district_name");
                int landUseActivityIdx = findColumnIndex(headers, "토지이용명", "land_use_activity");
                int permissionCategoryIdx = findColumnIndex(headers, "가능여부_정규화", "permission_category");
                int conditionExceptionIdx = findColumnIndex(headers, "조건제한예외사항", "condition_exception");
                
                log.info("컬럼 매핑: 구분코드={}, 지역명={}, 법률명={}, 용도지역지구명={}, 토지이용명={}, 가능여부_정규화={}, 조건제한예외사항={}", 
                    regionCodeIdx, regionNameIdx, lawNameIdx, zoneDistrictNameIdx, landUseActivityIdx, permissionCategoryIdx, conditionExceptionIdx);

                String line;
                while ((line = br.readLine()) != null) {
                    lineNumber++;
                    try {
                        String[] columns = parseCsvLine(line);
                        
                        if (columns.length < 7) {
                            log.warn("[라인 {}] 컬럼 수 부족: {} (최소 7개 필요)", lineNumber, columns.length);
                            skippedCount++;
                            continue;
                        }

                        // Law 엔티티 생성
                        Law law = Law.builder()
                                .regionCode(getValueOrNull(columns, regionCodeIdx))
                                .regionName(getValueOrNull(columns, regionNameIdx))
                                .lawName(getValueOrNull(columns, lawNameIdx))
                                .zoneDistrictName(getValueOrNull(columns, zoneDistrictNameIdx))
                                .landUseActivity(getValueOrNull(columns, landUseActivityIdx))
                                .permissionCategory(getValueOrNull(columns, permissionCategoryIdx))
                                .conditionException(getValueOrNull(columns, conditionExceptionIdx))
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
        if (index < 0 || index >= columns.length) {
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
    
    /**
     * 헤더에서 컬럼 인덱스 찾기 (여러 가능한 이름 지원)
     */
    private int findColumnIndex(String[] headers, String... possibleNames) {
        for (int i = 0; i < headers.length; i++) {
            String header = headers[i].trim()
                .replace("\"", "")
                .replace(" ", "")
                .replace("_", "")
                .toLowerCase();
            
            for (String name : possibleNames) {
                String searchName = name.replace("_", "").toLowerCase();
                if (header.contains(searchName) || searchName.contains(header)) {
                    return i;
                }
            }
        }
        log.warn("컬럼을 찾지 못했습니다. 찾으려는 이름들: {}", String.join(", ", possibleNames));
        return -1; // 못 찾으면 -1 반환
    }
    
    /**
     * 사내 평가 문서 JSON 로드
     */
    @Transactional
    public void loadInternalEvalData() {
        try {
            // 이미 데이터가 있으면 스킵
            long count = internalEvalRepository.count();
            if (count > 0) {
                log.info("사내 평가 문서 데이터가 이미 존재합니다. ({}건) - 스킵", count);
                return;
            }

            log.info("사내 평가 문서 데이터 로드 중...");
            ClassPathResource resource = new ClassPathResource("data/evaluation_docs_export.json");

            int loadedCount = 0;
            int skippedCount = 0;
            List<InternalEval> batch = new ArrayList<>(BATCH_SIZE);

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // JSON 배열 파싱
                JsonNode rootNode = objectMapper.readTree(br);
                
                if (!rootNode.isArray()) {
                    log.error("JSON 파일이 배열 형식이 아닙니다.");
                    return;
                }

                for (JsonNode node : rootNode) {
                    try {
                        // keywords 추출 (metadata.keywords)
                        String keywords = null;
                        if (node.has("metadata") && node.get("metadata").has("keywords")) {
                            keywords = node.get("metadata").get("keywords").asText();
                        }

                        // document 추출
                        String document = node.has("document") ? node.get("document").asText() : null;
                        if (document == null || document.isEmpty()) {
                            log.warn("document가 없는 항목 스킵");
                            skippedCount++;
                            continue;
                        }

                        // embedding 추출 (embedding.values 배열)
                        float[] embedding = null;
                        if (node.has("embedding") && node.get("embedding").has("values")) {
                            JsonNode valuesNode = node.get("embedding").get("values");
                            if (valuesNode.isArray()) {
                                int dimension = valuesNode.size();
                                embedding = new float[dimension];
                                for (int i = 0; i < dimension; i++) {
                                    embedding[i] = (float) valuesNode.get(i).asDouble();
                                }
                            }
                        }

                        // InternalEval 엔티티 생성
                        InternalEval internalEval = InternalEval.builder()
                                .keywords(keywords)
                                .document(document)
                                .embedding(embedding)
                                .build();

                        batch.add(internalEval);
                        loadedCount++;

                        // 배치 단위로 저장
                        if (batch.size() >= BATCH_SIZE) {
                            internalEvalRepository.saveAll(batch);
                            batch.clear();
                            log.info("사내 평가 문서 로드 중... {}건 완료", loadedCount);
                        }

                    } catch (Exception e) {
                        if (skippedCount < 10) { // 처음 10개만 상세 로그
                            log.error("사내 평가 문서 처리 중 오류", e);
                        }
                        skippedCount++;
                    }
                }

                // 남은 데이터 저장
                if (!batch.isEmpty()) {
                    internalEvalRepository.saveAll(batch);
                    batch.clear();
                }
            }

            log.info("사내 평가 문서 로드 완료: {}건 저장, {}건 스킵", loadedCount, skippedCount);

        } catch (Exception e) {
            log.error("사내 평가 문서 로드 실패", e);
        }
    }
    
    /**
     * 건축물용도 정의 CSV 로드 (OpenCSV 사용 - 줄바꿈 처리)
     */
    @Transactional
    public void loadUsebuildingData() {
        try {
            // 이미 데이터가 있으면 스킵
            long count = usebuildingRepository.count();
            if (count > 0) {
                log.info("건축물용도 정의 데이터가 이미 존재합니다. ({}건) - 스킵", count);
                return;
            }

            log.info("건축물용도 정의 데이터 로드 중...");
            ClassPathResource resource = new ClassPathResource("data/건축물용도_정의.csv");

            int loadedCount = 0;
            int skippedCount = 0;
            List<Usebuilding> batch = new ArrayList<>(BATCH_SIZE);

            try (CSVReader csvReader = new CSVReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                // 모든 줄 읽기 (OpenCSV가 줄바꿈 포함 필드를 올바르게 처리)
                List<String[]> allRows = csvReader.readAll();
                
                if (allRows.isEmpty()) {
                    log.warn("CSV 파일이 비어있습니다.");
                    return;
                }

                // 헤더 파싱
                String[] headers = allRows.get(0);
                log.info("CSV 헤더: {}", String.join(", ", headers));
                
                int categoryNameIdx = findColumnIndex(headers, "category_name", "카테고리명");
                int facilityNameIdx = findColumnIndex(headers, "facility_name", "시설명");
                int descriptionIdx = findColumnIndex(headers, "description", "설명");
                int urlIdx = findColumnIndex(headers, "url", "URL");
                
                log.info("컬럼 매핑: category_name={}, facility_name={}, description={}, url={}", 
                    categoryNameIdx, facilityNameIdx, descriptionIdx, urlIdx);
                
                // 필수 컬럼 체크
                if (categoryNameIdx < 0 || facilityNameIdx < 0) {
                    log.error("필수 컬럼 매핑 실패! category_name={}, facility_name={}", 
                        categoryNameIdx, facilityNameIdx);
                    return;
                }

                // 데이터 행 처리 (헤더 제외)
                for (int i = 1; i < allRows.size(); i++) {
                    try {
                        String[] columns = allRows.get(i);
                        
                        // CSV는 6개 컬럼 (category_code, category_name, facility_code, facility_name, description, url)
                        if (columns.length < 6) {
                            log.warn("[라인 {}] 컬럼 수 부족: {} (예상: 6개)", i + 1, columns.length);
                            skippedCount++;
                            continue;
                        }

                        // Usebuilding 엔티티 생성
                        Usebuilding usebuilding = Usebuilding.builder()
                                .category_name(getValueOrNull(columns, categoryNameIdx))
                                .facility_name(getValueOrNull(columns, facilityNameIdx))
                                .description(getValueOrNull(columns, descriptionIdx))
                                .url(getValueOrNull(columns, urlIdx))
                                .build();

                        batch.add(usebuilding);
                        loadedCount++;

                        // 배치 단위로 저장
                        if (batch.size() >= BATCH_SIZE) {
                            usebuildingRepository.saveAll(batch);
                            batch.clear();
                            log.info("건축물용도 정의 로드 중... {}건 완료 (현재 라인: {})", loadedCount, i + 1);
                        }

                    } catch (Exception e) {
                        if (skippedCount < 10) { // 처음 10개만 상세 로그
                            log.error("[라인 {}] 건축물용도 정의 처리 중 오류", i + 1, e);
                        }
                        skippedCount++;
                    }
                }

                // 남은 데이터 저장
                if (!batch.isEmpty()) {
                    usebuildingRepository.saveAll(batch);
                    batch.clear();
                }
            } catch (CsvException e) {
                log.error("CSV 파싱 오류", e);
            }

            log.info("건축물용도 정의 로드 완료: {}건 저장, {}건 스킵", loadedCount, skippedCount);

        } catch (Exception e) {
            log.error("건축물용도 정의 로드 실패", e);
        }
    }
}
