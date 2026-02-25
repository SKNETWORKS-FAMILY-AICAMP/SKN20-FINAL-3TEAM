package com.example.skn20.controller;

import com.example.skn20.dto.*;
import com.example.skn20.service.AdminService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
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
     * 활동 로그 조회 - 서버 사이드 페이징 + 필터링
     * GET /api/admin/logs?page=0&size=8&type=USER&search=...&startDate=...&endDate=...
     */
    @GetMapping("/logs")
    public ResponseEntity<PageResponse<ActivityLogResponse>> getActivityLogs(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "8") int size,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate) {

        LocalDate start = (startDate != null && !startDate.isEmpty()) ? LocalDate.parse(startDate) : null;
        LocalDate end = (endDate != null && !endDate.isEmpty()) ? LocalDate.parse(endDate) : null;

        PageResponse<ActivityLogResponse> logs = adminService.getActivityLogsPaged(page, size, type, search, start, end);
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
     * 전체 도면 목록 조회 - 서버 사이드 페이징
     * GET /api/admin/floorplans?page=0&size=8
     */
    @GetMapping("/floorplans")
    public ResponseEntity<PageResponse<AdminFloorPlanResponse>> getAllFloorPlans(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "8") int size) {
        PageResponse<AdminFloorPlanResponse> floorPlans = adminService.getAllFloorPlansPaged(page, size);
        return ResponseEntity.ok(floorPlans);
    }

    /**
     * 도면 검색 - 서버 사이드 페이징 + 필터링
     * POST /api/admin/searchfloorplan?page=0&size=8&name=...
     */
    @PostMapping("/searchfloorplan")
    public ResponseEntity<PageResponse<AdminFloorPlanResponse>> searchFloorPlans(
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String uploaderEmail,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false) Integer minRooms,
            @RequestParam(required = false) Integer maxRooms,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "8") int size) {

        LocalDate start = (startDate != null && !startDate.isEmpty()) ? LocalDate.parse(startDate) : null;
        LocalDate end = (endDate != null && !endDate.isEmpty()) ? LocalDate.parse(endDate) : null;

        PageResponse<AdminFloorPlanResponse> floorPlans = adminService.searchFloorPlansPaged(
            name, uploaderEmail, start, end, minRooms, maxRooms, page, size);
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
     * 도면 이미지 반환 → S3 URL로 리다이렉트
     * GET /api/admin/floorplan/{id}/image
     */
    @GetMapping("/floorplan/{id}/image")
    public ResponseEntity<?> getFloorPlanImage(@PathVariable Long id) {
        try {
            String imageUrl = adminService.getFloorPlanImageUrl(id);
            return ResponseEntity.status(HttpStatus.FOUND)
                    .header(HttpHeaders.LOCATION, imageUrl)
                    .build();
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
