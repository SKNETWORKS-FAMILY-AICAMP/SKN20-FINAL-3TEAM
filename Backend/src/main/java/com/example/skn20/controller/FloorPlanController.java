package com.example.skn20.controller;

import com.example.skn20.classes.UD;
import com.example.skn20.entity.User;
import com.example.skn20.service.FloorPlanService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/floorplan")
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:3000")
public class FloorPlanController {

	private final FloorPlanService floorPlanService;

	// [Step 1] 도면 분석: 프론트 이미지 -> 파이썬 -> 분석결과 반환
	@PostMapping("/analyze")
	public ResponseEntity<?> analyze(@RequestParam("file") MultipartFile file) {
		try {
			// 파이썬 서버 호출 및 결과(JSON, 그래프이미지, 평가, 임베딩) 반환
			Map<String, Object> result = floorPlanService.analyzeWithPython(file);
			return ResponseEntity.ok(result);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("분석 중 오류 발생: " + e.getMessage());
		}
	}

// [Step 2] 최종 저장: 유저 승인 후 데이터 분산 저장
	@PostMapping("/save")
	public ResponseEntity<?> save(@RequestBody Map<String, Object> saveRequest,
			@AuthenticationPrincipal UD principalDetails // 인증된 유저 정보 주입
	) {
		try {
			// 1. Principal에서 유저 엔티티 또는 ID 추출
			User user = principalDetails.getUser();

			// 2. 서비스 호출 시 유저 정보를 같이 넘겨줌
			floorPlanService.saveToDatabase(saveRequest, user);

			return ResponseEntity.ok("성공적으로 저장되었습니다.");
		} catch (Exception e) {
			return ResponseEntity.status(500).body("저장 중 오류 발생: " + e.getMessage());
		}
	}
}