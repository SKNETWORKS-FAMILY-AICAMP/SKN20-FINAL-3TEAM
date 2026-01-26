package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

import org.hibernate.annotations.CreationTimestamp;

@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long Id;

    @Column(unique = true, nullable = false, length = 100)
    private String email; // 이메일

    @Column(nullable = false)
    private String pw; // 비밀번호

    @Column(length = 50)
    private String name; // 이름

    @Column(length = 15)
    private Integer phonenumber; // 전화번호

    @Column(nullable = false)
    @Builder.Default
    private String role = "USER"; // USER, ADMIN

    @Column(name = "create_at", updatable = false)
    @CreationTimestamp
    private LocalDate create_at; // 첫 가입 일자

    @Column(name = "update_at")
    private LocalDate update_at; // 정보 수정 일자

}

