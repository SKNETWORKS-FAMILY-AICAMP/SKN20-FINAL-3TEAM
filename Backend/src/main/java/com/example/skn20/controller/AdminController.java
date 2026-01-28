package com.example.skn20.controller;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.skn20.entity.ChatRoom;
import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.User;
import com.example.skn20.repository.ChatRoomRepository;
import com.example.skn20.repository.FloorPlanRepository;
import com.example.skn20.repository.UserRepository;
import com.example.skn20.service.AdminService;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;


@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000" })
public class AdminController {
	private final UserRepository userRep;

	private final ChatRoomRepository chatRoomRep;

	private final FloorPlanRepository floorPlanRep;

	private final AdminService adminService;

	// 접속시 유저 리스트
	@GetMapping("/users")
	public ResponseEntity<List<User>> SelectUsers() {
		List<User> users = userRep.findAll();
		return ResponseEntity.ok(users);
	}

	// 특정 유저 검색
	@PostMapping("/searchuser")
	public ResponseEntity<List<User>> SearchUsers(@RequestParam String search) {
		List<User> result = Stream
				.concat(userRep.findByNameContaining(search).stream(), userRep.findByEmailContaining(search).stream())
				.distinct().collect(Collectors.toList());
		return ResponseEntity.ok(result);
	}

	// 유저 정보 수정
	@PostMapping("/edituser")
	public ResponseEntity<String> editUser(@RequestParam Long userid, @RequestParam(required = false) String name, @RequestParam(required = false) Integer phone, @RequestParam(required = false) String role) {
		User user = userRep.findById(userid).orElse(null);
		if (user == null) {
			return ResponseEntity.badRequest().body("해당 유저가 존재하지 않습니다.");
		}
		if (name != null)
			user.setName(name);
		if (phone != null)
			user.setPhonenumber(phone);
		if (role != null)
			user.setRole(role);
		user.setUpdate_at(LocalDate.now());
		userRep.save(user); // 변경사항 저장
		return ResponseEntity.ok("유저 정보가 수정되었습니다.");
	}

	// 유저 채팅 기록 조회
	@PostMapping("/userhistory")
	public ResponseEntity<List<ChatRoom>> UserChatHistory(@RequestParam Long userid) {
		User user = userRep.findById(userid).orElse(null);
		List<ChatRoom> userchats = chatRoomRep.findAllByUser(user);
		return ResponseEntity.ok(userchats);
	}

	// 화면 접속시 모든 도면 로드
	@GetMapping("/floorplans")
	public ResponseEntity<List<FloorPlan>> Allfloorplan() {
		List<FloorPlan> floorPlans = floorPlanRep.findAll();

		return ResponseEntity.ok(floorPlans);
	}

	// 다양한 조건으로 도면 검색 (이름, 날짜, 업로더, 이미지 경로, 공간 수)
	@PostMapping("/searchfloorplan")
	public ResponseEntity<List<FloorPlan>> searchFloorPlan(
			@RequestParam(required = false) String name,
			@RequestParam(required = false) String uploaderEmail,
			@RequestParam(required = false) String imageUrl,
			@RequestParam(required = false) String startDate,
			@RequestParam(required = false) String endDate,
			@RequestParam(required = false) Integer minRooms,
			@RequestParam(required = false) Integer maxRooms,
			@RequestParam(required = false) String roomName,
			@RequestParam(required = false) String objName,
			@RequestParam(required = false) String strName) {
		List<FloorPlan> filtered = adminService.searchFloorPlans(name, uploaderEmail, imageUrl, startDate, endDate,
				minRooms, maxRooms, roomName, objName, strName);
		return ResponseEntity.ok(filtered);
	}
	
	// 유저 상세 조회
	@PostMapping("/userdetail")
	public ResponseEntity<User> getUserDetail(@RequestParam Long userid) {
		User user = userRep.findById(userid).orElse(null);
		if (user == null) {
			return ResponseEntity.badRequest().build();
		}
		return ResponseEntity.ok(user);
	}

	// 도면 상세 조회
	@PostMapping("/floorplandetail")
	public ResponseEntity<FloorPlan> getFloorPlanDetail(@RequestParam Long floorplanid) {
		FloorPlan floorPlan = floorPlanRep.findById(floorplanid).orElse(null);
		if (floorPlan == null) {
			return ResponseEntity.badRequest().build();
		}
		return ResponseEntity.ok(floorPlan);
	}

	// 통계 (유저 수, 도면 수, 최근 등록/삭제 현황 등)
	@GetMapping("/stats")
	public ResponseEntity<?> getStats() {
		long userCount = userRep.count();
		long floorPlanCount = floorPlanRep.count();
		// 최근 7일 등록 도면 수 (예시)
		long recentFloorPlan = floorPlanRep.countRecentFloorPlans(LocalDate.now().minusDays(7));
        
		return ResponseEntity.ok(Map.of(
			"userCount", userCount,
			"floorPlanCount", floorPlanCount,
			"recentFloorPlan", recentFloorPlan
		));
	}

	// 유저 삭제 (한 개 또는 여러 개 모두 리스트로 받아 일괄 삭제)
	// 유저/도면 삭제를 하나의 API로 통합 (type: "user" 또는 "floorp/lan")
	@PostMapping("/deleteentities")
	public ResponseEntity<String> deleteEntities(@RequestParam String type, @RequestBody List<Long> ids) {
		if (ids == null || ids.isEmpty()) {
			return ResponseEntity.badRequest().body("삭제할 ID를 입력하세요.");
		}
		if ("user".equalsIgnoreCase(type)) {
			List<User> users = userRep.findAllById(ids);
			userRep.deleteAll(users);
			return ResponseEntity.ok("선택한 유저가 삭제되었습니다.");
		} else if ("floorplan".equalsIgnoreCase(type)) {
			for (Long id : ids) {
				adminService.deleteFloorPlanWithChildren(id);
			}
			return ResponseEntity.ok("선택한 도면이 삭제되었습니다.");
		} else {
			return ResponseEntity.badRequest().body("지원하지 않는 타입입니다.");
		}
	}
}
