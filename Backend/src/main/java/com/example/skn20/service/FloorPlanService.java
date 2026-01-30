package com.example.skn20.service;

import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.FloorplanSummary;
import com.example.skn20.entity.User;
import com.example.skn20.repository.FloorPlanRepository;
import com.example.skn20.repository.FloorplanSummaryRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class FloorPlanService {

	private final FloorPlanRepository floorPlanRepository;
	private final FloorplanSummaryRepository summaryRepository;
	private final ObjectMapper objectMapper;

	// 1. 분석 단계: 파이썬 호출 및 결과 반환 (위상그래프 이미지 포함)
	public Map<String, Object> analyzeWithPython(MultipartFile file) throws Exception {
		String pythonUrl = "http://localhost:8000/analyze";
		RestTemplate restTemplate = new RestTemplate();

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.MULTIPART_FORM_DATA);

		MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
		body.add("file", new ByteArrayResource(file.getBytes()) {
			@Override
			public String getFilename() {
				return file.getOriginalFilename();
			}
		});

		// 파이썬으로부터 { elementJson, topologyImage, eval, embedding } 등을 받음
		return restTemplate.postForObject(pythonUrl, new HttpEntity<>(body, headers), Map.class);
	}

	// 2. 저장 단계: 선택적 데이터 분산 저장 (위상그래프 이미지는 제외)
	@Transactional
	public void saveToDatabase(Map<String, Object> data, User user) throws Exception {

		// A. FloorPlan 저장 (도면 기본 정보 및 JSON)
		String elementJsonStr = objectMapper.writeValueAsString(data.get("elementJson"));

		FloorPlan floorPlan = FloorPlan.builder().name((String) data.getOrDefault("name", "신규 도면"))
				.imageUrl((String) data.get("imageUrl")).user(user) // 주입받은 유저 객체 사용
				.createdAt(LocalDate.now()).elementJson(elementJsonStr).build();

		FloorPlan savedPlan = floorPlanRepository.save(floorPlan);

		// B. FloorplanSummary 저장 (평가 내용 및 임베딩)
		float[] embeddingVector = extractEmbedding(data.get("embedding"));

		FloorplanSummary summary = FloorplanSummary.builder().floorPlan(savedPlan).eval((String) data.get("eval"))
				.embedding(embeddingVector).build();

		summaryRepository.save(summary);
	}

	private float[] extractEmbedding(Object obj) {
		if (obj instanceof List<?> list) {
			float[] vector = new float[list.size()];
			for (int i = 0; i < list.size(); i++) {
				vector[i] = ((Number) list.get(i)).floatValue();
			}
			return vector;
		}
		return null;
	}
}