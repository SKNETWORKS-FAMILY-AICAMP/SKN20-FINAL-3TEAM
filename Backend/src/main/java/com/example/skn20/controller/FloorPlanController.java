package com.example.skn20.controller;

import java.io.File;
import java.nio.file.Files;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.example.skn20.service.FloorPlanService;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;


@RestController
@RequestMapping("/api/floorplan")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000" })
public class FloorPlanController {
	
	private final FloorPlanService floorPlanService;
	
    // 도면 이미지 업로드 및 FastAPI 분석 결과 반환
    @PostMapping("/imgupload")
    public ResponseEntity<?> imageUpload(@RequestParam("file") MultipartFile file) {
        try {
            // 1. 파일 임시 저장 (예: /tmp 또는 지정 경로)
            String tempPath = Files.createTempFile("floorplan_", file.getOriginalFilename()).toString();
            file.transferTo(new File(tempPath));

            // 2. FastAPI 서비스 호출 (분석 결과 받기)
            String analysisResult = floorPlanService.analyzeFloorPlan(tempPath);

            // 3. 임시 파일 삭제
            new File(tempPath).delete();

            // 4. 결과 반환
            return ResponseEntity.ok(analysisResult);
        } catch (Exception e) {
            return ResponseEntity.status(500).body("분석 실패: " + e.getMessage());
        }
    }
    
    // 도면 분석 결과(예: JSON) 저장
    @PostMapping("/save")
    public ResponseEntity<?> saveFloorPlan(@RequestParam("data") String floorPlanData) {
        try {
            floorPlanService.saveFloorPlanData(floorPlanData);
            return ResponseEntity.ok("저장 완료");
        } catch (Exception e) {
            return ResponseEntity.status(500).body("저장 실패: " + e.getMessage());
        }
    }
}
