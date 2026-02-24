package com.example.skn20.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.User;
import com.example.skn20.repository.FloorPlanRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatbotService {

	private final RestTemplate restTemplate;
	private final ObjectMapper objectMapper;
	private final FloorPlanRepository floorPlanRepository;

	// 변경: /ask → /orchestrate
	private final String FASTAPI_ORCHESTRATE_URL = "http://localhost:8000/orchestrate";

//텍스트 전용 (기존 호환)

	public Map<String, Object> question2answer(User user, String question) {
		return orchestrate(user, question, null);
	}

//텍스트 + 이미지
	public Map<String, Object> question2answerWithImage(User user, String question, MultipartFile image) {
		return orchestrate(user, question, image);
	}

	private Map<String, Object> orchestrate(User user, String question, MultipartFile image) {

		Map<String, Object> result = new HashMap<>();

		try {
			// 1. 헤더 설정 (multipart/form-data)
			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(MediaType.MULTIPART_FORM_DATA);

			// 2. Form 데이터 구성
			MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
			body.add("email", user != null ? user.getEmail() : "anonymous");
			body.add("question", question != null ? question : "");

			// 3. 이미지가 있으면 file 필드 추가
			if (image != null && !image.isEmpty()) {
				body.add("file", new ByteArrayResource(image.getBytes()) {
					@Override
					public String getFilename() {
						return image.getOriginalFilename();
					}
				});
			}

			// 4. Python /orchestrate 호출
			HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

			log.info("Python /orchestrate 호출 - question: {}, hasImage: {}", question, image != null);

			ResponseEntity<String> response = restTemplate.postForEntity(FASTAPI_ORCHESTRATE_URL, requestEntity,
					String.class);

			// 5. 응답 파싱 (중첩 JSON에서 response.answer, response.summaryTitle 추출)
			JsonNode root = objectMapper.readTree(response.getBody());
			JsonNode responseNode = root.path("response");

			result.put("summaryTitle", responseNode.path("summaryTitle").asText("도면 분석 결과"));
			result.put("answer", responseNode.path("answer").asText("답변을 생성할 수 없습니다."));
			
			// 6. floorplan_ids가 있으면 DB에서 S3 URL 직접 조회
			JsonNode floorplanIdsNode = responseNode.path("floorplan_ids");
			if (!floorplanIdsNode.isMissingNode() && floorplanIdsNode.isArray()) {
				List<Long> floorplanIds = new java.util.ArrayList<>();
				floorplanIdsNode.forEach(node -> floorplanIds.add(node.asLong()));

				if (!floorplanIds.isEmpty()) {
					List<String> imageS3Urls = floorplanIds.stream()
							.map(id -> floorPlanRepository.findById(id)
									.map(FloorPlan::getImageUrl)
									.orElse(null))
							.filter(url -> url != null && !url.isEmpty())
							.collect(Collectors.toList());

					result.put("image_urls", imageS3Urls);
					log.info("조회된 도면 S3 이미지 URL 개수: {}", imageS3Urls.size());
				}
			}
			
			log.info("Python /orchestrate 응답 완료 - intent: {}, agent: {}", root.path("intent_type").asText(),
					root.path("agent_used").asText());

		} catch (Exception e) {
			log.error("Python /orchestrate 통신 오류: {}", e.getMessage());
			result.put("summaryTitle", "에러 발생");
			result.put("answer", "서버 통신 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
		}

		return result;
	}
}