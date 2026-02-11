package com.example.skn20.controller;

import com.example.skn20.dto.*;
import com.example.skn20.service.AdminService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:5173" })
public class AdminController {

    private final AdminService adminService;

    /**
     * 대시보드 통계 조회
     * GET /api/admin/stats
     */
    @GetMapping("/stats")
    public ResponseEntity<AdminStatsResponse> getAdminStats() {
        AdminStatsResponse stats = adminService.getAdminStats();
        return ResponseEntity.ok(stats);
    }

    /**
     * 활동 로그 조회 (도면 + 챗봇)
     * GET /api/admin/logs
     */
    @GetMapping("/logs")
    public ResponseEntity<List<ActivityLogResponse>> getActivityLogs() {
        List<ActivityLogResponse> logs = adminService.getActivityLogs();
        return ResponseEntity.ok(logs);
    }

    /**
     * 챗봇 대화 상세 조회
     * GET /api/admin/chathistory/{id}
     */
    @GetMapping("/chathistory/{id}")
    public ResponseEntity<ChatHistoryDetailResponse> getChatHistoryDetail(@PathVariable Long id) {
        ChatHistoryDetailResponse detail = adminService.getChatHistoryDetail(id);
        return ResponseEntity.ok(detail);
    }

    /**
     * 전체 도면 목록 조회
     * GET /api/admin/floorplans
     */
    @GetMapping("/floorplans")
    public ResponseEntity<List<AdminFloorPlanResponse>> getAllFloorPlans() {
        List<AdminFloorPlanResponse> floorPlans = adminService.getAllFloorPlans();
        return ResponseEntity.ok(floorPlans);
    }

    /**
     * 도면 검색
     * POST /api/admin/searchfloorplan 
     */
    @PostMapping("/searchfloorplan")
    public ResponseEntity<List<AdminFloorPlanResponse>> searchFloorPlans(
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String uploaderEmail,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false) Integer minRooms,
            @RequestParam(required = false) Integer maxRooms) {
        
        LocalDate start = (startDate != null && !startDate.isEmpty()) ? LocalDate.parse(startDate) : null;
        LocalDate end = (endDate != null && !endDate.isEmpty()) ? LocalDate.parse(endDate) : null;
        
        List<AdminFloorPlanResponse> floorPlans = adminService.searchFloorPlans(
            name, uploaderEmail, start, end, minRooms, maxRooms);
        return ResponseEntity.ok(floorPlans);
    }

    /**
     * 도면 상세 조회
     * POST /api/admin/floorplandetail?floorplanid=1
     */
    @PostMapping("/floorplandetail")
    public ResponseEntity<AdminFloorPlanResponse> getFloorPlanDetail(
            @RequestParam Long floorplanid) {
        AdminFloorPlanResponse floorPlan = adminService.getFloorPlanDetail(floorplanid);
        return ResponseEntity.ok(floorPlan);
    }

    /**
     * 도면 이미지 반환
     * GET /api/admin/floorplan/{id}/image
     */
    @GetMapping("/floorplan/{id}/image")
    public ResponseEntity<byte[]> getFloorPlanImage(@PathVariable Long id) {
        try {
            byte[] imageBytes = adminService.getFloorPlanImage(id);
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.IMAGE_PNG);
            return new ResponseEntity<>(imageBytes, headers, HttpStatus.OK);
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * 도면 삭제 (일괄 삭제 지원)
     * POST /api/admin/deleteentities?type=floorplan
     * Body: [1, 2, 3]
     */
    @PostMapping("/deleteentities")
    public ResponseEntity<String> deleteEntities(
            @RequestParam String type,
            @RequestBody List<Long> ids) {
        
        if ("floorplan".equalsIgnoreCase(type)) {
            String result = adminService.deleteFloorPlans(ids);
            return ResponseEntity.ok(result);
        }
        
        return ResponseEntity.badRequest().body("지원하지 않는 타입입니다.");
    }
}
