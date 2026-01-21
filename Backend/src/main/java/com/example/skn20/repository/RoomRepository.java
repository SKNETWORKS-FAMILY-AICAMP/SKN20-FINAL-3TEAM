package com.example.skn20.repository;

import com.example.skn20.entity.Room;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface RoomRepository extends JpaRepository<Room, Long> {
    // 필요시 커스텀 메서드 추가
}
