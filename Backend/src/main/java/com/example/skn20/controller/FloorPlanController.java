package com.example.skn20.controller;

import java.io.File;
import java.nio.file.Files;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.example.skn20.entity.FloorPlan;
import com.example.skn20.service.FloorPlanService;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@RestController
@RequestMapping("/api/floorplan")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000" })
public class FloorPlanController {

	private final FloorPlanService floorPlanService;

	@PostMapping("/analyze")
	public ResponseEntity<?> analyze(@RequestParam("file") MultipartFile file) {
		if (file.isEmpty())
			return ResponseEntity.badRequest().body("파일이 없습니다.");

		try {
			// 분석 결과를 바로 DTO 형태로 프론트에 전달
			FloorPlan result = floorPlanService.analyzeFloorPlan(file);
			return ResponseEntity.ok(result);
		} catch (Exception e) {
			return ResponseEntity.status(500).body("FastAPI 분석 요청 중 오류 발생: " + e.getMessage());
		}
	}

	@PostMapping("/save")
	public ResponseEntity<?> saveFloorPlan(@RequestBody FloorPlan finalData) {
		try {
			floorPlanService.saveFloorPlanData(finalData);
			return ResponseEntity.ok("엔티티에 데이터 저장 완료!");
		} catch (Exception e) {
			return ResponseEntity.status(500).body("저장 실패: " + e.getMessage());
		}
	}
}
