package com.example.skn20.service;

import com.example.skn20.dto.FloorplanPreviewResponse;
import com.example.skn20.dto.FloorplanSaveRequest;
import com.example.skn20.dto.FloorplanSaveResponse;
import com.example.skn20.dto.PythonAnalysisResponse;
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
	 * 프론트에서 이미지를 받아 Python 서버로 전송하고, 분석 결과를 프리뷰 형태로 즉시 반환
	 */
	public FloorplanPreviewResponse analyzeFloorplan(MultipartFile file) throws Exception {
		String analyzeUrl = pythonServerUrl + "/analyze";

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

		return FloorplanPreviewResponse.builder()
				.topologyJson(pythonResponse.getTopologyJson())
				.topologyImageUrl(pythonResponse.getTopologyImageUrl())
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
	}

	/**
	 * 2. 저장 단계: 프론트에서 "저장" 버튼 클릭 시 DB에 저장
	 * 프리뷰 단계에서 받았던 모든 데이터를 다시 받아서 FloorPlan과 FloorplanAnalysis에 저장
	 * @Transactional로 모든 작업을 하나의 트랜잭션으로 관리
	 */
	@Transactional
	public FloorplanSaveResponse saveFloorplan(FloorplanSaveRequest request, User user) {
		// A. FloorPlan 엔티티 먼저 생성하여 저장
		FloorPlan floorPlan = FloorPlan.builder()
				.name(request.getName())
				.imageUrl(request.getImageUrl())
				.topologyJson(request.getTopologyJson())
				.topologyImageUrl(request.getTopologyImageUrl())
				.user(user)
				.createdAt(LocalDate.now())
				.build();

		// FloorPlan을 먼저 저장하여 ID 생성
		FloorPlan savedPlan = floorPlanRepository.save(floorPlan);

		// B. 저장된 FloorPlan의 ID를 사용하여 FloorplanAnalysis 개별 컬럼에 매핑하여 저장
		FloorplanAnalysis analysis = FloorplanAnalysis.builder()
				.floorPlan(savedPlan)
				.windowlessRatio(request.getWindowlessRatio())
				.hasSpecialSpace(request.getHasSpecialSpace())
				.bayCount(request.getBayCount())
				.balconyRatio(request.getBalconyRatio())
				.livingRoomRatio(request.getLivingRoomRatio())
				.bathroomRatio(request.getBathroomRatio())
				.kitchenRatio(request.getKitchenRatio())
				.roomCount(request.getRoomCount())
				.complianceGrade(request.getComplianceGrade())
				.ventilationQuality(request.getVentilationQuality())
				.hasEtcSpace(request.getHasEtcSpace())
				.structureType(request.getStructureType())
				.bathroomCount(request.getBathroomCount())
				.analysisDescription(request.getAnalysisDescription())
				.embedding(request.getEmbedding())
				.build();

		FloorplanAnalysis savedAnalysis = summaryRepository.save(analysis);
		
		// C. 저장 성공 응답 반환
		return FloorplanSaveResponse.builder()
				.floorplanId(savedPlan.getId())
				.analysisId(savedAnalysis.getId())
				.name(savedPlan.getName())
				.createdAt(savedPlan.getCreatedAt())
				.message("도면 분석 결과가 성공적으로 저장되었습니다.")
				.build();
	}
}