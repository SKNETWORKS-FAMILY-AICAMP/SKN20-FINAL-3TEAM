package com.example.skn20.service;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import com.example.skn20.entity.FloorPlan;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class FloorPlanService {

	private final String FASTAPI_URL = "http://localhost:8000/analyze";
	private final RestTemplate restTemplate = new RestTemplate();

	public FloorPlan analyzeFloorPlan(MultipartFile file) throws Exception {
		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.MULTIPART_FORM_DATA);

		// 메모리 효율을 위해 ByteArrayResource 사용 (파일 생성/삭제 생략 가능)
		MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
		body.add("file", new ByteArrayResource(file.getBytes()) {
			@Override
			public String getFilename() {
				return file.getOriginalFilename();
			}
		});

		HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

		// String 대신 DTO(FloorPlanResponse)로 직접 매핑하여 반환
		return restTemplate.postForObject(FASTAPI_URL, requestEntity, FloorPlanResponse.class);
	}

	@Transactional
	public void saveFloorPlanData(FloorPlan dto) {
		// DTO 데이터를 기존 엔티티(FloorPlanEntity)에 매핑
		// 엔티티 구조에 따라 builder나 생성자를 사용하세요.
		FloorPlan entity = FloorPlan.builder().rawData(dto.rawData().toString()) // 객체를 String이나 JSON으로 변환
				.summary(dto.summary())
				// 위상 그래프나 평가 결과도 엔티티 필드에 맞게 세팅
				.build();

		floorPlanRepository.save(entity);
	}
}
