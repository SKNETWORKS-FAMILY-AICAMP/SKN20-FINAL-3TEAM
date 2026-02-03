package com.example.skn20.service;

import java.util.HashMap;
import java.util.Map;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.example.skn20.entity.User;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatbotService {
    
    // RestTemplate은 보통 Config 클래스에서 Bean으로 등록 후 주입받는 것이 정석입니다.
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;
    private final String FASTAPI_URL = "http://localhost:8000/ask";

    public Map<String, String> question2answer(User user, String question) {
        return fastapiCommunicate(user, question);
    }

    private Map<String, String> fastapiCommunicate(User user, String question) {
        Map<String, String> result = new HashMap<>();
        
        try {
            // 1. 요청 데이터 구성
            Map<String, Object> requestMap = new HashMap<>();
            // user가 null이면 "anonymous" 사용
            requestMap.put("email", user != null ? user.getEmail() : "anonymous");
            requestMap.put("question", question);

            // 2. 헤더 설정
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestMap, headers);

            // 3. FastAPI 호출
            log.info("FastAPI 호출 중... URL: {}, Question: {}", FASTAPI_URL, question);
            ResponseEntity<String> response = restTemplate.postForEntity(FASTAPI_URL, entity, String.class);
            
            // 4. 응답 파싱
            JsonNode node = objectMapper.readTree(response.getBody());
            
            result.put("summaryTitle", node.path("summaryTitle").asText("제목 없음"));
            result.put("answer", node.path("answer").asText("답변을 생성할 수 없습니다."));
            
            log.info("FastAPI 응답 완료: {}", result.get("summaryTitle"));

        } catch (Exception e) {
            log.error("FastAPI 통신 중 에러 발생: {}", e.getMessage());
            result.put("summaryTitle", "에러 발생");
            result.put("answer", "서버 통신 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
        }
        
        return result;
    }
}