package com.example.skn20.service;

import com.example.skn20.dto.FloorplanPreviewResponse;
import com.example.skn20.dto.FloorplanSaveRequest;
import com.example.skn20.dto.FloorplanSaveResponse;
import com.example.skn20.dto.PythonAnalysisResponse;
import com.example.skn20.dto.PythonMetadataResponse;
import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.FloorplanAnalysis;
import com.example.skn20.entity.User;
import com.example.skn20.repository.FloorPlanRepository;
import com.example.skn20.repository.FloorplanSummaryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;

@Service
@RequiredArgsConstructor
public class FloorPlanService {

	private final FloorPlanRepository floorPlanRepository;
	private final FloorplanSummaryRepository summaryRepository;
	private final RestTemplate restTemplate;

	@Value("${python.server.url:http://localhost:8000}")
	private String pythonServerUrl;

	/**
	 * 1. 분석 단계: Python CV 서버 호출 및 결과 반환 (DB 저장 없음)
	 * 프론트에서 이미지를 받아 Python 서버로 전송하고, 1번, 2번, 3번을 프리뷰 형태로 즉시 반환
	 */
	public FloorplanPreviewResponse analyzeFloorplan(MultipartFile file) throws Exception {
		String analyzeUrl = pythonServerUrl + "/analyze";
		try {
			// HTTP 헤더 설정
			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(MediaType.MULTIPART_FORM_DATA);

			// Multipart 요청 바디 구성
			MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
			body.add("file", new ByteArrayResource(file.getBytes()) {
				@Override
				public String getFilename() {
					return file.getOriginalFilename();
				}
			});

			System.out.println("[FloorPlanService] Python 서버로 요청 전송 중...");
			
			// Python 서버로 POST 요청
			HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);
			ResponseEntity<PythonAnalysisResponse> response = restTemplate.exchange(
					analyzeUrl,
					HttpMethod.POST,
					requestEntity,
					PythonAnalysisResponse.class
			);
			
			// Python 응답을 프리뷰 DTO로 변환
			PythonAnalysisResponse pythonResponse = response.getBody();
		if (pythonResponse == null) {
			throw new RuntimeException("Python 서버로부터 응답을 받지 못했습니다.");
		}

		System.out.println("[FloorPlanService] 응답 변환 중...");
		FloorplanPreviewResponse result = FloorplanPreviewResponse.builder()
				.topologyJson(pythonResponse.getTopologyJson())                   // 1번
				.topologyImageUrl(pythonResponse.getTopologyImageUrl())           // 2번
				.assessmentJson(pythonResponse.getAssessmentJson())               // 레거시
				.llmAnalysisJson(pythonResponse.getLlmAnalysisJson())             // 3번: compliance 포함
				.windowlessRatio(pythonResponse.getWindowlessRatio())
				.hasSpecialSpace(pythonResponse.getHasSpecialSpace())
				.bayCount(pythonResponse.getBayCount())
				.balconyRatio(pythonResponse.getBalconyRatio())
				.livingRoomRatio(pythonResponse.getLivingRoomRatio())
				.bathroomRatio(pythonResponse.getBathroomRatio())
				.kitchenRatio(pythonResponse.getKitchenRatio())
				.roomCount(pythonResponse.getRoomCount())
				.complianceGrade(pythonResponse.getComplianceGrade())
				.ventilationQuality(pythonResponse.getVentilationQuality())
				.hasEtcSpace(pythonResponse.getHasEtcSpace())
				.structureType(pythonResponse.getStructureType())
				.bathroomCount(pythonResponse.getBathroomCount())
				.analysisDescription(pythonResponse.getAnalysisDescription())
				.embedding(pythonResponse.getEmbedding())
				.build();
		
		return result;
		
		} catch (Exception e) {
			e.printStackTrace();
			throw e;
		}
	}

	/**
	 * 2. 저장 단계: 프론트에서 "저장" 버튼 클릭 시 DB에 저장
	 * 이미지 파일 저장 → 3번(assessmentJson)을 Python으로 전송 → 4번(메타데이터+임베딩) 받기 → DB 저장
	 * @Transactional로 모든 작업을 하나의 트랜잭션으로 관리
	 */
	@Transactional
	public FloorplanSaveResponse saveFloorplan(FloorplanSaveRequest request, MultipartFile imageFile, User user) throws Exception {
		
		// Step 0: 이미지 파일 저장
		String savedImagePath = saveImageFile(imageFile, user.getId());
		
		// Step 1: llmAnalysisJson을 Python 서버로 전송하여 4번(메타데이터+임베딩) 받기
		String generateMetadataUrl = pythonServerUrl + "/generate-metadata";

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.APPLICATION_JSON);

		// Python이 기대하는 형식: {"llm_analysis_json": "..."}
		java.util.Map<String, String> pythonRequest = new java.util.HashMap<>();
		pythonRequest.put("llm_analysis_json", request.getAssessmentJson());
		HttpEntity<java.util.Map<String, String>> requestEntity = new HttpEntity<>(pythonRequest, headers);
		ResponseEntity<PythonMetadataResponse> response = restTemplate.exchange(
				generateMetadataUrl,
				HttpMethod.POST,
				requestEntity,
				PythonMetadataResponse.class
		);
		
		PythonMetadataResponse metadataResponse = response.getBody();
		if (metadataResponse == null) {
			throw new RuntimeException("Python 서버로부터 메타데이터 응답을 받지 못했습니다.");
		}
		
		// Step 2: FloorPlan 엔티티 생성 및 저장 (3번 저장)
		FloorPlan floorPlan = FloorPlan.builder()
				.name(request.getName())
				.imageUrl(savedImagePath)  // 저장된 이미지 경로
				.assessmentJson(request.getAssessmentJson())  // 3번 저장
				.user(user)
				.createdAt(LocalDate.now())
				.build();

		FloorPlan savedPlan = floorPlanRepository.save(floorPlan);

		// Step 3: 4번 메타데이터를 파싱하여 FloorplanAnalysis 저장
		var metadata = metadataResponse.getMetadata();
		
		// double[] -> float[] 변환
		double[] embeddingDouble = metadataResponse.getEmbedding();
		float[] embeddingFloat = new float[embeddingDouble.length];
		for (int i = 0; i < embeddingDouble.length; i++) {
			embeddingFloat[i] = (float) embeddingDouble[i];
		}
		
		FloorplanAnalysis analysis = FloorplanAnalysis.builder()
				.floorPlan(savedPlan)
				.windowlessRatio(((Number) metadata.get("windowless_ratio")).doubleValue())
				.hasSpecialSpace((Boolean) metadata.get("has_special_space"))
				.bayCount(((Number) metadata.get("bay_count")).intValue())
				.balconyRatio(((Number) metadata.get("balcony_ratio")).doubleValue())
				.livingRoomRatio(((Number) metadata.get("living_room_ratio")).doubleValue())
				.bathroomRatio(((Number) metadata.get("bathroom_ratio")).doubleValue())
				.kitchenRatio(((Number) metadata.get("kitchen_ratio")).doubleValue())
				.roomCount(((Number) metadata.get("room_count")).intValue())
				.complianceGrade((String) metadata.get("compliance_grade"))
				.ventilationQuality((String) metadata.get("ventilation_quality"))
				.hasEtcSpace((Boolean) metadata.get("has_etc_space"))
				.structureType((String) metadata.get("structure_type"))
				.bathroomCount(((Number) metadata.get("bathroom_count")).intValue())
				.analysisDescription(metadataResponse.getDocument())
				.embedding(embeddingFloat)
				.build();

		FloorplanAnalysis savedAnalysis = summaryRepository.save(analysis);
		
		// Step 4: 저장 성공 응답 반환
		return FloorplanSaveResponse.builder()
				.floorplanId(savedPlan.getId())
				.analysisId(savedAnalysis.getId())
				.name(savedPlan.getName())
				.createdAt(savedPlan.getCreatedAt())
				.message("도면 분석 결과가 성공적으로 저장되었습니다.")
				.build();
	}
	
	/**
	 * 이미지 파일을 resources/image/floorplan/ 경로에 저장
	 * 파일명: userId_timestamp_originalFilename
	 */
	private String saveImageFile(MultipartFile file, Long userId) throws Exception {
		// 저장 디렉토리 경로 (절대 경로 사용)
		String uploadDir = System.getProperty("user.dir") + "/src/main/resources/image/floorplan/";
		java.io.File directory = new java.io.File(uploadDir);

		// 디렉토리가 없으면 생성
		if (!directory.exists()) {
			boolean created = directory.mkdirs();
			System.out.println("[FloorPlanService] 디렉토리 생성: " + uploadDir + " -> " + created);
		}

		// 고유한 파일명 생성 (userId_timestamp_originalFilename)
		String timestamp = String.valueOf(System.currentTimeMillis());
		String originalFilename = file.getOriginalFilename();
		String savedFilename = userId + "_" + timestamp + "_" + originalFilename;

		// 파일 저장
		String filePath = uploadDir + savedFilename;
		java.io.File destFile = new java.io.File(filePath);
		System.out.println("[FloorPlanService] 파일 저장 경로: " + destFile.getAbsolutePath());
		file.transferTo(destFile.getAbsoluteFile());

		// DB에 저장할 경로 반환 (상대 경로)
		return "/image/floorplan/" + savedFilename;
	}
}