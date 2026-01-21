package com.example.skn20.repository;

import com.example.skn20.entity.History;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface HistoryRepository extends JpaRepository<History, Long> {
    // 필요시 커스텀 쿼리 메서드 추가
}
