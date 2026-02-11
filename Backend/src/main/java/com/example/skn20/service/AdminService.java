package com.example.skn20.service;

import com.example.skn20.dto.*;
import com.example.skn20.entity.*;
import com.example.skn20.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StreamUtils;

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AdminService {

    private final UserRepository userRepository;
    private final FloorPlanRepository floorPlanRepository;
    private final ChatRoomRepository chatRoomRepository;
    private final ChatHistoryRepository chatHistoryRepository;
    private final FloorplanAnalysisRepository floorplanAnalysisRepository;

    /**
     * 대시보드 통계 조회
     */
    public AdminStatsResponse getAdminStats() {
        Long userCount = userRepository.count();
        Long floorPlanCount = floorPlanRepository.count();
        LocalDate sevenDaysAgo = LocalDate.now().minusDays(7);
        Long recentFloorPlan = floorPlanRepository.countRecentFloorPlans(sevenDaysAgo);
        
        // 챗봇 통계
        Long totalChatCount = chatHistoryRepository.count();
        LocalDateTime sevenDaysAgoDateTime = LocalDateTime.now().minusDays(7);
        Long recentChatCount = chatHistoryRepository.countRecentChats(sevenDaysAgoDateTime);
        Long chatRoomCount = chatRoomRepository.count();

        return AdminStatsResponse.builder()
                .userCount(userCount)
                .floorPlanCount(floorPlanCount)
                .recentFloorPlan(recentFloorPlan)
                .totalChatCount(totalChatCount)
                .recentChatCount(recentChatCount)
                .chatRoomCount(chatRoomCount)
                .build();
    }

    /**
     * 활동 로그 조회 (회원가입 + 도면 업로드 + 챗봇 대화 내역)
     */
    public List<ActivityLogResponse> getActivityLogs() {
        List<ActivityLogResponse> logs = new ArrayList<>();

        // 회원가입 활동
        List<User> users = userRepository.findAll();
        for (User user : users) {
            if (user.getCreate_at() != null) {
                logs.add(ActivityLogResponse.builder()
                        .id(user.getId())
                        .type("USER")
                        .userName(user.getName())
                        .userEmail(user.getEmail())
                        .action("회원가입")
                        .details(user.getRole() + " 계정 생성")
                        .createdAt(user.getCreate_at())
                        .build());
            }
        }

        // 도면 업로드 활동
        List<FloorPlan> floorPlans = floorPlanRepository.findAll();
        for (FloorPlan fp : floorPlans) {
            logs.add(ActivityLogResponse.builder()
                    .id(fp.getId())
                    .type("FLOORPLAN")
                    .userName(fp.getUser().getName())
                    .userEmail(fp.getUser().getEmail())
                    .action("도면 업로드")
                    .details(fp.getName() != null ? fp.getName() : "제목 없음")
                    .createdAt(fp.getCreatedAt())
                    .build());
        }

        // 챗봇 대화 활동 (ChatHistory 단위)
        List<ChatHistory> chatHistories = chatHistoryRepository.findAll();
        for (ChatHistory ch : chatHistories) {
            String question = ch.getQuestion();
            String preview = (question != null && question.length() > 50) 
                ? question.substring(0, 50) + "..." 
                : (question != null ? question : "질문 없음");
            
            logs.add(ActivityLogResponse.builder()
                    .id(ch.getId())
                    .type("CHAT")
                    .userName(ch.getChatRoom().getUser().getName())
                    .userEmail(ch.getChatRoom().getUser().getEmail())
                    .action("챗봇 질문")
                    .details("[" + ch.getChatRoom().getName() + "] " + preview)
                    .createdAt(ch.getCreatedAt().toLocalDate())
                    .build());
        }

        // 날짜 역순 정렬 (최신순)
        logs.sort(Comparator.comparing(ActivityLogResponse::getCreatedAt).reversed());
        return logs;
    }

    /**
     * 챗봇 대화 상세 조회
     */
    public ChatHistoryDetailResponse getChatHistoryDetail(Long chatHistoryId) {
        ChatHistory ch = chatHistoryRepository.findById(chatHistoryId)
                .orElseThrow(() -> new RuntimeException("대화 내역을 찾을 수 없습니다."));
        
        return ChatHistoryDetailResponse.builder()
                .id(ch.getId())
                .chatRoomName(ch.getChatRoom().getName())
                .userName(ch.getChatRoom().getUser().getName())
                .userEmail(ch.getChatRoom().getUser().getEmail())
                .question(ch.getQuestion())
                .answer(ch.getAnswer())
                .createdAt(ch.getCreatedAt())
                .build();
    }

    /**
     * 전체 도면 목록 조회
     */
    public List<AdminFloorPlanResponse> getAllFloorPlans() {
        List<FloorPlan> floorPlans = floorPlanRepository.findAll();
        return floorPlans.stream()
                .map(this::convertToAdminFloorPlanResponse)
                .collect(Collectors.toList());
    }

    /**
     * 도면 검색 (다양한 조건)
     */
    public List<AdminFloorPlanResponse> searchFloorPlans(
            String name,
            String uploaderEmail,
            LocalDate startDate,
            LocalDate endDate,
            Integer minRooms,
            Integer maxRooms) {
        
        List<FloorPlan> floorPlans = floorPlanRepository.findAll();

        // 필터링
        return floorPlans.stream()
                .filter(fp -> {
                    // 이름 검색
                    if (name != null && !name.isEmpty()) {
                        if (fp.getName() == null || !fp.getName().contains(name)) {
                            return false;
                        }
                    }
                    // 업로더 이메일 검색
                    if (uploaderEmail != null && !uploaderEmail.isEmpty()) {
                        if (!fp.getUser().getEmail().contains(uploaderEmail)) {
                            return false;
                        }
                    }
                    // 날짜 범위
                    if (startDate != null && fp.getCreatedAt().isBefore(startDate)) {
                        return false;
                    }
                    if (endDate != null && fp.getCreatedAt().isAfter(endDate)) {
                        return false;
                    }
                    // 방 개수 필터
                    if (minRooms != null || maxRooms != null) {
                        FloorplanAnalysis analysis = floorplanAnalysisRepository.findByFloorPlanId(fp.getId()).orElse(null);
                        if (analysis == null || analysis.getRoomCount() == null) {
                            return false;
                        }
                        if (minRooms != null && analysis.getRoomCount() < minRooms) {
                            return false;
                        }
                        if (maxRooms != null && analysis.getRoomCount() > maxRooms) {
                            return false;
                        }
                    }
                    return true;
                })
                .map(this::convertToAdminFloorPlanResponse)
                .collect(Collectors.toList());
    }

    /**
     * 도면 삭제
     */
    @Transactional
    public String deleteFloorPlans(List<Long> ids) {
        for (Long id : ids) {
            if (floorPlanRepository.existsById(id)) {
                floorPlanRepository.deleteById(id);
            }
        }
        return ids.size() + "개의 도면이 삭제되었습니다.";
    }

    /**
     * 도면 상세 조회
     */
    public AdminFloorPlanResponse getFloorPlanDetail(Long floorplanid) {
        FloorPlan fp = floorPlanRepository.findById(floorplanid)
                .orElseThrow(() -> new RuntimeException("도면을 찾을 수 없습니다."));
        return convertToAdminFloorPlanResponse(fp);
    }

    /**
     * 도면 이미지 파일 로드
     */
    public byte[] getFloorPlanImage(Long floorplanid) throws IOException {
        FloorPlan fp = floorPlanRepository.findById(floorplanid)
                .orElseThrow(() -> new RuntimeException("도면을 찾을 수 없습니다."));
        
        String imageUrl = fp.getImageUrl();
        if (imageUrl == null || imageUrl.isEmpty()) {
            throw new RuntimeException("이미지 URL이 없습니다.");
        }
        
        // /image/floorplan/xxx.png 형식에서 image/floorplan/xxx.png로 변환
        String resourcePath = imageUrl.startsWith("/") ? imageUrl.substring(1) : imageUrl;
        
        ClassPathResource resource = new ClassPathResource(resourcePath);
        if (!resource.exists()) {
            throw new RuntimeException("이미지 파일을 찾을 수 없습니다: " + resourcePath);
        }
        
        try (InputStream inputStream = resource.getInputStream()) {
            return StreamUtils.copyToByteArray(inputStream);
        }
    }

    /**
     * FloorPlan -> AdminFloorPlanResponse 변환
     */
    private AdminFloorPlanResponse convertToAdminFloorPlanResponse(FloorPlan fp) {
        FloorplanAnalysis analysis = floorplanAnalysisRepository.findByFloorPlanId(fp.getId()).orElse(null);
        Integer roomCount = (analysis != null) ? analysis.getRoomCount() : null;

        return AdminFloorPlanResponse.builder()
                .id(fp.getId())
                .name(fp.getName())
                .imageUrl(fp.getImageUrl())
                .user(AdminFloorPlanResponse.UserSimpleDto.builder()
                        .id(fp.getUser().getId())
                        .email(fp.getUser().getEmail())
                        .name(fp.getUser().getName())
                        .role(fp.getUser().getRole())
                        .build())
                .createdAt(fp.getCreatedAt())
                .roomCount(roomCount)
                .build();
    }
}
