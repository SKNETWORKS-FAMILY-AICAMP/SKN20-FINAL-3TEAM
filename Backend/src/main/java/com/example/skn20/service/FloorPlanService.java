package com.example.skn20.service;

import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class FloorPlanService {

	// FastAPI 서버 URL (예시)
	private final String FASTAPI_URL = "http://localhost:8000/analyze";

	// 도면 이미지 경로를 받아 FastAPI로 분석 요청
	public String analyzeFloorPlan(String imagePath) throws Exception {
		// RestTemplate 또는 WebClient 사용 가능 (여기선 RestTemplate 예시)
		RestTemplate restTemplate = new RestTemplate();

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.MULTIPART_FORM_DATA);

		FileSystemResource fileResource = new FileSystemResource(imagePath);
		MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
		body.add("file", fileResource);

		HttpEntity<MultiValueMap<String, Object>> requestEntity =
				new HttpEntity<>(body, headers);

		// FastAPI로 POST 요청
		ResponseEntity<String> response = restTemplate.postForEntity(
				FASTAPI_URL, requestEntity, String.class);

		return response.getBody();
	}
	// 도면 분석 결과(JSON 등) 저장
	public void saveFloorPlanData(String floorPlanData) throws Exception {
		// TODO: floorPlanData(JSON 등)를 파싱하여 DB에 저장하는 로직 구현
		// 예시: System.out.println("저장할 데이터: " + floorPlanData);
	}
}
