package com.example.skn20.controller;

import com.example.skn20.classes.UD;
import com.example.skn20.dto.FloorplanPreviewResponse;
import com.example.skn20.dto.FloorplanSaveRequest;
import com.example.skn20.dto.FloorplanSaveResponse;
import com.example.skn20.dto.MyFloorPlanResponse;
import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.User;
import com.example.skn20.service.FloorPlanService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

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
			e.printStackTrace();
			return ResponseEntity.status(500).body("분석 중 오류 발생: " + e.getMessage());
		}
	}

	/**
	 * [Step 2] 최종 저장: 프론트에서 "저장" 버튼 클릭 시 DB에 저장
	 * 이미지 파일과 3번 JSON을 받아 Python으로 전송 후 DB 저장
	 */
	@PostMapping("/save")
	public ResponseEntity<?> saveFloorplan(
			@RequestParam("file") MultipartFile file,
			@RequestParam("name") String name,
			@RequestParam("assessmentJson") String assessmentJson,
			@AuthenticationPrincipal UD principalDetails
	) {
		try {
			// 인증된 유저 정보 추출
			User user = principalDetails.getUser();

			// DTO 생성
			FloorplanSaveRequest saveRequest = new FloorplanSaveRequest();
			saveRequest.setName(name);
			saveRequest.setAssessmentJson(assessmentJson);

			// 서비스 호출하여 이미지 저장 및 DB에 저장
			FloorplanSaveResponse response = floorPlanService.saveFloorplan(saveRequest, file, user);

			return ResponseEntity.ok(response);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("저장 중 오류 발생: " + e.getMessage());
		}
	}

	/**
	 * [Step 3] 내 도면 분석 내역 조회
	 */
	@GetMapping("/my")
	public ResponseEntity<?> getMyFloorPlans(@AuthenticationPrincipal UD principalDetails) {
		if (principalDetails == null) {
			return ResponseEntity.status(401).body("인증이 필요합니다.");
		}
		try {
			User user = principalDetails.getUser();
			List<MyFloorPlanResponse> list = floorPlanService.getMyFloorPlans(user.getId());
			return ResponseEntity.ok(list);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("도면 내역 조회 실패: " + e.getMessage());
		}
	}

	/**
	 * [Step 4] 도면 상세 조회 (본인 도면만)
	 */
	@GetMapping("/{id}/detail")
	public ResponseEntity<?> getFloorPlanDetail(
			@PathVariable Long id,
			@AuthenticationPrincipal UD principalDetails
	) {
		if (principalDetails == null) {
			return ResponseEntity.status(401).body("인증이 필요합니다.");
		}
		try {
			User user = principalDetails.getUser();
			FloorPlan fp = floorPlanService.getFloorPlanDetail(id, user.getId());
			Map<String, Object> result = new HashMap<>();
			result.put("id", fp.getId());
			result.put("name", fp.getName());
			result.put("createdAt", fp.getCreatedAt());
			result.put("imageUrl", "/api/floorplan/" + fp.getId() + "/image");
			result.put("assessmentJson", fp.getAssessmentJson());
			return ResponseEntity.ok(result);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("도면 상세 조회 실패: " + e.getMessage());
		}
	}

	/**
	 * [Step 5] 도면 이미지 반환 (본인 도면만)
	 */
	@GetMapping("/{id}/image")
	public ResponseEntity<?> getFloorPlanImage(
			@PathVariable Long id,
			@AuthenticationPrincipal UD principalDetails
	) {
		if (principalDetails == null) {
			return ResponseEntity.status(401).body("인증이 필요합니다.");
		}
		try {
			User user = principalDetails.getUser();
			byte[] imageBytes = floorPlanService.getFloorPlanImage(id, user.getId());
			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(MediaType.IMAGE_PNG);
			return new ResponseEntity<>(imageBytes, headers, HttpStatus.OK);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("이미지 조회 실패: " + e.getMessage());
		}
	}
}