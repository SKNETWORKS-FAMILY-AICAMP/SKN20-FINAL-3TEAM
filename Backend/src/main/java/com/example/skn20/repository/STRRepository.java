package com.example.skn20.repository;

import com.example.skn20.entity.STR;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface STRRepository extends JpaRepository<STR, Long> {
    // 필요시 커스텀 메서드 추가
}
