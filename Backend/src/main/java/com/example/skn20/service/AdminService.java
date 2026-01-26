package com.example.skn20.service;

import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.example.skn20.entity.FloorPlan;
import com.example.skn20.repository.FloorPlanRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class AdminService {

	private final FloorPlanRepository floorPlanRep;

	// 다양한 조건으로 FloorPlan 검색
	public List<FloorPlan> searchFloorPlans(String name, String uploaderEmail, String imageUrl, String startDate,
			String endDate, Integer minRooms, Integer maxRooms, String roomName, String objName, String strName) {
		List<FloorPlan> all = floorPlanRep.findAll();
		return all.stream().filter(fp -> name == null || fp.getName() != null && fp.getName().contains(name))
				.filter(fp -> uploaderEmail == null
						|| (fp.getUser() != null && fp.getUser().getEmail().contains(uploaderEmail)))
				.filter(fp -> imageUrl == null || (fp.getImageUrl() != null && fp.getImageUrl().contains(imageUrl)))
				.filter(fp -> {
					if (startDate == null && endDate == null)
						return true;
					LocalDate created = fp.getCreatedAt();
					if (created == null)
						return false;
					boolean afterStart = startDate == null || !created.isBefore(LocalDate.parse(startDate));
					boolean beforeEnd = endDate == null || !created.isAfter(LocalDate.parse(endDate));
					return afterStart && beforeEnd;
				}).filter(fp -> {
					int roomCount = (fp.getRooms() != null) ? fp.getRooms().size() : 0;
					boolean minOk = minRooms == null || roomCount >= minRooms;
					boolean maxOk = maxRooms == null || roomCount <= maxRooms;
					return minOk && maxOk;
				})
				// Room 이름 포함 여부
				.filter(fp -> {
					if (roomName == null)
						return true;
					if (fp.getRooms() == null)
						return false;
					return fp.getRooms().stream()
							.anyMatch(r -> r.getSpcname() != null && r.getSpcname().contains(roomName));
				})
				// OBJ 이름 포함 여부
				.filter(fp -> {
					if (objName == null)
						return true;
					if (fp.getRooms() == null)
						return false;
					return fp.getRooms().stream().anyMatch(r -> r.getObjs() != null && r.getObjs().stream()
							.anyMatch(o -> o.getName() != null && o.getName().contains(objName)));
				})
				// STR 이름 포함 여부
				.filter(fp -> {
					if (strName == null)
						return true;
					if (fp.getRooms() == null)
						return false;
					return fp.getRooms().stream().anyMatch(r -> r.getStrs() != null && r.getStrs().stream()
							.anyMatch(s -> s.getName() != null && s.getName().contains(strName)));
				}).collect(Collectors.toList());
	}
	
    // 도면 및 하위 엔티티(rooms, objs, strs)까지 안전하게 삭제
	@Transactional
	public boolean deleteFloorPlanWithChildren(Long floorplanid) {
		FloorPlan floorPlan = floorPlanRep.findById(floorplanid).orElse(null);
		if (floorPlan == null) return false;

		// 하위 Room, OBJ, STR 직접 삭제 (JPA cascade가 없을 경우)
		if (floorPlan.getRooms() != null) {
			for (var room : floorPlan.getRooms()) {
				// OBJ 삭제
				if (room.getObjs() != null) {
					room.getObjs().clear();
				}
				// STR 삭제
				if (room.getStrs() != null) {
					room.getStrs().clear();
				}
			}
			floorPlan.getRooms().clear();
		}

		// 도면 이미지 파일 삭제 (imageUrl 경로가 실제 파일이라면)
		String imagePath = floorPlan.getImageUrl();
		if (imagePath != null && !imagePath.isEmpty()) {
			try {
				File file = new File(imagePath);
				if (file.exists()) file.delete();
			} catch (Exception e) {
				// 파일 삭제 실패는 무시하고 진행
			}
		}

		floorPlanRep.delete(floorPlan);
		return true;
	}
}
