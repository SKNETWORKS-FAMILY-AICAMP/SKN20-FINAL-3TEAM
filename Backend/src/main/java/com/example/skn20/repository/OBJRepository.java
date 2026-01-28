package com.example.skn20.repository;

import com.example.skn20.entity.OBJ;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface OBJRepository extends JpaRepository<OBJ, Long> {
    // 필요시 커스텀 메서드 추가
}
