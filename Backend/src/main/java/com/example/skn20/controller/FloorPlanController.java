package com.example.skn20.controller;

import com.example.skn20.classes.UD;
import com.example.skn20.dto.FloorplanPreviewResponse;
import com.example.skn20.dto.FloorplanSaveRequest;
import com.example.skn20.dto.FloorplanSaveResponse;
import com.example.skn20.entity.User;
import com.example.skn20.service.FloorPlanService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/floorplan")
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:3000")
public class FloorPlanController {

	private final FloorPlanService floorPlanService;

	/**
	 * [Step 1] 도면 분석: 프론트 이미지 -> Python 서버 -> 분석결과 반환
	 * DB에 저장하지 않고 프리뷰 데이터만 반환
	 */
	@PostMapping("/analyze")
	public ResponseEntity<?> analyzeFloorplan(@RequestParam("file") MultipartFile file) {
		try {
			// Python 서버 호출 및 분석 결과 반환 (DB 저장 없음)
			FloorplanPreviewResponse preview = floorPlanService.analyzeFloorplan(file);
			return ResponseEntity.ok(preview);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("분석 중 오류 발생: " + e.getMessage());
		}
	}

	/**
	 * [Step 2] 최종 저장: 프론트에서 "저장" 버튼 클릭 시 DB에 저장
	 * 프리뷰 단계에서 받았던 모든 데이터를 다시 전달받아 저장
	 */
	@PostMapping("/save")
	public ResponseEntity<?> saveFloorplan(
			@RequestBody FloorplanSaveRequest saveRequest,
			@AuthenticationPrincipal UD principalDetails
	) {
		try {
			// 인증된 유저 정보 추출
			User user = principalDetails.getUser();

			// 서비스 호출하여 DB에 저장
			FloorplanSaveResponse response = floorPlanService.saveFloorplan(saveRequest, user);

			return ResponseEntity.ok(response);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("저장 중 오류 발생: " + e.getMessage());
		}
	}
}