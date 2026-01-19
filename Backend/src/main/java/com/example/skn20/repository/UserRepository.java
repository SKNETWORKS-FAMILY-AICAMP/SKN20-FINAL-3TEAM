package com.example.skn20.repository;

import com.example.skn20.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    User findByEmail(String email);
    Optional<User> findByName(String name);
    boolean existsByEmail(String email);
    boolean existsByName(String name);
}

