package com.example.skn20.service;

import com.example.skn20.dto.*;
import com.example.skn20.entity.*;
import com.example.skn20.repository.*;
import com.example.skn20.specification.FloorPlanSpecification;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.TypedQuery;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AdminService {

    private final UserRepository userRepository;
    private final FloorPlanRepository floorPlanRepository;
    private final ChatRoomRepository chatRoomRepository;
    private final ChatHistoryRepository chatHistoryRepository;
    private final FloorplanAnalysisRepository floorplanAnalysisRepository;
    private final S3Service s3Service;

    @PersistenceContext
    private EntityManager entityManager;

    /**
     * 대시보드 통계 조회
     */
    public AdminStatsResponse getAdminStats() {
        Long userCount = userRepository.count();
        Long floorPlanCount = floorPlanRepository.count();
        LocalDateTime sevenDaysAgo = LocalDateTime.now().minusDays(7);
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
     * 활동 로그 조회 - JPQL 프로젝션 + 메모리 병합 + 서버 사이드 페이징
     * JPQL은 엔티티명을 사용하므로 테이블명 대소문자 문제 없음
     * 필요한 컬럼만 SELECT하여 대용량 TEXT(answer) 로딩 방지
     */
    public PageResponse<ActivityLogResponse> getActivityLogsPaged(
            int page, int size,
            String type, String search,
            LocalDate startDate, LocalDate endDate) {

        LocalDateTime startDateTime = (startDate != null) ? startDate.atStartOfDay() : null;
        LocalDateTime endDateTime = (endDate != null) ? endDate.atTime(LocalTime.MAX) : null;
        String searchLower = (search != null && !search.trim().isEmpty()) ? search.trim().toLowerCase() : null;

        boolean includeUser = (type == null || type.isEmpty() || "USER".equals(type));
        boolean includeFloorplan = (type == null || type.isEmpty() || "FLOORPLAN".equals(type));
        boolean includeChat = (type == null || type.isEmpty() || "CHAT".equals(type));

        List<ActivityLogResponse> allLogs = new ArrayList<>();

        // 1) 회원가입 로그 - JPQL 프로젝션 (필요한 컬럼만)
        if (includeUser) {
            StringBuilder jpql = new StringBuilder(
                "SELECT u.id, u.name, u.email, u.role, u.create_at FROM User u WHERE u.create_at IS NOT NULL");
            Map<String, Object> params = new HashMap<>();
            if (startDateTime != null) { jpql.append(" AND u.create_at >= :startDt"); params.put("startDt", startDateTime); }
            if (endDateTime != null) { jpql.append(" AND u.create_at <= :endDt"); params.put("endDt", endDateTime); }
            if (searchLower != null) {
                jpql.append(" AND (LOWER(u.name) LIKE :search OR LOWER(u.email) LIKE :search)");
                params.put("search", "%" + searchLower + "%");
            }

            TypedQuery<Object[]> query = entityManager.createQuery(jpql.toString(), Object[].class);
            params.forEach(query::setParameter);

            for (Object[] row : query.getResultList()) {
                String role = (String) row[3];
                String details = role + " 계정 생성";
                if (searchLower != null && !details.toLowerCase().contains(searchLower)
                        && (row[1] == null || !((String) row[1]).toLowerCase().contains(searchLower))
                        && (row[2] == null || !((String) row[2]).toLowerCase().contains(searchLower))) {
                    continue;
                }
                allLogs.add(ActivityLogResponse.builder()
                        .id((Long) row[0]).type("USER")
                        .userName((String) row[1]).userEmail((String) row[2])
                        .action("회원가입").details(details)
                        .createdAt((LocalDateTime) row[4]).build());
            }
        }

        // 2) 도면 업로드 로그 - JPQL 프로젝션 (JOIN으로 User 함께 조회)
        if (includeFloorplan) {
            StringBuilder jpql = new StringBuilder(
                "SELECT fp.id, fp.name, fp.createdAt, u.name, u.email FROM FloorPlan fp JOIN fp.user u WHERE 1=1");
            Map<String, Object> params = new HashMap<>();
            if (startDateTime != null) { jpql.append(" AND fp.createdAt >= :startDt"); params.put("startDt", startDateTime); }
            if (endDateTime != null) { jpql.append(" AND fp.createdAt <= :endDt"); params.put("endDt", endDateTime); }
            if (searchLower != null) {
                jpql.append(" AND (LOWER(u.name) LIKE :search OR LOWER(u.email) LIKE :search OR LOWER(fp.name) LIKE :search)");
                params.put("search", "%" + searchLower + "%");
            }

            TypedQuery<Object[]> query = entityManager.createQuery(jpql.toString(), Object[].class);
            params.forEach(query::setParameter);

            for (Object[] row : query.getResultList()) {
                String fpName = row[1] != null ? (String) row[1] : "제목 없음";
                allLogs.add(ActivityLogResponse.builder()
                        .id((Long) row[0]).type("FLOORPLAN")
                        .userName((String) row[3]).userEmail((String) row[4])
                        .action("도면 업로드").details(fpName)
                        .createdAt((LocalDateTime) row[2]).build());
            }
        }

        // 3) 챗봇 대화 로그 - JPQL 프로젝션 (JOIN으로 ChatRoom + User 함께 조회, answer 제외)
        if (includeChat) {
            StringBuilder jpql = new StringBuilder(
                "SELECT ch.id, ch.question, ch.createdAt, cr.name, u.name, u.email " +
                "FROM ChatHistory ch JOIN ch.chatRoom cr JOIN cr.user u WHERE 1=1");
            Map<String, Object> params = new HashMap<>();
            if (startDateTime != null) { jpql.append(" AND ch.createdAt >= :startDt"); params.put("startDt", startDateTime); }
            if (endDateTime != null) { jpql.append(" AND ch.createdAt <= :endDt"); params.put("endDt", endDateTime); }
            if (searchLower != null) {
                jpql.append(" AND (LOWER(u.name) LIKE :search OR LOWER(u.email) LIKE :search OR LOWER(cr.name) LIKE :search OR LOWER(ch.question) LIKE :search)");
                params.put("search", "%" + searchLower + "%");
            }

            TypedQuery<Object[]> query = entityManager.createQuery(jpql.toString(), Object[].class);
            params.forEach(query::setParameter);

            for (Object[] row : query.getResultList()) {
                String question = (String) row[1];
                String preview = (question != null && question.length() > 50)
                        ? question.substring(0, 50) + "..."
                        : (question != null ? question : "질문 없음");
                String details = "[" + row[3] + "] " + preview;
                allLogs.add(ActivityLogResponse.builder()
                        .id((Long) row[0]).type("CHAT")
                        .userName((String) row[4]).userEmail((String) row[5])
                        .action("챗봇 질문").details(details)
                        .createdAt((LocalDateTime) row[2]).build());
            }
        }

        // 날짜 역순 정렬
        allLogs.sort(Comparator.comparing(ActivityLogResponse::getCreatedAt).reversed());

        // 서버 사이드 페이징
        long total = allLogs.size();
        int fromIndex = page * size;
        int toIndex = Math.min(fromIndex + size, allLogs.size());
        List<ActivityLogResponse> pagedLogs = (fromIndex >= allLogs.size())
                ? Collections.emptyList()
                : allLogs.subList(fromIndex, toIndex);

        return PageResponse.of(pagedLogs, page, size, total);
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
     * 전체 도면 목록 조회 - 서버 사이드 페이징
     */
    public PageResponse<AdminFloorPlanResponse> getAllFloorPlansPaged(int page, int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<FloorPlan> floorPlanPage = floorPlanRepository.findAllWithUserAndAnalysis(pageable);

        List<AdminFloorPlanResponse> content = floorPlanPage.getContent().stream()
                .map(fp -> convertToAdminFloorPlanResponse(fp, fp.getAnalysis()))
                .collect(Collectors.toList());

        return PageResponse.of(content, floorPlanPage.getNumber(), floorPlanPage.getSize(), floorPlanPage.getTotalElements());
    }

    /**
     * 도면 검색 - 서버 사이드 페이징 + 필터링 (Specification)
     */
    public PageResponse<AdminFloorPlanResponse> searchFloorPlansPaged(
            String name, String uploaderEmail,
            LocalDate startDate, LocalDate endDate,
            Integer minRooms, Integer maxRooms,
            int page, int size) {

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));

        Specification<FloorPlan> spec = Specification
                .where(FloorPlanSpecification.nameLike(name))
                .and(FloorPlanSpecification.uploaderEmailLike(uploaderEmail))
                .and(FloorPlanSpecification.createdAfter(startDate))
                .and(FloorPlanSpecification.createdBefore(endDate))
                .and(FloorPlanSpecification.roomCountBetween(minRooms, maxRooms));

        Page<FloorPlan> floorPlanPage = floorPlanRepository.findAll(spec, pageable);

        // 배치 Analysis 조회 (N+1 해결)
        List<Long> fpIds = floorPlanPage.getContent().stream()
                .map(FloorPlan::getId).collect(Collectors.toList());
        Map<Long, FloorplanAnalysis> analysisMap = fpIds.isEmpty()
                ? Collections.emptyMap()
                : floorplanAnalysisRepository.findByFloorPlanIdIn(fpIds).stream()
                    .collect(Collectors.toMap(a -> a.getFloorPlan().getId(), a -> a));

        List<AdminFloorPlanResponse> content = floorPlanPage.getContent().stream()
                .map(fp -> convertToAdminFloorPlanResponse(fp, analysisMap.get(fp.getId())))
                .collect(Collectors.toList());

        return PageResponse.of(content, floorPlanPage.getNumber(), floorPlanPage.getSize(), floorPlanPage.getTotalElements());
    }

    /**
     * 도면 삭제
     */
    @Transactional
    public String deleteFloorPlans(List<Long> ids) {
        for (Long id : ids) {
            floorPlanRepository.findById(id).ifPresent(fp -> {
                // S3 이미지 삭제 (URL에서 key 추출)
                String imageUrl = fp.getImageUrl();
                if (imageUrl != null && imageUrl.contains(".amazonaws.com/")) {
                    String s3Key = imageUrl.substring(imageUrl.indexOf(".amazonaws.com/") + ".amazonaws.com/".length());
                    try {
                        s3Service.delete(s3Key);
                    } catch (Exception e) {
                        // S3 삭제 실패해도 DB 삭제는 진행
                    }
                }
                floorPlanRepository.delete(fp);
            });
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
     * 도면 이미지 S3 URL 반환
     */
    public String getFloorPlanImageUrl(Long floorplanid) {
        FloorPlan fp = floorPlanRepository.findById(floorplanid)
                .orElseThrow(() -> new RuntimeException("도면을 찾을 수 없습니다."));

        String imageUrl = fp.getImageUrl();
        if (imageUrl == null || imageUrl.isEmpty()) {
            throw new RuntimeException("이미지 URL이 없습니다.");
        }

        return imageUrl;
    }

    /**
     * FloorPlan -> AdminFloorPlanResponse 변환 (단일 조회용)
     */
    private AdminFloorPlanResponse convertToAdminFloorPlanResponse(FloorPlan fp) {
        FloorplanAnalysis analysis = floorplanAnalysisRepository.findByFloorPlanId(fp.getId()).orElse(null);
        return convertToAdminFloorPlanResponse(fp, analysis);
    }

    /**
     * FloorPlan -> AdminFloorPlanResponse 변환 (배치 조회용, N+1 방지)
     */
    private AdminFloorPlanResponse convertToAdminFloorPlanResponse(FloorPlan fp, FloorplanAnalysis analysis) {
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
                .assessmentJson(fp.getAssessmentJson())
                .build();
    }
}
