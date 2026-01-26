package com.example.skn20.service;

import java.util.HashMap;
import java.util.Map;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.client.RestTemplate;

import com.example.skn20.entity.User;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000" })
public class ChatbotService {
    
    // 요약제목과 답변을 Map으로 반환
    public Map<String, String> question2answer(User user, String question) {
        return fastapiCommunicate(user, question);
    }

    // FastAPI 통신 후 요약제목과 답변을 Map으로 반환
    private Map<String, String> fastapiCommunicate(User user, String question) {
        Map<String, String> result = new HashMap<>();
        try {
            RestTemplate restTemplate = new RestTemplate();
            String url = "http://localhost:8000/chatllm"; // FastAPI 엔드포인트 주소

            Map<String, Object> request = new HashMap<>();
            request.put("email", user.getEmail());
            request.put("question", question);

            HttpHeaders headers = new HttpHeaders();
            headers.set("Content-Type", "application/json");
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            String responseBody = response.getBody();

            ObjectMapper mapper = new ObjectMapper();
            JsonNode node = mapper.readTree(responseBody);
            // FastAPI에서 summaryTitle, answer로 응답한다고 가정
            result.put("summaryTitle", node.has("summaryTitle") ? node.get("summaryTitle").asText() : "");
            result.put("answer", node.has("answer") ? node.get("answer").asText() : "");
        } catch (Exception e) {
            result.put("summaryTitle", "");
            result.put("answer", "FastAPI 서버 통신 오류: " + e.getMessage());
        }
        return result;
    }
}
